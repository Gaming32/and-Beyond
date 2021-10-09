import pygame.event

UI_BG = (29, 107, 103)
UI_FG = (194, 209, 151)

BLOCK_RENDER_SIZE = 25
CHAT_DISPLAY_TIME = 5.0 # Seconds

SERVER_CONNECT_EVENT = pygame.event.custom_type()
SERVER_DISCONNECT_EVENT = pygame.event.custom_type()
PERIODIC_TICK_EVENT = pygame.event.custom_type()
