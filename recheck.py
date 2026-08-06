import os
import re
import subprocess
import threading
from enum import IntEnum
from typing import Tuple  # noqa: UP035

import orjson

if (ex := os.environ.get("RECHECK_EXECUTABLE")) is None:
    raise RuntimeError(
        "RECHECK_EXECUTABLE environment variable not set. Please download the recheck executable from github.com/makenowjust-labs/recheck/releases and put its path into the RECHECK_EXECUTABLE envvar."
    )
RECHECK_EXECUTABLE = ex


def _p2jre(py_regex, py_flags=0) -> Tuple[str, str]:  # 此函数改编自Whitestar14/pytojsregex，可能有AI成分  # noqa: UP006
    if py_flags & re.VERBOSE:
        py_regex = _reverbose(py_regex)
        py_flags &= ~re.VERBOSE
    js_regex = re.sub(r"\(\?P<(\w+)>", r"(?<\1>", py_regex)
    js_regex = js_regex.replace(r"\A", "^").replace(r"\Z", "$")
    js_regex = js_regex.replace(r"\#", "#")
    js_regex = re.sub(r"\(\?P=(\w+)\)", (lambda match: f"\\k<{match.group(1)}>"), js_regex)
    if r"\p" in js_regex or r"\P" in js_regex:
        py_flags |= re.UNICODE
    js_regex = js_regex.replace(r"\N", "")
    js_flags = ""
    if py_flags & re.IGNORECASE:
        js_flags += "i"
    if py_flags & re.MULTILINE:
        js_flags += "m"
    if py_flags & re.DOTALL:
        js_flags += "s"
    if py_flags & re.UNICODE:
        js_flags += "u"
    return js_regex, js_flags


def _reverbose(regex):
    lines = []
    for line in regex.split("\n"):
        in_class = False
        i = 0
        while i < len(line):
            if line[i] == "\\":
                i += 2
                continue
            if line[i] == "[":
                in_class = True
            elif line[i] == "]":
                in_class = False
            elif line[i] == "#" and not in_class:
                line = line[:i]
                break
            i += 1
        lines.append(line)
    stripped = "\n".join(lines)
    result = []
    in_class = False
    i = 0
    while i < len(stripped):
        ch = stripped[i]
        if ch == "\\":
            result.append(ch)
            i += 1
            if i < len(stripped):
                result.append(stripped[i])
            i += 1
            continue
        if ch == "[" and not in_class:
            in_class = True
            result.append(ch)
        elif ch == "]" and in_class:
            in_class = False
            result.append(ch)
        elif not ch.isspace() or in_class:
            result.append(ch)
        i += 1
    clean = re.sub(r"\(\?x\)", "", "".join(result))
    return clean.strip()


class Complexity(IntEnum):
    CONSTANT = 1
    LINEAR = 2
    SAFE = 3
    POLYNOMIAL = 4
    EXPONENTIAL = 5


class Rechecker:
    def __init__(self):
        try:
            self._process = subprocess.Popen(
                [RECHECK_EXECUTABLE, "agent"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
            )
        except OSError as e:
            raise RuntimeError(f"Failed to start recheck executable: {e} Please check your path or file") from e

        self._counter = 0
        self._responses = {}
        self._cond = threading.Condition()
        self._stop_event = threading.Event()
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def _reader_loop(self):
        assert self._process.stdout
        while not self._stop_event.is_set():
            line = self._process.stdout.readline()
            if not line:
                break
            resp = orjson.loads(line)
            if "id" in resp:
                rid = resp["id"]
                with self._cond:
                    self._responses[rid] = resp
                    self._cond.notify_all()

    def check(self, regex: str, flags: int = 0) -> Tuple[Complexity, int]:  # noqa: UP006
        assert self._process.stdin
        js_regex, js_flags = _p2jre(regex, flags)

        with self._cond:
            self._counter += 1
            req_id = self._counter

        request = {
            "jsonrpc": "2.0+push",
            "id": req_id,
            "method": "check",
            "params": {
                "source": js_regex,
                "flags": js_flags,
                "params": {
                    "checker": "automaton",
                    "maxRecallStringSize": 0,
                    "recallLimit": 0,
                },
            },
        }
        payload = orjson.dumps(request) + b"\n"
        self._process.stdin.write(payload)
        self._process.stdin.flush()

        with self._cond:
            while req_id not in self._responses:
                self._cond.wait()
            resp = self._responses.pop(req_id)

        result = resp.get("result", {})
        complexity_info = result.get("complexity", {})
        type_str = complexity_info.get("type", "").lower()
        degree: int = complexity_info.get("degree", 0)

        type_map = {
            "constant": Complexity.CONSTANT,
            "linear": Complexity.LINEAR,
            "safe": Complexity.SAFE,
            "polynomial": Complexity.POLYNOMIAL,
            "exponential": Complexity.EXPONENTIAL,
        }
        complexity_enum = type_map[type_str]
        return complexity_enum, degree

    def close(self):
        assert self._process.stdin
        if hasattr(self, "_process") and self._process.poll() is None:
            self._process.stdin.close()
            self._stop_event.set()
            self._reader_thread.join(timeout=1.0)

            try:
                self._process.terminate()
                self._process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()

    def __del__(self):
        self.close()


__all__ = ["Complexity", "Rechecker"]
