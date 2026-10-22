#!/bin/bash
# macOS 启动器：双击即可（第一次可能需要在「系统设置 → 隐私与安全性」里允许）
cd "$(dirname "$0")" || exit 1

# 补充 macOS 常见可执行文件路径（Finder 双击启动时 PATH 默认不含 Homebrew / Cargo / Conda）
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.cargo/bin:$HOME/.local/bin:$HOME/bin:$PATH"

CANDIDATES=(
    "$(pwd)/.venv/bin/python3"
    "$(pwd)/venv/bin/python3"
)

if [ -n "$CONDA_PREFIX" ] && [ -x "$CONDA_PREFIX/bin/python3" ]; then
    CANDIDATES+=("$CONDA_PREFIX/bin/python3")
fi

CANDIDATES+=(
    "/opt/miniconda3/bin/python3"
    "$HOME/miniconda3/bin/python3"
    "$HOME/opt/miniconda3/bin/python3"
    "/opt/homebrew/Caskroom/miniconda/base/bin/python3"
    "/opt/anaconda3/bin/python3"
    "$HOME/anaconda3/bin/python3"
    "$HOME/miniforge3/bin/python3"
    "/opt/miniforge3/bin/python3"
    "$(command -v python3 2>/dev/null)"
    "/opt/homebrew/bin/python3"
    "/usr/local/bin/python3"
    "/usr/bin/python3"
)

PY=""
FALLBACK_PY=""

for cand in "${CANDIDATES[@]}"; do
    if [ -n "$cand" ] && [ -x "$cand" ]; then
        if [ -z "$FALLBACK_PY" ]; then
            FALLBACK_PY="$cand"
        fi
        if "$cand" -c "import PySide6" >/dev/null 2>&1; then
            PY="$cand"
            break
        fi
    fi
done

if [ -z "$PY" ]; then
    if [ -z "$FALLBACK_PY" ]; then
        echo "找不到 python3，请先安装 Python 3（例如 brew install python 或安装 Miniconda）。"
        read -r -p "按回车退出..."
        exit 1
    fi

    echo "未在现有 Python 环境中检测到 PySide6，正在准备本地虚拟环境 (.venv)..."
    if [ ! -x ".venv/bin/python3" ]; then
        "$FALLBACK_PY" -m venv .venv || {
            echo "创建虚拟环境失败，请手动执行：pip install PySide6"
            read -r -p "按回车退出..."
            exit 1
        }
    fi
    PY="$(pwd)/.venv/bin/python3"
    echo "正在安装 PySide6（首次安装可能需要几分钟）..."
    "$PY" -m pip install --upgrade pip >/dev/null 2>&1
    "$PY" -m pip install PySide6 || {
        echo "安装失败，请手动在终端执行：$PY -m pip install PySide6"
        read -r -p "按回车退出..."
        exit 1
    }
fi

echo "正在使用 $PY 启动 DDL 小组件..."
nohup "$PY" run.pyw "$@" >/dev/null 2>&1 &
disown 2>/dev/null || true
echo "DDL 小组件已在后台启动，现在可以安全关闭此终端窗口。"
exit 0
