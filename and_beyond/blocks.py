from typing import Optional

from typing_extensions import Self

from and_beyond.physics import AABB

BLOCKS: list[Optional['Block']] = [None] * 256


def get_block_by_id(id: int) -> 'Block':
    block = BLOCKS[id]
    if block is None:
        return AIR
    return block


class Block:
    id: int
    name: str
    bounding_box: Optional[AABB]
    turnable_texture: bool = False
    texture_path: Optional[str]

    def __init__(self, id: int, name: str) -> None:
        self.id = id
        self.name = name
        self.bounding_box = AABB(0, 0, 1, 1)
        self.texture_path = f'blocks/{name}.png'
        BLOCKS[id] = self

    def set_bounding_box(self, bb: Optional[AABB]) -> Self:
        self.bounding_box = bb
        return self

    def set_turnable_texture(self, turnable: bool) -> Self:
        self.turnable_texture = turnable
        return self

    def set_texture_path(self, path: Optional[str]) -> Self:
        self.texture_path = path
        return self


AIR    = Block(0, 'air').set_bounding_box(None).set_texture_path(None)
STONE  = Block(1, 'stone').set_turnable_texture(True)
DIRT   = Block(2, 'dirt').set_turnable_texture(True)
GRASS  = Block(3, 'grass')
WOOD   = Block(4, 'wood')
PLANKS = Block(5, 'planks')
LEAVES = Block(6, 'leaves').set_turnable_texture(True)
