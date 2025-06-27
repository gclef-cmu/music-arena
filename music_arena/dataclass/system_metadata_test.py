import unittest

from .system_metadata import SystemAccess, SystemKey, TextToMusicSystemMetadata


class TextToMusicSystemMetadataTest(unittest.TestCase):
    def test_post_init(self):
        default_kwargs = {
            "key": SystemKey(system_tag="musicgen-small", variant_tag="initial"),
            "display_name": "MusicGen Small",
            "description": "...",
            "organization": "Meta",
            "access": SystemAccess.OPEN,
            "supports_lyrics": False,
            "module_name": "musicgen",
            "class_name": "MusicGen",
        }
        TextToMusicSystemMetadata.from_dict(default_kwargs)
        result = TextToMusicSystemMetadata(**default_kwargs)
        self.assertTrue(result.requires_gpu)
        default_kwargs["access"] = SystemAccess.PROPRIETARY
        result = TextToMusicSystemMetadata(**default_kwargs)
        self.assertFalse(result.requires_gpu)


if __name__ == "__main__":
    unittest.main()
