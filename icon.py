from PIL import Image, ImageDraw, ImageFont
import os, math

out = "./nplabplot_white_2.ico"

sizes = [16, 24, 32, 48, 64, 128, 256]

# def font(size, bold=False):
#     # candidates = [
#     # "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
#     # "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
#     # ]
#     # for p in candidates:
#     #     if os.path.exists(p):
#     #         return ImageFont.truetype(p, size)
#     return ImageFont.load_default()

base = Image.new("RGBA", (256, 256), (255, 255, 255, 255))
d = ImageDraw.Draw(base)

# clean rounded white card
d.rounded_rectangle((8, 8, 248, 248), radius=52, fill=(255, 255, 255, 255), outline=(210,210,210,255), width=3)

# axes
d.line((42, 202, 222, 202), fill=(40, 40, 40, 255), width=6)
d.line((42, 202, 42, 56), fill=(40, 40, 40, 255), width=6)

# plot curve
pts = []
for i in range(0, 170):
    x = 48 + i
    y = 142 - 42 * math.sin(i / 27.0) - 0.2 * i
    pts.append((x, y))

d.line(pts, fill=(0, 120, 255, 255), width=9, joint="curve")

# title
# f = font(38, bold=True)
# text = "nplab"
# bbox = d.textbbox((0, 0), text, font=f)
# tw = bbox[2] - bbox[0]

# d.text(((256 - tw) / 2, 22), text, font=f, fill=(20, 20, 20, 255))

base.save(out, format="ICO", sizes=[(s, s) for s in sizes])

print(out)