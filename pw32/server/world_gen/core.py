# import perlin_noise

from typing import TYPE_CHECKING

from pw32.server.world_gen.phase import AbstractPhase
from pw32.server.world_gen.phases.caves import CavePhase
from pw32.utils import autoslots

if TYPE_CHECKING:
    from pw32.world import WorldChunk


@autoslots
class WorldGenerator:
    seed: int
    phases: list[AbstractPhase]

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.phases = [
            GroundPhase(self),
            CavePhase(self),
        ]

    def generate_chunk(self, chunk: 'WorldChunk') -> None:
        for phase in self.phases:
            phase.generate_chunk(chunk)


from pw32.server.world_gen.phases.ground import GroundPhase
