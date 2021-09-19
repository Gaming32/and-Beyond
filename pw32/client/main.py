# pyright: reportWildcardImportFromLibrary=false
import logging

import pygame
import pygame.display
import pygame.event
import pygame.time
from pw32.client import globals
from pw32.client.globals import ConfigManager
from pw32.client.title import TitleScreen
from pw32.utils import init_logger
from pygame import *
from pygame.locals import *

init_logger()
logging.info('Starting client...')
pygame.init()
logging.info('Pygame loaded')

globals.display_info = pygame.display.Info()
globals.config = config = ConfigManager(globals.display_info)

def reset_window() -> Surface:
    pygame.display.init()
    globals.display_info = pygame.display.Info()
    if globals.fullscreen:
        globals.w_width = globals.display_info.current_w
        globals.w_height = globals.display_info.current_h
    else:
        globals.w_width = config.config['w_width']
        globals.w_height = config.config['w_height']
    # type: ignore is needed to shut type checkers up about https://github.com/pygame/pygame/issues/839#issuecomment-812919220
    return pygame.display.set_mode(
        (globals.w_width, globals.w_height),
        (FULLSCREEN if globals.fullscreen else 0) | RESIZABLE
    ) # type: ignore

globals.fullscreen = config.config['fullscreen']
screen = reset_window()

title = TitleScreen()


globals.at_title = True
globals.running = True
clock = pygame.time.Clock()
while globals.running:
    for event in pygame.event.get():
        if event.type == QUIT:
            globals.running = False
        elif event.type == VIDEORESIZE:
            logging.debug('Screen resize')
            if not globals.fullscreen:
                globals.w_width = event.w
                globals.w_height = event.h
        elif event.type == KEYDOWN:
            if event.key == K_F11:
                globals.fullscreen = not globals.fullscreen
                logging.debug('Switching fullscreen mode...')
                pygame.display.quit()
                screen = reset_window()

    if globals.at_title:
        title.render(screen)

    pygame.display.update()


logging.info('Quitting...')
config.save()
pygame.quit()