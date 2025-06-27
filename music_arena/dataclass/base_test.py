import unittest
from dataclasses import dataclass
from typing import Any, Optional

from .base import MusicArenaDataClass


@dataclass
class Foo(MusicArenaDataClass):
    a: int


@dataclass
class Bar(MusicArenaDataClass):
    b: int
    c: Optional[Foo] = None

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "Bar":
        if d.get("c") is not None:
            d["c"] = Foo.from_json_dict(d["c"])
        return cls.from_dict(d)


@dataclass
class Baz(MusicArenaDataClass):
    d: int
    e: Bar

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "Baz":
        d["e"] = Bar.from_json_dict(d["e"])
        return cls.from_dict(d)


class TestMusicArenaDataclass(unittest.TestCase):
    def test_as_json_dict(self):
        f = Foo(a=1)
        b = Bar(b=2, c=f)
        baz = Baz(d=3, e=b)
        self.assertEqual(baz.as_json_dict(), {"d": 3, "e": {"b": 2, "c": {"a": 1}}})

    def test_from_json_dict(self):
        # Test simple case without nested objects
        d = {"a": 1}
        foo = Foo.from_json_dict(d)
        self.assertEqual(foo.a, 1)

        # Test with None values
        d = {"b": 2, "c": None}
        bar = Bar.from_json_dict(d)
        self.assertEqual(bar.b, 2)
        self.assertIsNone(bar.c)


if __name__ == "__main__":
    unittest.main()
