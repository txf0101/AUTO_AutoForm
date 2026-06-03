"""这个文件让用户可以用 `python -m autoform_agent` 启动项目命令。它本身不放业务逻辑，只把请求交给命令行入口处理。

This file lets users start the project with `python -m autoform_agent`. It does not hold business rules; it forwards execution to the command-line entry point.
"""

from .cli import main


if __name__ == "__main__":
    # Convert the integer return value from `main` into the process exit status.
    raise SystemExit(main())
