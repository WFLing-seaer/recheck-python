recheck的Python封装层

Python wrapper for recheck

<br/>

需要去[recheck官方页面](github.com/makenowjust-labs/recheck/releases)安装recheck二进制可执行文件然后把二进制路径放到环境变量`RECHECK_EXECUTABLE`里

You need to go to the [recheck official page](github.com/makenowjust-labs/recheck/releases) to install the recheck binary executable and then add the binary path to the environment variable `RECHECK_EXECUTABLE`.

<br/>

唯一API：

Only API:

```python
import recheck
c = recheck.Rechecker() # 这会拉起一个recheck agent
c.check("\\w+_\\w+_\\w+$") # 或者(regex, flags)
(<Complexity.POLYNOMIAL: 4>, 4)
```

<br/>

返回Complexity枚举值（良序的）与多项式次数，可以直接tuple比较（比如`check_result < (recheck.Complexity.POLYNOMIAL,2)`

Returns a well-ordered Complexity enumeration value and its polynomial degree, which can be directly compared using a tuple (e.g., `check_result < (recheck.Complexity.POLYNOMIAL, 2)`).

<br/>

与recheck官方无任何关联

Not related to the original/official recheck project.

<br/>

不保证检验的准确性，本库对此不负责

The accuracy of the inspection is not guaranteed, and this program is not responsible for it.
