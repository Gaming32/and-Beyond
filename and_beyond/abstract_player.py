import abc
import math
from typing import TYPE_CHECKING, Iterable, Optional, cast

from typing_extensions import Self

from and_beyond import blocks
from and_beyond.abc import JsonArray, ValidJson
from and_beyond.blocks import Block, get_block_by_id
from and_beyond.common import REACH_DISTANCE_SQ

if TYPE_CHECKING:
    from and_beyond.physics import AABB, PlayerPhysics
    from and_beyond.world import AbstractWorld, WorldChunk


class InventoryItem:
    item: Block
    count: int

    def __init__(self, item: Block, count: int = 1) -> None:
        self.item = item
        self.count = count

    @classmethod
    def from_json(cls, data: ValidJson) -> Self:
        assert isinstance(data, dict)
        return cls(get_block_by_id(cast(int, data['item'])), cast(int, data['count']))

    def to_json(self) -> ValidJson:
        return {
            'item': self.item.id,
            'count': self.count,
        }


class PlayerInventory:
    items: list[Optional[InventoryItem]]
    selected: int

    def __init__(self) -> None:
        self.items = [
            InventoryItem(blocks.STONE),
            InventoryItem(blocks.DIRT),
            InventoryItem(blocks.GRASS),
            InventoryItem(blocks.WOOD),
            InventoryItem(blocks.PLANKS),
            InventoryItem(blocks.LEAVES),
            InventoryItem(blocks.TORCH),
            InventoryItem(blocks.SLAB),
            None
        ]
        self.selected = 0

    @classmethod
    def from_json(cls, data: ValidJson) -> Self:
        assert isinstance(data, dict)
        inventory = cls()
        inventory.items = [
            None if item is None else InventoryItem.from_json(item)
            for item in cast(JsonArray, data['items'])
        ]
        inventory.selected = cast(int, data['selected'])
        return inventory

    def to_json(self) -> ValidJson:
        return {
            'items': [item.to_json() if item is not None else None for item in self.items],
            'selected': self.selected,
        }

    @property
    def selected_item(self) -> Optional[InventoryItem]:
        return self.items[self.selected]


class AbstractPlayer(abc.ABC):
    x: float
    y: float
    loaded_chunks: dict[tuple[int, int], 'WorldChunk']
    world: 'AbstractWorld'
    physics: 'PlayerPhysics'
    inventory: PlayerInventory

    def can_reach(self,
        x: float, y: float,
        for_place: Optional['AABB'], bbs: Optional[Iterable['AABB']] = None
    ) -> bool:
        rel_x = x - self.x
        rel_y = y - self.y
        if rel_x == math.inf or rel_y == math.inf:
            return False
        if for_place is not None:
            for_place += x, y
            if bbs is None:
                bbs = [self.physics.offset_bb]
            for bb in bbs:
                if bb.intersect(for_place):
                    return False
        dist = rel_x * rel_x + rel_y * rel_y
        return dist <= REACH_DISTANCE_SQ
