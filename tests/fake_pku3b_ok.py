"""假的 pku3b：输出与真实 assignment list 一致格式的文本（含 ANSI）。"""

import sys

TEXT = (
    "\x1b[2m>\x1b[22m \x1b[1m未完成作业 (4)\x1b[22m \x1b[2m<\x1b[22m\n"
    "\n"
    "\x1b[36m\x1b[1m计算概论A\x1b[22m\x1b[39m \x1b[2m>\x1b[22m "
    "\x1b[36m\x1b[1m第三次作业\x1b[22m\x1b[39m "
    "(\x1b[31min 0d 4h 20m 30s\x1b[39m) f4f30444c7485d49\n"
    "\n"
    "\x1b[36m\x1b[1m数据结构\x1b[22m\x1b[39m \x1b[2m>\x1b[22m "
    "\x1b[36m\x1b[1m大作业（含报告）\x1b[22m\x1b[39m "
    "(\x1b[33min 3d 2h 1m 5s\x1b[39m) 9c1a7f30b2e54d18\n"
    "\n"
    "\x1b[36m\x1b[1m操作系统\x1b[22m\x1b[39m \x1b[2m>\x1b[22m "
    "\x1b[36m\x1b[1m实验一\x1b[22m\x1b[39m "
    "(\x1b[2m已完成: 尝试 26-9-14 下午8:17\x1b[22m) 2b3c4d5e6f7a8b9c\n"
    "\n"
    "\x1b[36m\x1b[1m线性代数\x1b[22m\x1b[39m \x1b[2m>\x1b[22m "
    "\x1b[36m\x1b[1m习题课\x1b[22m\x1b[39m "
    "(\x1b[2m无截止时间\x1b[22m) 1a2b3c4d5e6f7a8b\n"
)

sys.stdout.buffer.write(TEXT.encode("utf-8"))
sys.stdout.buffer.flush()
