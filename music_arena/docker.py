import hashlib
import logging
import os
import pathlib
import subprocess
from typing import List, Optional

from .dataclass import SystemAccess, SystemKey
from .env import get_git_summary
from .path import (
    CACHE_DIR,
    COMPONENTS_DIR,
    CONTAINER_CACHE_DIR,
    CONTAINER_COMPONENTS_DIR,
    CONTAINER_IO_DIR,
    CONTAINER_LIB_DIR,
    CONTAINER_SYSTEMS_DIR,
    CONTAINER_SYSTEMS_PRIVATE_DIR,
    IO_DIR,
    LIB_DIR,
    REPO_DIR,
    SYSTEMS_DIR,
    SYSTEMS_PRIVATE_DIR,
)
from .registry import get_system_metadata
from .secret import get_secret, get_secret_var_name

DEFAULT_DOCKER_BASE = {
    SystemAccess.OPEN: "nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04",
    SystemAccess.PROPRIETARY: "python:3.10-slim",
}

_LOGGER = logging.getLogger(__name__)


def build_command(
    tag: str,
    dockerfile: pathlib.Path,
    *,
    context_dir: Optional[pathlib.Path] = None,
    build_args: dict[str, str] = {},
) -> List[str]:
    if context_dir is None:
        context_dir = REPO_DIR

    # Build the command with proper build args formatting
    cmd = [
        "docker",
        "build",
        "-t",
        tag,
        "-f",
        str(dockerfile.resolve()),
    ]

    # Add build args as separate arguments
    for k, v in build_args.items():
        cmd.extend(["--build-arg", f"{k}={v}"])

    cmd.append(str(context_dir.resolve()))
    return cmd


def run_command(
    tag: str,
    cmd: List[str] = [],
    *,
    name: Optional[str] = None,
    entrypoint: Optional[str] = None,
    gpu_id: Optional[str] = None,
    port_mapping: List[tuple[int, int]] = [],
    volume_mapping: List[tuple[pathlib.Path, pathlib.Path]] = [],
    env_vars: dict[str, str] = {},
    user_id: Optional[int] = None,
    run_as_current_user: bool = False,
    requires_host_mapping: bool = False,
) -> List[str]:
    command = ["docker", "run", "--rm"]

    # Name
    if name is not None:
        command.extend(["--name", name])

    # GPU
    if gpu_id is not None:
        command.extend(["--gpus", f"device={gpu_id}"])

    # User
    if run_as_current_user:
        user_id = os.getuid()
    if user_id is not None:
        command.extend(["--user", f"{user_id}"])

    # Port mapping
    for host_port, container_port in port_mapping:
        command.extend(["-p", f"{host_port}:{container_port}"])

    # Volume mapping
    for host_path, container_path in volume_mapping:
        command.extend(["-v", f"{host_path.resolve()}:{container_path}"])

    # Environment variables
    for var_name, var_value in env_vars.items():
        command.extend(["-e", f"{var_name}={var_value}"])

    # Network
    if requires_host_mapping:
        command.extend(["--add-host=host.docker.internal:host-gateway"])

    # Entrypoint
    if entrypoint is not None:
        command.extend(["--entrypoint", entrypoint])

    # Add docker tag
    command.append(tag)

    # Add command
    command.extend(cmd)

    return command


def kill_command(name: str) -> List[str]:
    return [
        "sh",
        "-c",
        f"'docker ps -q --filter name=\"^{name}$\" | grep -q . && {{ docker kill {name}; sleep 5; }} || true'",
    ]


def system_dockerfile(system_key: SystemKey) -> str:
    metadata = get_system_metadata(system_key)
    docker_base = metadata.docker_base
    if docker_base is None:
        docker_base = DEFAULT_DOCKER_BASE[metadata.access]
    module_name = metadata.module_name

    # Assemble Dockerfile from mixins
    mixin_dir = metadata.registry_dir / "Dockermixins"
    paths = [
        REPO_DIR / "Dockerfile",
        mixin_dir / f"{module_name}.Dockerfile",
        mixin_dir / f"{module_name}.{system_key.system_tag}.Dockerfile",
        mixin_dir
        / f"{module_name}.{system_key.system_tag}.{system_key.variant_tag}.Dockerfile",
    ]
    parts = []
    for path in paths:
        if path.exists():
            with open(path) as f:
                parts.append(f.read())
    assert (
        len(parts) > 0
    ), f"No Dockerfile found for {system_key.system_tag}.{system_key.variant_tag}"
    dockerfile = "\n\n".join(parts)

    # Replace base container
    lines = dockerfile.splitlines()
    assert lines[0].startswith("ARG BASE_CONTAINER")
    lines[0] = f'ARG BASE_CONTAINER="{docker_base}"'

    return "\n".join(lines)


