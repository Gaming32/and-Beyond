from typing import Protocol, Union

from typing_extensions import Self

ValidJson = Union[
    dict[str, 'ValidJson'],
    list['ValidJson'], tuple['ValidJson'],
    int, float,
    str,
    bool,
    None
]


class JsonSerializable(Protocol):
    def to_json(self) -> ValidJson: ...
    @classmethod
    def from_json(cls, data: ValidJson) -> Self: ...
