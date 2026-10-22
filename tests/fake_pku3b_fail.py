"""假的 pku3b：模拟未登录 / 网络失败。"""

import sys

sys.stderr.buffer.write(
    "\x1b[31m\x1b[1mError\x1b[0m\x1b[0m: check if OTP is required: tls handshake failed\n".encode("utf-8")
)
sys.stderr.buffer.flush()
sys.exit(1)
