from typing import Protocol, Union

from typing_extensions import Self

JsonPrimitive = Union[
    int, float,
    str,
    bool,
    None
]
JsonObject = dict[str, 'ValidJson']
JsonArray = Union[list['ValidJson'], tuple['ValidJson']]
JsonStructure = Union[JsonObject, JsonArray]
ValidJson = Union[JsonPrimitive, JsonStructure]


class JsonSerializable(Protocol):
    def to_json(self) -> ValidJson: ...
    @classmethod
    def from_json(cls, data: ValidJson) -> Self: ...
