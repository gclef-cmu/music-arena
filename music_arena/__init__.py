from .audio import Audio
from .dataclass import (
    DetailedTextToMusicPrompt,
    SimpleTextToMusicPrompt,
    TextToMusicResponse,
)
from .path import LIB_DIR
from .system import PromptSupport, TextToMusicSystem

__all__ = [
    "Audio",
    "DetailedTextToMusicPrompt",
    "SimpleTextToMusicPrompt",
    "TextToMusicResponse",
    "TextToMusicSystem",
    "PromptSupport",
]


# NOTE: This changes the test discovery pattern from "test*.py" (default) to "*test.py".
def load_tests(loader, standard_tests, pattern):
    package_tests = loader.discover(start_dir=LIB_DIR, pattern="*test.py")
    standard_tests.addTests(package_tests)
    return standard_tests