def system_dockerfile_path(system_key: SystemKey) -> pathlib.Path:
    return (
        CACHE_DIR
        / "dockerfile"
        / f"{system_key.system_tag}.{system_key.variant_tag}.Dockerfile"
    )


def system_port(system_key: SystemKey) -> int:
    key = f"{system_key.system_tag}.{system_key.variant_tag}".encode("utf-8")
    hash_bytes = hashlib.sha256(key).digest()[:8]
    hash_val = int.from_bytes(hash_bytes, byteorder="big", signed=False)
    return 15000 + hash_val % 10000


def system_write_dockerfile(
    system_key: SystemKey, dockerfile_path: Optional[pathlib.Path] = None
) -> pathlib.Path:
    if dockerfile_path is None:
        dockerfile_path = system_dockerfile_path(system_key)
    dockerfile_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dockerfile_path, "w") as f:
        f.write(system_dockerfile(system_key))
    return dockerfile_path


def system_docker_tag(system_key: SystemKey) -> str:
    return f"music-arena-sys-{system_key.system_tag}-{system_key.variant_tag}"


def system_build_command(
    system_key: SystemKey, dockerfile_path: Optional[pathlib.Path] = None
) -> List[str]:
    if dockerfile_path is None:
        dockerfile_path = system_dockerfile_path(system_key)

    # Get system metadata
    metadata = get_system_metadata(system_key)

    # Create build_args
    build_args = {}
    for secret in metadata.secrets:
        build_args[get_secret_var_name(secret)] = get_secret(secret)

    # Build command
    return build_command(
        tag=system_docker_tag(system_key),
        dockerfile=dockerfile_path,
        context_dir=REPO_DIR,
        build_args=build_args,
    )


def system_run_command(
    system_key: SystemKey,
    cmd: List[str] = [],
    *,
    name_suffix: Optional[str] = "",
    port_mapping: Optional[List[tuple[int, int]]] = None,
    gpu_id: Optional[str] = None,
) -> List[str]:
    metadata = get_system_metadata(system_key)
    if metadata.requires_gpu and gpu_id is None:
        raise ValueError("GPU ID is required for systems that require GPU")
    volume_mapping = [
        (LIB_DIR, CONTAINER_LIB_DIR),
        (CACHE_DIR, CONTAINER_CACHE_DIR),
        (SYSTEMS_DIR, CONTAINER_SYSTEMS_DIR),
        (IO_DIR, CONTAINER_IO_DIR),
    ]
    if SYSTEMS_PRIVATE_DIR.is_dir():
        volume_mapping.append((SYSTEMS_PRIVATE_DIR, CONTAINER_SYSTEMS_PRIVATE_DIR))
    return run_command(
        tag=system_docker_tag(system_key),
        cmd=cmd,
        name=system_docker_tag(system_key) + name_suffix,
        gpu_id=gpu_id,
        port_mapping=port_mapping,
        volume_mapping=volume_mapping,
        env_vars={
            "MUSIC_ARENA_CONTAINER_HOST_GIT_HASH": get_git_summary(),
            "MUSIC_ARENA_CONTAINER_COMPONENT": "system",
            "MUSIC_ARENA_CONTAINER_SYSTEM_TAG": system_key.system_tag,
            "MUSIC_ARENA_CONTAINER_VARIANT_TAG": system_key.variant_tag,
        },
    )


def system_kill_command(
    system_key: SystemKey, name_suffix: Optional[str] = ""
) -> List[str]:
    return kill_command(system_docker_tag(system_key) + name_suffix)


def system_execute_command(
    system_key: SystemKey,
    cmd: List[str] = [],
    *,
    name_suffix: Optional[str] = "",
    skip_kill: bool = False,
    skip_build: bool = False,
    gpu_id: Optional[str] = None,
    port_mapping: List[tuple[int, int]] = [],
) -> None:
    tag = system_docker_tag(system_key)
    if not skip_build:
        # Write Dockerfile
        dockerfile_path = system_dockerfile_path(system_key)
        _LOGGER.info(f"Writing Dockerfile to {dockerfile_path}...")
        system_write_dockerfile(system_key, dockerfile_path)
        _LOGGER.info(f"Dockerfile:\n```\n{dockerfile_path.read_text()}\n```")

        # Build container
        build_cmd = system_build_command(system_key, dockerfile_path)
        _LOGGER.info(f"Building container {tag} from {dockerfile_path} via:")
        _LOGGER.info(" ".join(build_cmd))
        subprocess.run(build_cmd, check=True)
        _LOGGER.info(f"Container {tag} built successfully.")

    # Run command
    if len(cmd) > 0:
        if not skip_kill:
            kill_cmd = system_kill_command(system_key, name_suffix=name_suffix)
            _LOGGER.info(f"Killing container {tag} via:")
            _LOGGER.info(" ".join(kill_cmd))
            subprocess.run(kill_cmd)
            _LOGGER.info(f"Container {tag} killed successfully.")

        run_cmd = system_run_command(
            system_key,
            cmd,
            name_suffix=name_suffix,
            gpu_id=gpu_id,
            port_mapping=port_mapping,
        )
        _LOGGER.info(f"Running command in container {tag}:")
        _LOGGER.info(" ".join(run_cmd))
        subprocess.run(run_cmd)


