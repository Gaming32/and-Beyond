# pyright: reportWildcardImportFromLibrary=false
import logging
import random
from typing import Optional

import pygame
import pygame.mixer
from and_beyond.client import globals
from pygame import *
from pygame.locals import *

TITLE_TRACKS = [
    pygame.mixer.Sound('assets/music/Evening Fall - Harp.ogg'),
    pygame.mixer.Sound('assets/music/Enchanted Valley.ogg'),
]

OVERWORLD_TRACKS = [
    TITLE_TRACKS[0],
    TITLE_TRACKS[1],
]

CAVE_TRACKS = [
    TITLE_TRACKS[0],
    pygame.mixer.Sound('assets/music/Terminal D - Silent Partner.ogg'),
]

SONG_NAMES = {
    TITLE_TRACKS[0]: 'Evening Fall - Harp',
    TITLE_TRACKS[1]: 'Enchanted Valley',
    CAVE_TRACKS[1]: 'Terminal D',
}


class Mixer:
    music_channel: Optional[pygame.mixer.Channel]
    current_song: Optional[pygame.mixer.Sound]
    volume: float

    def __init__(self) -> None:
        if pygame.mixer.get_num_channels():
            self.music_channel = pygame.mixer.Channel(0)
            pygame.mixer.set_reserved(0) # type: ignore (the stubs are incorrect)
        else:
            logging.warn('No music channels available')
            self.music_channel = None
        self.current_song = None
        self.volume = 1.0

    def set_volume(self, volume: float) -> None:
        self.volume = volume
        if self.music_channel is not None:
            self.music_channel.set_volume(volume)

    def play_song(self, song: pygame.mixer.Sound = None) -> None:
        logging.debug('Playing new song')
        if self.music_channel is None:
            logging.debug('No music channel')
            return
        if song is None:
            try:
                # Select song from state
                if globals.game_status != globals.GameStatus.IN_GAME:
                    song = random.choice(TITLE_TRACKS)
                elif globals.player.y > -75:
                    song = random.choice(OVERWORLD_TRACKS)
                elif globals.player.y < -125:
                    song = random.choice(CAVE_TRACKS)
                else:
                    chance = (abs(globals.player.y) - 75) / (125 - 75)
                    tracks = OVERWORLD_TRACKS if random.random() < chance else CAVE_TRACKS
                    song = random.choice(tracks)
            except IndexError:
                logging.debug('No song found')
                return
        logging.info('Playing song -- %s', SONG_NAMES.get(song, str(song)))
        self.current_song = song
        song.set_volume(self.volume)
        self.music_channel.play(song, fade_ms=500)

    def stop_all_music(self) -> None:
        if self.music_channel is not None:
            self.music_channel.fadeout(500)
