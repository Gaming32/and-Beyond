from typing import TYPE_CHECKING, Optional

from typing_extensions import Self

if TYPE_CHECKING:
    from and_beyond.world import WorldChunk

BLOCKS: list[Optional['Block']] = [None] * 256


def get_block_by_id(id: int) -> 'Block':
    block = BLOCKS[id]
    if block is None:
        return AIR
    return block


class Block:
    id: int
    name: str
    bounding_box: Optional['AABB']
    turnable_texture: bool = False
    texture_path: Optional[str]
    luminescence: int = 0

    def __init__(self, id: int, name: str) -> None:
        self.id = id
        self.name = name
        self.bounding_box = AABB(0, 0, 1, 1)
        self.texture_path = f'blocks/{name}.png'
        BLOCKS[id] = self

    def set_bounding_box(self, bb: Optional['AABB']) -> Self:
        self.bounding_box = bb
        return self

    def set_turnable_texture(self, turnable: bool) -> Self:
        self.turnable_texture = turnable
        return self

    def set_texture_path(self, path: Optional[str]) -> Self:
        self.texture_path = path
        return self

    def set_luminescence(self, luminescence: int) -> Self:
        self.luminescence = luminescence
        return self

    def on_place(self, chunk: 'WorldChunk', x: int, y: int) -> None:
        self.update_lighting(chunk, x, y)

    def update_lighting(self, chunk: 'WorldChunk', x: int, y: int) -> None:
        while self._propogate_lighting(chunk, x, y, set()):
            pass

    def _propogate_lighting(self, chunk: 'WorldChunk', x: int, y: int, encountered: set[tuple[int, int]]) -> bool:
        if (x, y) in encountered:
            return False
        left_blocklight = 0
        if x > 0:
            left_blocklight = chunk.get_blocklight(x - 1, y)
        right_blocklight = 0
        if x < 15:
            right_blocklight = chunk.get_blocklight(x + 1, y)
        down_blocklight = 0
        if y > 0:
            down_blocklight = chunk.get_blocklight(x, y - 1)
        up_blocklight = 0
        if y < 15:
            up_blocklight = chunk.get_blocklight(x, y + 1)
        blocklight = max(
            self.luminescence,
            left_blocklight - 1,
            right_blocklight - 1,
            down_blocklight - 1,
            up_blocklight - 1
        )
        old_blocklight = chunk.get_blocklight(x, y)
        chunk.set_blocklight(x, y, blocklight)
        encountered.add((x, y))
        child_changed = False
        if x > 0:
            child_changed |= chunk.get_tile_type(x - 1, y)._propogate_lighting(chunk, x - 1, y, encountered)
        if x < 15:
            child_changed |= chunk.get_tile_type(x + 1, y)._propogate_lighting(chunk, x + 1, y, encountered)
        if y > 0:
            child_changed |= chunk.get_tile_type(x, y - 1)._propogate_lighting(chunk, x, y - 1, encountered)
        if y < 15:
            child_changed |= chunk.get_tile_type(x, y + 1)._propogate_lighting(chunk, x, y + 1, encountered)
        return child_changed or blocklight != old_blocklight

    def _propogate_lighting_dimmer(self, chunk: 'WorldChunk', x: int, y: int) -> None:
        pass

    def __repr__(self) -> str:
        return f'<Block {self.name} id={self.id}>'


from and_beyond.physics import AABB

AIR    = Block(0, 'air').set_bounding_box(None).set_texture_path(None)
STONE  = Block(1, 'stone').set_turnable_texture(True)
DIRT   = Block(2, 'dirt').set_turnable_texture(True)
GRASS  = Block(3, 'grass')
WOOD   = Block(4, 'wood')
PLANKS = Block(5, 'planks')
LEAVES = Block(6, 'leaves').set_turnable_texture(True)
TORCH  = Block(7, 'torch').set_bounding_box(None).set_luminescence(12)
