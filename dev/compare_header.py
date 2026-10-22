"""把新旧两版头部拼在一起做对比。"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
old = Image.open(ROOT / ".tmp" / "old_main.png").convert("RGB")
new = Image.open(ROOT / "docs" / "screenshots" / "main.png").convert("RGB")

x0, y0, x1, y1 = 360, 40, 670, 110
crop_old = old.crop((x0, y0, x1, y1))
crop_new = new.crop((x0, y0, x1, y1))

scale = 3
w, h = x1 - x0, y1 - y0
canvas = Image.new("RGB", (w * scale, h * scale * 2 + 14), (10, 11, 16))
canvas.paste(crop_old.resize((w * scale, h * scale), Image.LANCZOS), (0, 0))
canvas.paste(crop_new.resize((w * scale, h * scale), Image.LANCZOS), (0, h * scale + 14))
out = ROOT / "dev" / "shots" / "header_compare.png"
canvas.save(out)
print("saved", out, canvas.size)
