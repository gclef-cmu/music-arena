import unittest
from typing import Optional

from .prompt import DetailedTextToMusicPrompt, SimpleTextToMusicPrompt


class _ExtendedTextToMusicPrompt(DetailedTextToMusicPrompt):
    some_new_field: Optional[str] = None


class TextToMusicPromptTest(unittest.TestCase):
    def test_post_init(self):
        with self.assertRaises(ValueError):
            DetailedTextToMusicPrompt(
                overall_prompt="heavy metal", instrumental=True, lyrics="lyrics"
            )

    def test_generate_lyrics(self):
        prompt = DetailedTextToMusicPrompt(
            overall_prompt="heavy metal", instrumental=True, lyrics=None
        )
        self.assertFalse(prompt.generate_lyrics)
        prompt = DetailedTextToMusicPrompt(
            overall_prompt="heavy metal", instrumental=False, lyrics="lyrics"
        )
        self.assertFalse(prompt.generate_lyrics)
        prompt = DetailedTextToMusicPrompt(
            overall_prompt="heavy metal", instrumental=False, lyrics=None
        )
        self.assertTrue(prompt.generate_lyrics)

    def test_from_text(self):
        prompt = SimpleTextToMusicPrompt.from_text("heavy metal")
        self.assertEqual(prompt.prompt, "heavy metal")

    def test_as_dict(self):
        prompt = DetailedTextToMusicPrompt(
            overall_prompt="heavy metal", instrumental=True, lyrics=None
        )
        self.assertEqual(
            prompt.as_dict(),
            {
                "overall_prompt": "heavy metal",
                "instrumental": True,
                "lyrics": None,
                "duration": None,
            },
        )
        prompt = DetailedTextToMusicPrompt(
            overall_prompt="heavy metal", instrumental=False, lyrics="lyrics"
        )
        self.assertEqual(
            prompt.as_dict(),
            {
                "overall_prompt": "heavy metal",
                "instrumental": False,
                "lyrics": "lyrics",
                "duration": None,
            },
        )
        prompt = DetailedTextToMusicPrompt(
            overall_prompt="heavy metal", instrumental=False, lyrics=None
        )
        self.assertEqual(
            prompt.as_dict(),
            {
                "overall_prompt": "heavy metal",
                "instrumental": False,
                "lyrics": None,
                "duration": None,
            },
        )

    def test_checksum(self):
        prompt = SimpleTextToMusicPrompt(prompt="heavy metal")
        self.assertEqual(prompt.checksum, "2064d7a16d7385599cfb7d63d6653a32")
        prompt = DetailedTextToMusicPrompt(
            overall_prompt="heavy metal", instrumental=True, lyrics=None
        )
        self.assertEqual(prompt.checksum, "f09577079db8a81f475ae94e85ddd3a7")
        prompt = DetailedTextToMusicPrompt(
            overall_prompt="heavy metal", instrumental=True, lyrics=None, duration=None
        )
        self.assertEqual(prompt.checksum, "f09577079db8a81f475ae94e85ddd3a7")
        prompt = DetailedTextToMusicPrompt(
            overall_prompt="heavy metal", instrumental=True, lyrics=None, duration=2.0
        )
        self.assertEqual(prompt.checksum, "8fcfd48ccc257fca63355dc236a7ecdc")
        prompt = DetailedTextToMusicPrompt(
            overall_prompt=None, instrumental=True, lyrics=None
        )
        self.assertEqual(prompt.checksum, "bc53810b01fe23bf3737c07c0e4a1986")
        prompt = DetailedTextToMusicPrompt(
            overall_prompt="heavy metal", instrumental=False, lyrics="We will rock you"
        )
        self.assertEqual(prompt.checksum, "e2ad45cdb73ac1118b4ed9fa03d0222d")
        eprompt = _ExtendedTextToMusicPrompt(
            overall_prompt="heavy metal", instrumental=True, lyrics=None
        )
        self.assertEqual(eprompt.checksum, "f09577079db8a81f475ae94e85ddd3a7")
        self.assertEqual(eprompt.some_new_field, None)


if __name__ == "__main__":
    unittest.main()
