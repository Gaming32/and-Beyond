from typing import Optional

from typing_extensions import Self

from and_beyond.physics import AABB

BLOCKS: list[Optional['Block']] = [None] * 256


class Block:
    id: int
    name: str
    bounding_box: AABB
    turnable_texture: bool = False

    def __init__(self, id: int, name: str) -> None:
        self.id = id
        self.name = name
        self.bounding_box = AABB(0, 0, 1, 1)
        BLOCKS[id] = self

    def set_bounding_box(self, bb: AABB) -> None:
        self.bounding_box = bb

    def set_turnable_texture(self, turnable: bool) -> Self:
        self.turnable_texture = turnable
        return self


STONE  = Block(1, 'stone').set_turnable_texture(True)
DIRT   = Block(2, 'dirt').set_turnable_texture(True)
GRASS  = Block(3, 'grass')
WOOD   = Block(4, 'wood')
PLANKS = Block(5, 'planks')
LEAVES = Block(6, 'leaves').set_turnable_texture(True)
