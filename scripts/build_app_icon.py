"""Generate Memivo's existing layered mark as SVG, PNG, and a multi-size Windows ICO."""
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def main():
    destination = ROOT / 'frontend/public'
    destination.mkdir(parents=True, exist_ok=True)
    marks = [(4, 4, .5), (11, 9, .75), (18, 13, 1)]
    slope = math.tan(math.radians(15))
    scale = 32
    image = Image.new('RGBA', (36 * scale, 36 * scale))
    groups = []
    for x, y, opacity in marks:
        groups.append(f'<g transform="translate({x} {y + slope * 6.5:.6f}) skewY(-15)" opacity="{opacity}"><rect width="13" height="19" rx="5"/></g>')
        layer = Image.new('RGBA', image.size)
        ImageDraw.Draw(layer).rounded_rectangle(
            (x*scale, y*scale, (x+13)*scale, (y+19)*scale),
            radius=5*scale, fill=(59, 83, 245, round(255*opacity)))
        layer = layer.transform(image.size, Image.Transform.AFFINE,
            (1, 0, 0, slope, 1, -slope*(x+6.5)*scale), Image.Resampling.BICUBIC)
        image = Image.alpha_composite(image, layer)
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36"><g fill="#3b53f5">' + ''.join(groups) + '</g></svg>\n'
    (destination/'memivo.svg').write_text(svg, encoding='utf-8')
    image = image.resize((256, 256), Image.Resampling.LANCZOS)
    image.save(destination/'memivo.png')
    image.save(destination/'memivo.ico', sizes=[(size, size) for size in (16,20,24,32,40,48,64,128,256)])


if __name__ == '__main__':
    main()
