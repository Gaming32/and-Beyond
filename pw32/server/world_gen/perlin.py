import math
import random
from typing import Callable, Optional

from pw32.utils import autoslots

PERM = [
    151, 160, 137, 91, 90, 15,
    131, 13, 201, 95, 96, 53, 194, 233, 7, 225, 140, 36, 103, 30, 69, 142, 8, 99, 37, 240, 21, 10, 23,
    190,  6, 148, 247, 120, 234, 75, 0, 26, 197, 62, 94, 252, 219, 203, 117, 35, 11, 32, 57, 177, 33,
    88, 237, 149, 56, 87, 174, 20, 125, 136, 171, 168,  68, 175, 74, 165, 71, 134, 139, 48, 27, 166,
    77, 146, 158, 231, 83, 111, 229, 122, 60, 211, 133, 230, 220, 105, 92, 41, 55, 46, 245, 40, 244,
    102, 143, 54,  65, 25, 63, 161,  1, 216, 80, 73, 209, 76, 132, 187, 208,  89, 18, 169, 200, 196,
    135, 130, 116, 188, 159, 86, 164, 100, 109, 198, 173, 186,  3, 64, 52, 217, 226, 250, 124, 123,
    5, 202, 38, 147, 118, 126, 255, 82, 85, 212, 207, 206, 59, 227, 47, 16, 58, 17, 182, 189, 28, 42,
    223, 183, 170, 213, 119, 248, 152,  2, 44, 154, 163,  70, 221, 153, 101, 155, 167,  43, 172, 9,
    129, 22, 39, 253,  19, 98, 108, 110, 79, 113, 224, 232, 178, 185,  112, 104, 218, 246, 97, 228,
    251, 34, 242, 193, 238, 210, 144, 12, 191, 179, 162, 241,  81, 51, 145, 235, 249, 14, 239, 107,
    49, 192, 214,  31, 181, 199, 106, 157, 184,  84, 204, 176, 115, 121, 50, 45, 127,  4, 150, 254,
    138, 236, 205, 93, 222, 114, 67, 29, 24, 72, 243, 141, 128, 195, 78, 66, 215, 61, 156, 180,
    151
]


@autoslots
class PerlinNoise:
    perm: list[int]

    def __init__(self, seed: Optional[int] = None) -> None:
        if seed is None:
            self.perm = PERM[:]
        else:
            p = PERM[:]
            r = random.Random(seed)
            r.shuffle(p)
            self.perm = p

    def noise_1d(self, x: float) -> float:
        x2 = int(x) & 0xff
        x -= math.floor(x)
        u = self._fade(x)
        return self._lerp(u, self._grad_1d(self.perm[x2], x), self._grad_1d(self.perm[x2 + 1], x - 1)) * 2

    def noise_2d(self, x: float, y: float) -> float:
        x2 = int(x) & 0xff
        y2 = int(y) & 0xff
        x -= math.floor(x)
        y -= math.floor(y)
        u = self._fade(x)
        v = self._fade(y)
        a = (self.perm[x2] + y2) & 0xff
        b = (self.perm[x2 + 1] + y2) & 0xff
        return self._lerp(v, self._lerp(u, self._grad_2d(self.perm[a], x, y), self._grad_2d(self.perm[b], x - 1, y)),
                             self._lerp(u, self._grad_2d(self.perm[a + 1], x, y - 1), self._grad_2d(self.perm[b + 1], x - 1, y - 1)))

    def fbm_1d(self, x: float, octave: int) -> float:
        return self._fbm(self.noise_1d, octave, x)

    def fbm_2d(self, x: float, y: float, octave: int) -> float:
        return self._fbm(self.noise_2d, octave, x, y)

    def _fbm(self, noise_function: Callable[..., float], octave: int, *coords: float) -> float:
        coords_l = list(coords)
        f = 0.0
        w = 0.5
        for i in range(octave):
            f += w * noise_function(*coords_l)
            for j in range(len(coords_l)):
                coords_l[j] *= 2.0
            w *= 0.5
        return f

    def _fade(self, t: float) -> float:
        return t * t * t * (t * (t * 6 - 15) + 10)

    def _lerp(self, t: float, a: float, b: float) -> float:
        return a + t * (b - a)

    def _grad_1d(self, hash: int, x: float) -> float:
        return x if (hash & 1) else -x

    def _grad_2d(self, hash: int, x: float, y: float) -> float:
        return (x if (hash & 1) else -x) + (y if (hash & 2) else -y)
