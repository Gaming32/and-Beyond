import re

PORT = 7932
PROTOCOL_VERSION = 3
PROTOCOL_VERSION_MAP = [
    'a1.2.2', # 0
    'a1.2.3', # 1
    'a1.2.4', # 2
    'a1.3.0', # 3
]
VERSION_DISPLAY_NAME = 'a1.3.0'

KEY_LENGTH = 32
AUTH_SERVER = 'ab-auth.jemnetworks.com'
_USERNAME_REGEX = '[_a-zA-Z][_a-zA-Z0-9]{0,15}'
USERNAME_REGEX = re.compile(_USERNAME_REGEX)

VIEW_DISTANCE = 8
VIEW_DISTANCE_BOX = 2 * VIEW_DISTANCE + 1
REACH_DISTANCE = 5
REACH_DISTANCE_SQ = REACH_DISTANCE * REACH_DISTANCE
MOVE_SPEED = 3
MOVE_SPEED_CAP = 7
MOVE_SPEED_CAP_SQ = MOVE_SPEED_CAP * MOVE_SPEED_CAP
JUMP_SPEED = 1.5
GRAVITY = -5


def get_version_name(protocol_version: int) -> str:
    if 0 <= protocol_version < len(PROTOCOL_VERSION_MAP):
        return PROTOCOL_VERSION_MAP[protocol_version]
    return 'UNKNOWN'
