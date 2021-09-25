# pyright: reportWildcardImportFromLibrary=false
import asyncio
import logging
import sys
import time as pytime

import janus
import pygame
import pygame.display
import pygame.draw
import pygame.event
import pygame.mouse
import pygame.time
from and_beyond.utils import init_logger

init_logger('client.log')
logging.info('Starting client...')
pygame.init()
logging.info('Pygame loaded')
logging.info('Loading assets...')
start = pytime.perf_counter()
from and_beyond.client.assets import ASSET_COUNT, GAME_FONT, transform_assets

end = pytime.perf_counter()
logging.info('Loaded %i assets in %f seconds', ASSET_COUNT, end - start)

from and_beyond.client import globals
from and_beyond.client.consts import UI_FG
from and_beyond.client.globals import ConfigManager, GameStatus
from and_beyond.client.player import ClientPlayer
from and_beyond.client.server_connection import ServerConnection
from and_beyond.client.ui.pause_menu import PauseMenu
from and_beyond.client.ui.title_screen import TitleScreen
from and_beyond.client.utils import screen_to_world
from and_beyond.client.world import ClientWorld
from and_beyond.common import JUMP_SPEED, MOVE_SPEED
from and_beyond.packet import PlayerPositionPacket
from pygame import *
from pygame.locals import *

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
old_fullscreen = globals.fullscreen
screen = reset_window()

logging.info('Performing asset transformations...')
start = pytime.perf_counter()
count = transform_assets()
end = pytime.perf_counter()
logging.info('Transformed %i assets in %f seconds', count, end - start)

title = TitleScreen()
pause_menu = PauseMenu()

globals.local_world = ClientWorld()
globals.player = ClientPlayer()


move_left = False
move_right = False
move_up = False
globals.game_status = GameStatus.MAIN_MENU
globals.running = True
globals.frame = 0
clock = pygame.time.Clock()
while globals.running:
    try:
        globals.delta = clock.tick(globals.config.config['max_framerate']) / 1000
        globals.released_mouse_buttons = [False] * 5
        if globals.fullscreen != old_fullscreen:
            logging.debug('Switching fullscreen mode...')
            pygame.display.quit()
            screen = reset_window()
        old_fullscreen = globals.fullscreen

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
                elif event.key == K_d:
                    move_right = True
                elif event.key == K_a:
                    move_left = True
                elif event.key == K_SPACE:
                    move_up = True
                elif event.key == K_ESCAPE:
                    if globals.paused:
                        pause_menu.continue_game()
                    else:
                        pause_menu.pause_game()
            elif event.type == KEYUP:
                if event.key == K_d:
                    move_right = False
                elif event.key == K_a:
                    move_left = False
            elif event.type == MOUSEBUTTONUP:
                globals.released_mouse_buttons[event.button - 1] = True

        globals.mouse_screen = Vector2(pygame.mouse.get_pos())

        if globals.game_connection is not None and not globals.paused:
            if move_left ^ move_right:
                globals.player.add_velocity(x=MOVE_SPEED * globals.delta * (move_right - move_left))
            if move_up:
                globals.player.add_velocity(y=JUMP_SPEED)
                move_up = False

        if globals.game_status == GameStatus.MAIN_MENU:
            title.draw_and_call(screen)
        elif globals.game_status in (GameStatus.CONNECTING, GameStatus.STOPPING):
            screen.fill((0, 0, 0))
            text_render = GAME_FONT.render(globals.connecting_status, True, UI_FG)
            x = screen.get_width() // 2 - text_render.get_width() // 2
            y = screen.get_height() // 2 - text_render.get_height() // 2
            area = text_render.get_rect().move(x, y)
            screen.blit(text_render, area)
            if globals.game_status == GameStatus.STOPPING:
                if globals.singleplayer_popen is not None:
                    if (returncode := globals.singleplayer_popen.poll()) is not None:
                        if returncode:
                            logging.warn('Singleplayer server stopped with exit code %i', returncode)
                        globals.singleplayer_popen = None
                        globals.game_status = GameStatus.MAIN_MENU
        else:
            globals.mouse_world = screen_to_world(globals.mouse_screen, screen)
            globals.local_world.tick(screen)
            globals.player.render(screen)
            text_render = GAME_FONT.render(str(1 / globals.delta), True, UI_FG)
            screen.fill((0, 0, 0), text_render.get_rect())
            screen.blit(text_render, text_render.get_rect())
            if globals.paused:
                pause_menu.draw_and_call(screen)

        pygame.display.update()
        globals.frame += 1
    except BaseException as e:
        if isinstance(e, Exception):
            logging.critical('Game crashed hard with exception', exc_info=True)
        globals.running = False


logging.info('Quitting...')

# I can't use pygame.quit() because it segfaults for some reason when in fullscreen mode
pygame.mixer.quit()
pygame.font.quit()
pygame.joystick.quit()
pygame.display.quit()

if globals.game_connection is not None:
    globals.game_connection.stop()
globals.close_singleplayer_server()
config.save()
