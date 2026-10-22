import sys
from PIL import Image

src, dst = sys.argv[1], sys.argv[2]
x, y, w, h = (int(v) for v in sys.argv[3:7])
scale = float(sys.argv[7])
img = Image.open(src)
crop = img.crop((x, y, x + w, y + h))
crop = crop.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
crop.save(dst)
print("saved", dst, crop.size)
