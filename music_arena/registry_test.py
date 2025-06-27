import pathlib
import tempfile
import unittest

from .dataclass.system_metadata import SystemAccess, SystemKey
from .registry import get_registered_systems, get_system_metadata, init_system

TEST_YAML_GOOD = """
foo:
  display_name: "Foo"
  description: "Foo description"
  organization: "Foo"
  access: "OPEN"
  supports_lyrics: true
  variants:
    "initial":
      module_name: "foo"
      class_name: "Bar"
      description: "Foo variant"
"""

TEST_YAML_BAD = """
missing-attrs:
  display_name: "Missing Attr"
""".strip()


class RegistryTest(unittest.TestCase):
    def test_get_system_metadata(self):
        system_key = SystemKey(system_tag="noise", variant_tag="loud")
        system = get_system_metadata(system_key)
        self.assertEqual(system.key.system_tag, "noise")
        self.assertEqual(system.key.variant_tag, "loud")
        self.assertEqual(system.display_name, "Noise")
        self.assertEqual(
            system.description, "Noise generator for testing. Slightly louder noise."
        )
        self.assertEqual(system.organization, "ACME")
        self.assertEqual(system.access, SystemAccess.OPEN)
        self.assertEqual(system.supports_lyrics, True)
        self.assertEqual(system.module_name, "dsp")
        self.assertEqual(system.class_name, "Noise")
        self.assertEqual(system.requires_gpu, False)
        self.assertEqual(system.model_type, "DSP")
        self.assertEqual(system.training_data, {"type": "None"})
        self.assertIsNone(system.citation)
        self.assertEqual(system.links, {"home": "#"})
        with self.assertRaises(ValueError):
            invalid_key = SystemKey(
                system_tag="musicgen-small", variant_tag="not-a-real-variant"
            )
            get_system_metadata(invalid_key)

    def test_init_system(self):
        loud_key = SystemKey(system_tag="noise", variant_tag="loud")
        system = init_system(loud_key)
        self.assertEqual(system.gain, 0.01)
        self.assertEqual(system.lyrics, "Foo")
        self.assertEqual(str(system.__class__), "<class 'dsp.Noise'>")
        quiet_key = SystemKey(system_tag="noise", variant_tag="quiet")
        system = init_system(quiet_key)
        self.assertEqual(system.gain, 0.005)
        self.assertEqual(system.lyrics, "Bar")
        self.assertEqual(str(system.__class__), "<class 'dsp.Noise'>")

    def test_get_registered_systems(self):
        systems = get_registered_systems()
        self.assertGreater(len(systems), 0)
        loud_key = SystemKey(system_tag="noise", variant_tag="loud")
        quiet_key = SystemKey(system_tag="noise", variant_tag="quiet")
        self.assertIn(loud_key, systems)
        self.assertIn(quiet_key, systems)

    def test_parse_systems(self):
        with tempfile.NamedTemporaryFile(mode="w") as f:
            f.write(TEST_YAML_GOOD)
            f.flush()
            systems = get_registered_systems(pathlib.Path(f.name))
            self.assertEqual(len(systems), 1)
            foo_key = SystemKey(system_tag="foo", variant_tag="initial")
            self.assertIn(foo_key, systems)
            self.assertEqual(systems[foo_key].key.system_tag, "foo")
            self.assertEqual(systems[foo_key].key.variant_tag, "initial")
        with self.assertRaises(TypeError):
            with tempfile.NamedTemporaryFile(mode="w") as f:
                f.write(TEST_YAML_BAD)
                f.flush()
                get_registered_systems(pathlib.Path(f.name))


if __name__ == "__main__":
    unittest.main()
