import random
import colorsys

from PIL import Image

CHANCE = 0.6
BASE_COLOR = (120 / 360, 75 / 100)
VALUE_RANGE = (20, 35)

image = Image.new('RGBA', (12, 12), (0, 0, 0, 0))
for x in range(image.width):
    for y in range(image.height):
        if random.random() < CHANCE:
            color_hsv = BASE_COLOR + (random.randint(*VALUE_RANGE) / 100,)
            color_rgb = colorsys.hsv_to_rgb(*color_hsv)
            image.putpixel((x, y), tuple(int(c * 255) for c in color_rgb) + (255,))
image.save('leaves.png')
