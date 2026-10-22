"""Windows 启动入口：先修复 Qt DLL 搜索路径，再加载应用。

用 pythonw.exe 运行可获得无控制台的静默启动（开机自启用这个）。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ddlwidget.sysutil import sanitize_dll_path  # noqa: E402

_removed = sanitize_dll_path()

from ddlwidget.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv))