def base_build_command(dockerfile_path: Optional[pathlib.Path] = None) -> List[str]:
    if dockerfile_path is None:
        dockerfile_path = REPO_DIR / "Dockerfile"
    return build_command(
        tag="music-arena-base",
        dockerfile=dockerfile_path,
        context_dir=REPO_DIR,
    )


def component_dockerfile_path(component_name: str) -> pathlib.Path:
    return COMPONENTS_DIR / component_name / "Dockerfile"


def component_docker_tag(component_name: str) -> str:
    return f"music-arena-comp-{component_name}"


def component_build_command(
    component_name: str,
    dockerfile_path: Optional[pathlib.Path] = None,
) -> List[str]:
    if dockerfile_path is None:
        dockerfile_path = component_dockerfile_path(component_name)
    return build_command(
        tag=component_docker_tag(component_name),
        dockerfile=dockerfile_path,
        context_dir=COMPONENTS_DIR / component_name,
    )


def component_run_command(
    component_name: str,
    cmd: List[str] = [],
    *,
    name_suffix: Optional[str] = "",
    env_vars: dict[str, str] = {},
    entrypoint: Optional[str] = None,
    port_mapping: List[tuple[int, int]] = [],
    requires_host_mapping: bool = False,
) -> None:
    volume_mapping = [
        (LIB_DIR, CONTAINER_LIB_DIR),
        (CACHE_DIR, CONTAINER_CACHE_DIR),
        (SYSTEMS_DIR, CONTAINER_SYSTEMS_DIR),
        (
            COMPONENTS_DIR / component_name,
            CONTAINER_COMPONENTS_DIR / component_name,
        ),
        (IO_DIR, CONTAINER_IO_DIR),
        (REPO_DIR / "leaderboard/outputs", pathlib.Path("/music-arena/leaderboard/outputs")),
    ]
    if SYSTEMS_PRIVATE_DIR.is_dir():
        volume_mapping.append((SYSTEMS_PRIVATE_DIR, CONTAINER_SYSTEMS_PRIVATE_DIR))
    return run_command(
        tag=component_docker_tag(component_name),
        cmd=cmd,
        name=component_docker_tag(component_name) + name_suffix,
        entrypoint=entrypoint,
        port_mapping=port_mapping,
        volume_mapping=volume_mapping,
        env_vars={
            "MUSIC_ARENA_CONTAINER_HOST_GIT_HASH": get_git_summary(),
            "MUSIC_ARENA_CONTAINER_COMPONENT": component_name,
            **env_vars,
        },
        requires_host_mapping=requires_host_mapping,
    )


def component_kill_command(
    component_name: str, name_suffix: Optional[str] = ""
) -> List[str]:
    return kill_command(component_docker_tag(component_name) + name_suffix)


def component_execute_command(
    component_name: str,
    cmd: List[str] = [],
    *,
    name_suffix: Optional[str] = "",
    skip_kill: bool = False,
    skip_build: bool = False,
    **kwargs,
) -> None:
    tag = component_docker_tag(component_name)
    if not skip_build:
        # Build base container
        base_build_cmd = base_build_command()
        _LOGGER.info(f"Building base container via:")
        _LOGGER.info(" ".join(base_build_cmd))
        subprocess.run(base_build_cmd, check=True)
        _LOGGER.info(f"Base container built successfully.")

        # Build container
        build_cmd = component_build_command(component_name)
        _LOGGER.info(f"Building component container {tag} via:")
        _LOGGER.info(" ".join(build_cmd))
        subprocess.run(build_cmd, check=True)
        _LOGGER.info(f"Container {tag} built successfully.")

    # Kill container
    if not skip_kill:
        kill_cmd = component_kill_command(component_name, name_suffix=name_suffix)
        _LOGGER.info(f"Killing container {tag} via:")
        _LOGGER.info(" ".join(kill_cmd))
        subprocess.run(kill_cmd)
        _LOGGER.info(f"Container {tag} killed successfully.")

    # Run command
    run_cmd = component_run_command(
        component_name=component_name,
        cmd=cmd,
        name_suffix=name_suffix,
        **kwargs,
    )
    _LOGGER.info(f"Running command in container {tag}:")
    _LOGGER.info(" ".join(run_cmd))
    subprocess.run(run_cmd)
