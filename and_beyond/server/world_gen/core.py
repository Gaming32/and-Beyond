# import perlin_noise

from typing import TYPE_CHECKING

from and_beyond.server.world_gen.perlin import PerlinNoise
from and_beyond.server.world_gen.phase import AbstractPhase
from and_beyond.server.world_gen.phases.biomes import (BiomeTypesPhase,
                                                       sample_biome_at)
from and_beyond.server.world_gen.phases.caves import CavePhase
from and_beyond.server.world_gen.phases.sky_islands import SkyIslandsPhase
from and_beyond.utils import autoslots
from and_beyond.world import BiomeTypes

if TYPE_CHECKING:
    from and_beyond.world import WorldChunk

BIOME_FLIP_CONSTANT = 8112343193046603085


@autoslots
class WorldGenerator:
    seed: int
    phases: list[AbstractPhase]

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.biome_generator = PerlinNoise(seed ^ BIOME_FLIP_CONSTANT)
        self.phases = [
            BiomeTypesPhase(self),
            GroundPhase(self),
            CavePhase(self),
            SkyIslandsPhase(self),
        ]

    def sample_biome_at(self, x: int) -> BiomeTypes:
        return sample_biome_at(x, self.biome_generator)

    def generate_chunk(self, chunk: 'WorldChunk') -> None:
        for phase in self.phases:
            phase.generate_chunk(chunk)


from and_beyond.server.world_gen.phases.ground import GroundPhase
