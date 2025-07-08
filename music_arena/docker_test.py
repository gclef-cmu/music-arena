import pathlib
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from .dataclass import SystemAccess, SystemKey
from .docker import (
    DEFAULT_DOCKER_BASE,
    build_command,
    run_command,
    system_build_command,
    system_docker_tag,
    system_dockerfile,
    system_dockerfile_path,
    system_execute_command,
    system_port,
    system_run_command,
    system_write_dockerfile,
)
from .registry import get_registered_systems


class DockerTest(unittest.TestCase):
    def test_build_command_basic(self):
        """Test basic docker build command generation."""
        dockerfile = pathlib.Path("/path/to/Dockerfile")
        result = build_command("test-tag", dockerfile)
        expected = [
            "docker",
            "build",
            "-t",
            "test-tag",
            "-f",
            str(dockerfile.resolve()),
        ]
        # The last element should be the context directory (resolved REPO_DIR)
        self.assertEqual(result[:-1], expected)
        self.assertTrue(result[-1].endswith("music-arena"))

    def test_build_command_with_context_and_args(self):
        """Test docker build command with custom context and build args."""
        dockerfile = pathlib.Path("/path/to/Dockerfile")
        context_dir = pathlib.Path("/custom/context")
        build_args = {"ARG1": "value1", "ARG2": "value2"}

        result = build_command(
            "test-tag", dockerfile, context_dir=context_dir, build_args=build_args
        )

        self.assertIn("docker", result)
        self.assertIn("build", result)
        self.assertIn("-t", result)
        self.assertIn("test-tag", result)
        self.assertIn("-f", result)
        self.assertIn(str(dockerfile.resolve()), result)
        self.assertIn("--build-arg", result)
        self.assertIn("ARG1=value1", result)
        self.assertIn("ARG2=value2", result)
        self.assertEqual(result[-1], str(context_dir.resolve()))

    def test_run_command_basic(self):
        """Test basic docker run command generation."""
        result = run_command("test-tag")
        expected = ["docker", "run", "--rm", "test-tag"]
        self.assertEqual(result, expected)

    def test_run_command_with_gpu(self):
        """Test docker run command with GPU."""
        result = run_command("test-tag", gpu_id="0")
        self.assertIn("--gpus", result)
        self.assertIn("device=0", result)

    @patch("os.getuid", return_value=1000)
    def test_run_command_with_user(self, mock_getuid):
        """Test docker run command with user options."""
        # Test with explicit user_id
        result = run_command("test-tag", user_id=500)
        self.assertIn("--user", result)
        self.assertIn("500", result)

        # Test with run_as_current_user
        result = run_command("test-tag", run_as_current_user=True)
        self.assertIn("--user", result)
        self.assertIn("1000", result)

    def test_run_command_with_port_mapping(self):
        """Test docker run command with port mapping."""
        port_mapping = [(8080, 80), (9000, 9000)]
        result = run_command("test-tag", port_mapping=port_mapping)

        self.assertIn("-p", result)
        self.assertIn("8080:80", result)
        self.assertIn("9000:9000", result)

    def test_run_command_with_volume_mapping(self):
        """Test docker run command with volume mapping."""
        host_path = pathlib.Path("/host/path")
        container_path = pathlib.Path("/container/path")
        volume_mapping = [(host_path, container_path)]

        result = run_command("test-tag", volume_mapping=volume_mapping)

        self.assertIn("-v", result)
        self.assertIn(f"{host_path.resolve()}:{container_path}", result)

    def test_run_command_with_env_vars(self):
        """Test docker run command with environment variables."""
        env_vars = {"VAR1": "value1", "VAR2": "value2"}
        result = run_command("test-tag", env_vars=env_vars)

        self.assertIn("-e", result)
        self.assertIn("VAR1=value1", result)
        self.assertIn("VAR2=value2", result)

    def test_run_command_with_host_mapping(self):
        """Test docker run command with host mapping."""
        result = run_command("test-tag", requires_host_mapping=True)

        self.assertIn("--add-host=host.docker.internal:host-gateway", result)

    def test_run_command_with_cmd(self):
        """Test docker run command with custom command."""
        cmd = ["python", "script.py", "--arg", "value"]
        result = run_command("test-tag", cmd=cmd)

        # Check that the command is appended at the end
        self.assertEqual(result[-4:], cmd)

    @patch("music_arena.docker.get_system_metadata")
    @patch("music_arena.docker.SYSTEMS_DIR", pathlib.Path("/fake/systems"))
    @patch("music_arena.docker.REPO_DIR", pathlib.Path("/fake/repo"))
    def test_system_dockerfile(self, mock_get_metadata):
        """Test system dockerfile generation."""
        # Mock system metadata
        mock_metadata = MagicMock()
        mock_metadata.docker_base = None
        mock_metadata.access = SystemAccess.OPEN
        mock_metadata.module_name = "test_module"
        mock_get_metadata.return_value = mock_metadata

        # Create temporary files to simulate Dockerfile mixins
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)

            # Create fake repo Dockerfile
            repo_dockerfile = tmp_path / "Dockerfile"
            repo_dockerfile.write_text(
                "ARG BASE_CONTAINER\nFROM ${BASE_CONTAINER}\nRUN echo 'base'"
            )

            # Create fake mixin directory and files
            mixin_dir = tmp_path / "systems" / "Dockermixins"
            mixin_dir.mkdir(parents=True)

            module_dockerfile = mixin_dir / "test_module.Dockerfile"
            module_dockerfile.write_text("RUN echo 'module'")

            # Patch the paths
            with (
                patch("music_arena.docker.REPO_DIR", tmp_path),
                patch("music_arena.docker.SYSTEMS_DIR", tmp_path / "systems"),
            ):
                system_key = SystemKey(
                    system_tag="test_system", variant_tag="test_variant"
                )
                result = system_dockerfile(system_key)

                # Check that it contains expected content
                self.assertIn(
                    f'ARG BASE_CONTAINER="{DEFAULT_DOCKER_BASE[SystemAccess.OPEN]}"',
                    result,
                )
                self.assertIn("RUN echo 'base'", result)
                self.assertIn("RUN echo 'module'", result)

    def test_system_dockerfile_path(self):
        """Test system dockerfile path generation."""
        system_key = SystemKey(system_tag="test_system", variant_tag="test_variant")
        result = system_dockerfile_path(system_key)

        self.assertTrue(
            str(result).endswith("dockerfile/test_system.test_variant.Dockerfile")
        )

    def test_system_port(self):
        """Test system port generation."""
        systems = get_registered_systems()
        self.assertGreater(len(systems), 0)
        ports = set()
        for system_key in systems.keys():
            port = system_port(system_key)
            ports.add(port)
            self.assertGreaterEqual(port, 15000)
            self.assertLess(port, 25000)
        self.assertEqual(len(ports), len(systems))
        test_key = SystemKey(system_tag="foo", variant_tag="bar")
        self.assertEqual(system_port(test_key), 19079)

    def test_system_port_reproducible(self):
        """Test that system_port is reproducible across calls."""
        system_key = SystemKey(system_tag="test_system", variant_tag="test_variant")
        port1 = system_port(system_key)
        port2 = system_port(system_key)
        self.assertEqual(port1, port2)

    @patch("music_arena.docker.system_dockerfile")
    def test_system_write_dockerfile(self, mock_dockerfile):
        """Test writing system dockerfile to disk."""
        mock_dockerfile.return_value = "FAKE DOCKERFILE CONTENT"

        with tempfile.TemporaryDirectory() as tmp_dir:
            dockerfile_path = pathlib.Path(tmp_dir) / "test.Dockerfile"
            system_key = SystemKey(system_tag="test_system", variant_tag="test_variant")

            result = system_write_dockerfile(system_key, dockerfile_path)

            self.assertEqual(result, dockerfile_path)
            self.assertTrue(dockerfile_path.exists())
            self.assertEqual(dockerfile_path.read_text(), "FAKE DOCKERFILE CONTENT")

    def test_system_docker_tag(self):
        """Test system docker tag generation."""
        system_key = SystemKey(system_tag="test_system", variant_tag="test_variant")
        result = system_docker_tag(system_key)
        expected = "music-arena-sys-test_system-test_variant"
        self.assertEqual(result, expected)

    @patch("music_arena.docker.get_system_metadata")
    @patch("music_arena.docker.get_secret")
    @patch("music_arena.docker.get_secret_var_name")
    @patch("music_arena.docker.system_dockerfile_path")
    @patch("music_arena.docker.build_command")
    def test_system_build_command(
        self,
        mock_build_command,
        mock_dockerfile_path,
        mock_get_secret_var_name,
        mock_get_secret,
        mock_get_metadata,
    ):
        """Test system build command generation."""
        # Mock dependencies
        mock_metadata = MagicMock()
        mock_metadata.secrets = ["SECRET1", "SECRET2"]
        mock_get_metadata.return_value = mock_metadata

        mock_get_secret_var_name.side_effect = lambda x: f"{x}_VAR"
        mock_get_secret.side_effect = lambda x: f"secret_value_{x}"

        dockerfile_path = pathlib.Path("/fake/dockerfile")
        mock_dockerfile_path.return_value = dockerfile_path

        mock_build_command.return_value = ["docker", "build", "..."]

        system_key = SystemKey(system_tag="test_system", variant_tag="test_variant")
        result = system_build_command(system_key)

        # Verify build_command was called with correct arguments
        mock_build_command.assert_called_once()
        args, kwargs = mock_build_command.call_args

        self.assertEqual(
            kwargs["tag"], "music-arena-sys-test_system-test_variant"
        )  # tag
        self.assertEqual(kwargs["dockerfile"], dockerfile_path)  # dockerfile path
        self.assertIn("context_dir", kwargs)
        self.assertIn("build_args", kwargs)

        # Check build_args contain secrets
        build_args = kwargs["build_args"]
        self.assertEqual(build_args["SECRET1_VAR"], "secret_value_SECRET1")
        self.assertEqual(build_args["SECRET2_VAR"], "secret_value_SECRET2")

    @patch("music_arena.docker.get_system_metadata")
    @patch("music_arena.docker.run_command")
    def test_system_run_command(self, mock_run_command, mock_get_metadata):
        """Test system run command generation."""
        # Mock metadata
        mock_metadata = MagicMock()
        mock_metadata.requires_gpu = False
        mock_get_metadata.return_value = mock_metadata

        mock_run_command.return_value = ["docker", "run", "..."]

        system_key = SystemKey(system_tag="test_system", variant_tag="test_variant")
        cmd = ["python", "test.py"]
        result = system_run_command(system_key, cmd=cmd)

        # Verify run_command was called
        mock_run_command.assert_called_once()
        args, kwargs = mock_run_command.call_args

        self.assertEqual(
            kwargs["tag"], "music-arena-sys-test_system-test_variant"
        )  # tag
        self.assertEqual(kwargs["cmd"], cmd)

        # Check environment variables
        env_vars = kwargs["env_vars"]
        self.assertEqual(env_vars["MUSIC_ARENA_CONTAINER_COMPONENT"], "system")
        self.assertEqual(env_vars["MUSIC_ARENA_CONTAINER_SYSTEM_TAG"], "test_system")
        self.assertEqual(env_vars["MUSIC_ARENA_CONTAINER_VARIANT_TAG"], "test_variant")
        self.assertIn("MUSIC_ARENA_CONTAINER_HOST_GIT_HASH", env_vars)

        # Check volume mappings are present
        self.assertIn("volume_mapping", kwargs)
        self.assertGreater(len(kwargs["volume_mapping"]), 0)

    @patch("music_arena.docker.get_system_metadata")
    def test_system_run_command_gpu_required_error(self, mock_get_metadata):
        """Test system run command raises error when GPU required but not provided."""
        mock_metadata = MagicMock()
        mock_metadata.requires_gpu = True
        mock_get_metadata.return_value = mock_metadata

        system_key = SystemKey(system_tag="test_system", variant_tag="test_variant")
        with self.assertRaises(ValueError) as cm:
            system_run_command(system_key)

        self.assertIn("GPU ID is required", str(cm.exception))

    @patch("music_arena.docker.system_write_dockerfile")
    @patch("music_arena.docker.system_build_command")
    @patch("music_arena.docker.system_run_command")
    @patch("music_arena.docker.subprocess.run")
    def test_system_execute_command_with_build(
        self,
        mock_subprocess_run,
        mock_system_run_command,
        mock_system_build_command,
        mock_system_write_dockerfile,
    ):
        """Test system execute command with build step."""
        # Mock return values
        dockerfile_path = pathlib.Path("/fake/dockerfile")
        mock_system_write_dockerfile.return_value = dockerfile_path
        mock_system_build_command.return_value = ["docker", "build", "..."]
        mock_system_run_command.return_value = ["docker", "run", "..."]

        system_key = SystemKey(system_tag="test_system", variant_tag="test_variant")
        # Mock file reading for logging
        with patch.object(pathlib.Path, "read_text", return_value="FAKE DOCKERFILE"):
            system_execute_command(system_key, cmd=["python", "test.py"])

        # Verify all steps were called
        mock_system_write_dockerfile.assert_called_once()
        mock_system_build_command.assert_called_once()
        mock_system_run_command.assert_called_once()

        # Verify subprocess.run was called three times (build + kill + run)
        self.assertEqual(mock_subprocess_run.call_count, 3)

    @patch("music_arena.docker.system_run_command")
    @patch("music_arena.docker.subprocess.run")
    def test_system_execute_command_skip_build(
        self, mock_subprocess_run, mock_system_run_command
    ):
        """Test system execute command with build skipped."""
        mock_system_run_command.return_value = ["docker", "run", "..."]

        system_key = SystemKey(system_tag="test_system", variant_tag="test_variant")
        system_execute_command(system_key, cmd=["python", "test.py"], skip_build=True)

        # Only run command should be executed
        mock_system_run_command.assert_called_once()
        # subprocess.run called twice (kill + run)
        self.assertEqual(mock_subprocess_run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
