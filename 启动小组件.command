#!/bin/bash
# macOS 启动器：双击即可（第一次可能需要在「系统设置 → 隐私与安全性」里允许）
cd "$(dirname "$0")" || exit 1

if [ -x "/opt/homebrew/bin/python3" ]; then
    PY="/opt/homebrew/bin/python3"
elif [ -x "/usr/local/bin/python3" ]; then
    PY="/usr/local/bin/python3"
else
    PY="$(command -v python3)"
fi

if [ -z "$PY" ]; then
    echo "找不到 python3，请先安装：brew install python"
    read -r -p "按回车退出..."
    exit 1
fi

"$PY" -c "import PySide6" 2>/dev/null || {
    echo "缺少 PySide6，正在尝试安装..."
    "$PY" -m pip install PySide6 || {
        echo "安装失败，请手动执行： $PY -m pip install PySide6"
        read -r -p "按回车退出..."
        exit 1
    }
}

exec "$PY" run.pyw "$@"
