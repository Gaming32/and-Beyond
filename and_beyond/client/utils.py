from and_beyond.client import globals
from and_beyond.client.consts import BLOCK_RENDER_SIZE
from pygame import Surface, Vector2


def world_to_screen(x: float, y: float, surf: Surface) -> Vector2:
    draw_pos = (Vector2(x, y + 1) - globals.camera) * BLOCK_RENDER_SIZE
    draw_pos += Vector2(surf.get_size()) / 2
    draw_pos.y = surf.get_height() - draw_pos.y
    return draw_pos # type: ignore (more pygame.Y versus pygame.x.Y issues)


def screen_to_world(pos: Vector2, surf: Surface) -> tuple[float, float]:
    pos = Vector2(pos) # Copy
    pos.y = surf.get_height() - pos.y
    pos -= Vector2(surf.get_size()) / 2 # type: ignore
    pos = pos / BLOCK_RENDER_SIZE + globals.camera # type: ignore
    return pos.x, pos.y - 1


def lerp(a: float, b: float, f: float) -> float:
    return a + f * (b - a)
