# pyright: reportWildcardImportFromLibrary=false
import asyncio
import logging
import sys
import time as pytime
from math import inf
from typing import Optional

import pygame
import pygame.display
import pygame.draw
import pygame.event
import pygame.mouse
import pygame.time
from and_beyond.utils import DEBUG, init_logger

init_logger('client.log')
logging.info('Starting client...')
pygame.init()
logging.info('Pygame loaded')
logging.info('Loading assets...')
start = pytime.perf_counter()
from and_beyond.client.assets import (ASSET_COUNT, DEBUG_FONT, GAME_FONT,
                                      transform_assets)

end = pytime.perf_counter()
logging.info('Loaded %i assets in %f seconds', ASSET_COUNT, end - start)

from and_beyond.client import globals
from and_beyond.client.consts import SERVER_DISCONNECT_EVENT, UI_FG
from and_beyond.client.globals import ConfigManager, GameStatus
from and_beyond.client.mixer import Mixer
from and_beyond.client.player import ClientPlayer
from and_beyond.client.ui.label_screen import LabelScreen
from and_beyond.client.ui.pause_menu import PauseMenu
from and_beyond.client.ui.title_screen import TitleScreen
from and_beyond.client.utils import screen_to_world
from and_beyond.client.world import ClientWorld
from and_beyond.common import JUMP_SPEED, MOVE_SPEED
from and_beyond.world import BlockTypes
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


def render_debug() -> None:
    y = 0
    lines = [
        f'FPS: {clock.get_fps():.2f}',
        f'X/Y: {globals.player.x:.1f}/{globals.player.y:.1f}',
    ]
    if globals.player.x != inf and globals.player.y != inf:
        cx = int(globals.player.x) >> 4
        cy = int(globals.player.y) >> 4
        lines.extend([
            f'CX/CY: {cx}/{cy}',
            f'SX/SY: {cx >> 4}/{cy >> 4}',
        ])
    lines.extend([
        f'Loaded chunks: {len(globals.local_world.loaded_chunks)}',
    ])
    for line in lines:
        text_render = DEBUG_FONT.render(line, False, (0, 0, 0))
        screen.blit(text_render, text_render.get_rect().move(0, y))
        y += text_render.get_height()


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
should_show_debug = DEBUG

globals.local_world = ClientWorld()
globals.player = ClientPlayer()

globals.game_status = GameStatus.MAIN_MENU
globals.mixer = Mixer()
globals.mixer.set_volume(globals.config.config['volume'])
globals.mixer.play_song()

disconnect_reason: Optional[str] = None
move_left = False
move_right = False
move_up = False
globals.running = True
globals.frame = 0
clock = pygame.time.Clock()
while globals.running:
    try:
        globals.delta = clock.tick(globals.config.config['max_framerate']) / 1000
        globals.released_mouse_buttons = [False] * 7
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
                elif event.key == K_F3:
                    should_show_debug = not should_show_debug
                elif event.key == K_d:
                    move_right = True
                elif event.key == K_a:
                    move_left = True
                elif event.key == K_SPACE:
                    move_up = True
                elif event.key == K_ESCAPE:
                    if globals.ui_override is not None:
                        globals.ui_override.close()
                    elif globals.paused:
                        pause_menu.continue_game()
                    else:
                        pause_menu.pause_game()
                elif event.key == K_1:
                    globals.player.change_selected_block(BlockTypes.STONE)
                elif event.key == K_2:
                    globals.player.change_selected_block(BlockTypes.DIRT)
                elif event.key == K_3:
                    globals.player.change_selected_block(BlockTypes.GRASS)
            elif event.type == KEYUP:
                if event.key == K_d:
                    move_right = False
                elif event.key == K_a:
                    move_left = False
            elif event.type == MOUSEBUTTONUP:
                if event.button == 6 and globals.ui_override is not None:
                    globals.ui_override.close()
                globals.released_mouse_buttons[event.button - 1] = True
            elif event.type == SERVER_DISCONNECT_EVENT:
                globals.game_status = globals.GameStatus.STOPPING
                globals.mixer.stop_all_music()
                globals.mixer.play_song()
                globals.connecting_status = 'Disconnecting'
                if globals.game_connection is not None:
                    globals.game_connection.stop()
                    globals.game_connection = None
                if globals.singleplayer_pipe is not None:
                    globals.connecting_status = 'Stopping singleplayer server'
                    globals.close_singleplayer_server(False)
                    globals.singleplayer_pipe = None
                disconnect_reason = event.reason

        if globals.mixer.music_channel is not None and not globals.mixer.music_channel.get_busy():
            globals.mixer.play_song()
        globals.mouse_screen = Vector2(pygame.mouse.get_pos())

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
                        if disconnect_reason is not None:
                            if disconnect_reason.lower() != 'Server closed':
                                globals.ui_override = LabelScreen(disconnect_reason)
                            disconnect_reason = None
                else:
                    globals.game_status = GameStatus.MAIN_MENU
                    if disconnect_reason is not None:
                        globals.ui_override = LabelScreen(disconnect_reason)
                        disconnect_reason = None
        else:
            globals.mouse_world = screen_to_world(globals.mouse_screen, screen)
            if globals.game_connection is not None and not globals.paused:
                if move_left ^ move_right:
                    globals.player.add_velocity(x=MOVE_SPEED * globals.delta * (move_right - move_left))
                if move_up:
                    globals.player.add_velocity(y=JUMP_SPEED)
                    move_up = False
            globals.local_world.tick(screen)
            globals.player.render(screen)
            if should_show_debug:
                render_debug()
            elif globals.config.config['always_show_fps']:
                text_render = DEBUG_FONT.render(f'{int(clock.get_fps())} FPS', False, (0, 0, 0))
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
