import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .secret import get_secret, get_secret_var_name


class TestGetSecretVarName(unittest.TestCase):
    def test_get_secret_var_name(self):
        self.assertEqual(get_secret_var_name("test"), "MUSIC_ARENA_SECRET_TEST")
        self.assertEqual(
            get_secret_var_name("user_salt"), "MUSIC_ARENA_SECRET_USER_SALT"
        )
        self.assertEqual(get_secret_var_name("API_KEY"), "MUSIC_ARENA_SECRET_API_KEY")
        self.assertEqual(get_secret_var_name("some-tag"), "MUSIC_ARENA_SECRET_SOME-TAG")


class TestGetSecret(unittest.TestCase):
    def setUp(self):
        # Clear the LRU cache before each test
        get_secret.cache_clear()

    def test_get_secret_from_environment(self):
        with patch.dict(os.environ, {"MUSIC_ARENA_SECRET_TEST": "env-secret"}):
            with patch("music_arena.secret._SECRETS_DIR") as mock_secrets_dir:
                mock_path = mock_secrets_dir / "test.txt"
                mock_path.exists.return_value = False
                mock_path.write_text = unittest.mock.Mock()

                result = get_secret("test")

                self.assertEqual(result, "env-secret")
                mock_path.write_text.assert_called_once_with("env-secret")

    def test_get_secret_from_file(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("music_arena.secret._SECRETS_DIR") as mock_secrets_dir:
                mock_path = mock_secrets_dir / "test.txt"
                mock_path.exists.return_value = True
                mock_path.read_text.return_value = "file-secret"

                result = get_secret("test")

                self.assertEqual(result, "file-secret")
                mock_path.read_text.assert_called_once()

    def test_get_secret_randomly_initialize(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("music_arena.secret._SECRETS_DIR") as mock_secrets_dir:
                with patch("music_arena.secret.secrets.token_hex") as mock_token_hex:
                    mock_path = mock_secrets_dir / "test.txt"
                    mock_path.exists.return_value = False
                    mock_path.write_text = unittest.mock.Mock()
                    mock_token_hex.return_value = "random-secure-token"

                    result = get_secret("test", randomly_initialize=True)

                    self.assertEqual(result, "random-secure-token")
                    mock_token_hex.assert_called_once_with(32)
                    mock_path.write_text.assert_called_once_with("random-secure-token")

    def test_get_secret_user_input(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("music_arena.secret._SECRETS_DIR") as mock_secrets_dir:
                with patch("builtins.input") as mock_input:
                    mock_path = mock_secrets_dir / "test.txt"
                    mock_path.exists.return_value = False
                    mock_path.write_text = unittest.mock.Mock()
                    mock_input.return_value = "user-input-secret"

                    result = get_secret("test")

                    self.assertEqual(result, "user-input-secret")
                    mock_input.assert_called_once_with("Enter secret for tag test: ")
                    mock_path.write_text.assert_called_once_with("user-input-secret")

    def test_get_secret_user_input_empty_raises_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("music_arena.secret._SECRETS_DIR") as mock_secrets_dir:
                with patch("builtins.input") as mock_input:
                    mock_path = mock_secrets_dir / "test.txt"
                    mock_path.exists.return_value = False
                    mock_input.return_value = ""

                    with self.assertRaises(ValueError) as cm:
                        get_secret("test")

                    self.assertEqual(str(cm.exception), "Secret for tag test not found")

    def test_get_secret_user_input_whitespace_only_raises_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("music_arena.secret._SECRETS_DIR") as mock_secrets_dir:
                with patch("builtins.input") as mock_input:
                    mock_path = mock_secrets_dir / "test.txt"
                    mock_path.exists.return_value = False
                    mock_input.return_value = "   "

                    with self.assertRaises(ValueError) as cm:
                        get_secret("test")

                    self.assertEqual(str(cm.exception), "Secret for tag test not found")

    def test_get_secret_file_not_created_when_exists(self):
        with patch("music_arena.secret._SECRETS_DIR") as mock_secrets_dir:
            mock_path = mock_secrets_dir / "test.txt"
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = "existing-secret"
            mock_path.write_text = unittest.mock.Mock()

            result = get_secret("test")

            self.assertEqual(result, "existing-secret")
            mock_path.write_text.assert_not_called()

    def test_get_secret_caching(self):
        with patch.dict(os.environ, {"MUSIC_ARENA_SECRET_TEST": "cached-secret"}):
            with patch("music_arena.secret._SECRETS_DIR") as mock_secrets_dir:
                mock_path = mock_secrets_dir / "test.txt"
                mock_path.exists.return_value = False
                mock_path.write_text = unittest.mock.Mock()

                # First call
                result1 = get_secret("test")
                # Second call with same tag
                result2 = get_secret("test")

                self.assertEqual(result1, "cached-secret")
                self.assertEqual(result2, "cached-secret")
                # File should only be written once due to caching
                mock_path.write_text.assert_called_once_with("cached-secret")

    def test_get_secret_different_tags_not_cached_together(self):
        with patch.dict(
            os.environ,
            {
                "MUSIC_ARENA_SECRET_TEST1": "secret1",
                "MUSIC_ARENA_SECRET_TEST2": "secret2",
            },
        ):
            with patch("music_arena.secret._SECRETS_DIR") as mock_secrets_dir:
                mock_path1 = unittest.mock.Mock()
                mock_path1.exists.return_value = False
                mock_path1.write_text = unittest.mock.Mock()

                mock_path2 = unittest.mock.Mock()
                mock_path2.exists.return_value = False
                mock_path2.write_text = unittest.mock.Mock()

                # Mock the __truediv__ operator to return different paths
                def mock_truediv(self, path):
                    if "test1.txt" in str(path):
                        return mock_path1
                    elif "test2.txt" in str(path):
                        return mock_path2
                    return mock_path1  # fallback

                mock_secrets_dir.__truediv__ = mock_truediv

                result1 = get_secret("test1")
                result2 = get_secret("test2")

                self.assertEqual(result1, "secret1")
                self.assertEqual(result2, "secret2")

    def test_get_secret_token_hex_generates_64_char_string(self):
        """Test that the cryptographically secure token is properly generated"""
        with patch.dict(os.environ, {}, clear=True):
            with patch("music_arena.secret._SECRETS_DIR") as mock_secrets_dir:
                mock_path = mock_secrets_dir / "test.txt"
                mock_path.exists.return_value = False
                mock_path.write_text = unittest.mock.Mock()

                # Don't mock token_hex, let it run to verify it produces correct output
                result = get_secret("test", randomly_initialize=True)

                # secrets.token_hex(32) should produce a 64-character hex string
                self.assertIsInstance(result, str)
                self.assertEqual(len(result), 64)
                # Should only contain hex characters
                self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_get_secret_priority_order(self):
        """Test that environment variable takes priority over file"""
        with patch.dict(os.environ, {"MUSIC_ARENA_SECRET_TEST": "env-priority"}):
            with patch("music_arena.secret._SECRETS_DIR") as mock_secrets_dir:
                mock_path = mock_secrets_dir / "test.txt"
                mock_path.exists.return_value = False  # File doesn't exist yet
                mock_path.read_text.return_value = "file-content"
                mock_path.write_text = unittest.mock.Mock()

                result = get_secret("test")

                # Should get env var, not file content
                self.assertEqual(result, "env-priority")
                # Should not read from file
                mock_path.read_text.assert_not_called()
                # Should write env var to file since file doesn't exist
                mock_path.write_text.assert_called_once_with("env-priority")


class TestSecretIntegration(unittest.TestCase):
    """Integration tests using actual temporary files"""

    def setUp(self):
        get_secret.cache_clear()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_secret_file_creation_and_reading(self):
        """Test actual file creation and reading without mocks"""
        with patch.dict(os.environ, {}, clear=True):
            with patch("music_arena.secret._SECRETS_DIR", self.temp_path):
                with patch("builtins.input", return_value="integration-test-secret"):
                    result = get_secret("integration")

                    self.assertEqual(result, "integration-test-secret")

                    # Verify file was created
                    secret_file = self.temp_path / "integration.txt"
                    self.assertTrue(secret_file.exists())
                    self.assertEqual(secret_file.read_text(), "integration-test-secret")

                    # Clear cache and test reading from file
                    get_secret.cache_clear()
                    result2 = get_secret("integration")
                    self.assertEqual(result2, "integration-test-secret")


if __name__ == "__main__":
    unittest.main()
