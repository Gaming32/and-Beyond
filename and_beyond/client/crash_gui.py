import traceback

import pygame

from and_beyond.client.consts import PERIODIC_TICK_EVENT


def _render_crash_gui(crash_font: pygame.font.Font, surf: pygame.surface.Surface, lines: list[str]) -> None:
    surf.fill((255, 255, 255))
    y = 10
    for line in lines:
        line_render = crash_font.render(line, True, (0, 0, 0))
        surf.blit(line_render, (10, y))
        y += line_render.get_height() + 2


def display_crash_gui(exc: Exception) -> None:
    base_tb = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    tb_lines = base_tb.split('\n')
    lines = ['Your game has crashed! Here is a brief summary of the error:'] + tb_lines

    if pygame.scrap.get_init():
        lines[0] += ' (click to copy)'
        copy_font = pygame.font.SysFont('monospace', 36)
    else:
        copy_font = None

    crash_font = pygame.font.SysFont('monospace', 12)
    surf = pygame.display.get_surface()
    _render_crash_gui(crash_font, surf, lines)

    running = True
    copy_time = 0
    clock = pygame.time.Clock()
    pygame.time.set_timer(PERIODIC_TICK_EVENT, 0)
    while running:
        clock.tick(10) # Prevent ticking too much

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and copy_font is not None:
                pygame.scrap.put(pygame.SCRAP_TEXT, base_tb.encode())
                copy_time = pygame.time.get_ticks()
                copy_render = copy_font.render('Copied to clipboard!', True, (0, 255, 0))
                surf.blit(copy_render, (
                    surf.get_width() - copy_render.get_width() - 10,
                    surf.get_height() - copy_render.get_height() - 10
                ))
            elif event.type in (pygame.VIDEORESIZE, pygame.VIDEOEXPOSE):
                _render_crash_gui(crash_font, surf, lines)

        if copy_time > 0 and pygame.time.get_ticks() - copy_time > 2000:
            copy_time = 0
            _render_crash_gui(crash_font, surf, lines)

        pygame.display.update()
