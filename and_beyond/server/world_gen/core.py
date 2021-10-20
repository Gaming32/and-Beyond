from typing import TYPE_CHECKING

from and_beyond.server.world_gen.phase import AbstractPhase
from and_beyond.server.world_gen.phases.caves import CavePhase
from and_beyond.server.world_gen.phases.decorations import TreeDecorationPhase
from and_beyond.server.world_gen.phases.sky_islands import SkyIslandsPhase
from and_beyond.utils import autoslots

if TYPE_CHECKING:
    from and_beyond.world import WorldChunk

@autoslots
class WorldGenerator:
    seed: int
    ground: 'GroundPhase'
    phases: list[AbstractPhase]

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.ground = GroundPhase(self)
        self.phases = [
            self.ground,
            CavePhase(self),
            SkyIslandsPhase(self),
            TreeDecorationPhase(self),
        ]

    def generate_chunk(self, chunk: 'WorldChunk') -> None:
        for phase in self.phases:
            phase.generate_chunk(chunk)


from and_beyond.server.world_gen.phases.ground import GroundPhase
