import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ..dataclass import SystemKey
from ..docker import (
    base_build_command,
    component_build_command,
    component_kill_command,
    component_run_command,
    system_build_command,
    system_dockerfile_path,
    system_kill_command,
    system_port,
    system_run_command,
    system_write_dockerfile,
)
from ..env import EXECUTING_IN_CONTAINER
from ..path import REPO_DIR
from ..secret import get_secret_json

CONFIGS_DIR = REPO_DIR / "deploy"


@dataclass
class Command:
    command: str | list[str] | list[list[str]]
    comment: Optional[str] = None
    dir: Optional[Path] = None


def _args_to_cmd(args: dict[str, Any]) -> list[str]:
    cmd = []
    for key, value in args.items():
        if isinstance(value, bool) and value:
            cmd.append(f"--{key}")
        else:
            cmd.append(f"--{key}")
            cmd.append(str(value))
    return cmd


def parse_deployment_config(config_path: Path):
    """Load deployment configuration from yaml file."""
    with open(config_path, "r") as f:
        result = yaml.safe_load(f)
    return result


def get_frontend_commands(config: Dict[str, Any], config_name: str) -> List[Command]:
    """Generate frontend deployment commands."""
    component = "frontend"
    commands = []
    frontend_config = config.get("components", {}).get(component, {})
    if not frontend_config.get("enabled", False):
        return commands

    # Build command
    cmd = frontend_config.get("cmd", []) + _args_to_cmd(frontend_config.get("args", {}))

    # Hostname
    host = frontend_config.get("host", "0.0.0.0")
    cmd.extend(["--host", host])

    # Port
    port = frontend_config.get("port", 8080)
    port_mapping = [(port, port)]
    cmd.extend(["--port", str(port)])

    if "fly.io" in host:
        raise NotImplementedError("Fly.io deployment not implemented yet")
    elif host == "0.0.0.0":
        commands.append(
            Command(
                command=[
                    base_build_command(),
                    component_build_command(component),
                    component_kill_command(component, name_suffix=config_name),
                    component_run_command(
                        component,
                        cmd=cmd,
                        name_suffix=config_name,
                        env_vars=frontend_config.get("vars", {}),
                        port_mapping=port_mapping,
                        requires_host_mapping=True,
                    ),
                ],
                comment=f"Kill, build and run {component}",
            )
        )
    else:
        raise NotImplementedError(f"Deployment to {host} not implemented yet")

    return commands


def get_gateway_commands(config: Dict[str, Any], config_name: str) -> List[Command]:
    """Generate mock gateway deployment commands."""
    component = "gateway"
    commands = []
    gateway_config = config.get("components", {}).get(component, {})
    if not gateway_config.get("enabled", False):
        return commands

    # Build command
    args = gateway_config.get("args", {})
    cmd = gateway_config.get("cmd", []) + _args_to_cmd(args)

    # Hostname
    host = gateway_config.get("host", "0.0.0.0")
    cmd.extend(["--host", host])

    # Port
    port = gateway_config.get("port", 8080)
    port_mapping = [(port, port)]
    cmd.extend(["--port", str(port)])

    # Build systems args
    systems = []
    for system_key_str, system_config in config.get("systems", {}).items():
        if "port" in system_config:
            systems.append(f"{system_key_str}:{system_config['port']}")
        else:
            systems.append(system_key_str)
    cmd.extend(["--systems", ",".join(systems)])

    # Build weights args
    weights = []
    for pair, weight in config.get("weights", {}).items():
        weights.append(f"{pair}/{weight}")
    if len(weights) > 0:
        cmd.extend(["--weights", ",".join(weights)])

    # Secrets
    if "bucket_metadata" in args or "bucket_audio" in args:
        get_secret_json("GCP_BUCKET_SERVICE_ACCOUNT")

    # Build command
    commands.append(
        Command(
            command=[
                base_build_command(),
                component_build_command(component),
                component_kill_command(component, name_suffix=config_name),
                component_run_command(
                    component,
                    cmd=cmd,
                    name_suffix=config_name,
                    env_vars=gateway_config.get("vars", {}),
                    port_mapping=port_mapping,
                    requires_host_mapping=True,
                ),
            ],
            comment=f"Kill, build and run {component}",
        )
    )
    return commands


def get_systems_commands(config: Dict[str, Any], config_name: str) -> List[Command]:
    """Generate systems deployment commands."""
    commands = []
    systems_config = config.get("systems", [])

    for system_key_str, system_config in systems_config.items():
        system_key = SystemKey.from_string(system_key_str)
        args_cmd = _args_to_cmd(system_config.get("args", {}))
        port = system_config.get("port", system_port(system_key))
        port_mapping = [(port, port)]
        args_cmd += ["--port", str(port)]

        # Write dockerfile
        dockerfile_path = system_dockerfile_path(system_key)
        system_write_dockerfile(system_key, dockerfile_path)

        # Build command
        commands.append(
            Command(
                command=[
                    system_build_command(system_key),
                    system_kill_command(system_key, name_suffix=config_name),
                    system_run_command(
                        system_key=system_key,
                        cmd=["python", "-m", "music_arena.cli.system-serve"] + args_cmd,
                        name_suffix=config_name,
                        gpu_id=system_config.get("gpu", None),
                        port_mapping=port_mapping,
                    ),
                ],
                comment=f"Kill, build and run {system_key}",
            )
        )
    return commands


def get_deployment_commands(
    config_path: Path, component: Optional[str] = None, config_name: str = ""
) -> List[Command]:
    """Parse yaml config and return list of deployment commands."""
    config = parse_deployment_config(config_path)
    config_name = f"-{config_path.stem}"
    commands = []
    if component is None or component.startswith("s"):
        commands.extend(get_systems_commands(config, config_name))
    if component is None or component.startswith("g"):
        commands.extend(get_gateway_commands(config, config_name))
    if component is None or component.startswith("f"):
        commands.extend(get_frontend_commands(config, config_name))
    return commands


def generate_tmux_script(config_path: Path, commands: List[Command]) -> str:
    """Generate tmux script with directory navigation."""
    session_name = f"MUSIC-ARENA-{config_path.stem.upper()}"

    script_lines = [
        "#!/bin/bash",
        "set -e",
        f"# Generated deployment script for {config_path.stem}",
        "",
        f'SESSION_NAME="{session_name}"',
        "",
        "# Kill existing session if it exists",
        'tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true',
        "",
        "# Create new tmux session",
        'tmux new-session -d -s "$SESSION_NAME"',
        "",
        "# Launch services",
    ]

    for i, cmd_obj in enumerate(commands):
        # Build the command string based on the command type
        if isinstance(cmd_obj.command, str):
            cmd_str = cmd_obj.command
        elif isinstance(cmd_obj.command, list):
            if len(cmd_obj.command) == 0:
                cmd_str = ""
            else:
                if isinstance(cmd_obj.command[0], list):
                    # list[list[str]] - execute commands one after the other
                    cmd_str = " && ".join([" ".join(cmd) for cmd in cmd_obj.command])
                else:
                    # list[str] - single command
                    cmd_str = " ".join(cmd_obj.command)
        else:
            raise ValueError(f"Invalid command type: {type(cmd_obj.command)}")

        # Add directory navigation if specified
        if cmd_obj.dir:
            full_command = f"pushd {cmd_obj.dir} && {cmd_str} && popd"
        else:
            full_command = cmd_str

        if i == 0:
            # First command runs in the initial window
            script_lines.append(
                f'tmux send-keys -t "$SESSION_NAME":0 "{full_command}" Enter'
            )
        else:
            # Subsequent commands create new windows
            script_lines.extend(
                [
                    f'tmux new-window -t "$SESSION_NAME"',
                    f'tmux send-keys -t "$SESSION_NAME":{i} "{full_command}" Enter',
                ]
            )

    script_lines.extend(
        [
            "",
            "# Session created successfully!",
            'echo "Tmux session \\"$SESSION_NAME\\" created successfully!"',
            'echo "To attach to the session, run: tmux attach-session -t \\"$SESSION_NAME\\""',
            'echo "To list all sessions, run: tmux list-sessions"',
            'echo "To kill the session, run: tmux kill-session -t \\"$SESSION_NAME\\""',
            "",
            "# Try to attach if we have a terminal available",
            "if [ -t 0 ]; then",
            '    echo "Attaching to session..."',
            '    tmux attach-session -t "$SESSION_NAME"',
            "else",
            '    echo "No terminal available for auto-attach. Use the commands above to attach manually."',
            "fi",
        ]
    )

    return "\n".join(script_lines)


def generate_basic_script(config_path: Path, commands: List[Command]) -> str:
    """Generate basic script output with directory navigation."""
    script_lines = [f"# Deployment commands for {config_path.stem}", "", "set -e", ""]

    for cmd in commands:
        if cmd.comment:
            script_lines.append(f"# {cmd.comment}")
        if cmd.dir:
            script_lines.append(f"pushd {cmd.dir}")
        if isinstance(cmd.command, str):
            cmd_str = cmd.command
        elif isinstance(cmd.command, list):
            if len(cmd.command) == 0:
                cmd_str = ""
            else:
                if isinstance(cmd.command[0], list):
                    cmd_str = " && ".join([" ".join(cmd) for cmd in cmd.command])
                else:
                    cmd_str = " ".join(cmd.command)
        else:
            raise ValueError(f"Invalid command type: {type(cmd.command)}")
        script_lines.append(cmd_str)
        if cmd.dir:
            script_lines.append("popd")

    return "\n".join(script_lines)


def generate_deployment_script(
    config_path: Path, component: Optional[str] = None, tmux: bool = False
) -> str:
    """Generate complete deployment script."""
    commands = get_deployment_commands(config_path, component)
    if tmux:
        return generate_tmux_script(config_path, commands)
    else:
        return generate_basic_script(config_path, commands)


def main():
    if EXECUTING_IN_CONTAINER:
        raise RuntimeError("This is intended to be run on the host")

    parser = argparse.ArgumentParser(
        description="Generate deployment script for Music Arena"
    )
    parser.add_argument("deployment_tag", help="Deployment tag (e.g., dev, prod)")
    parser.add_argument(
        "-c",
        "--component",
        help="Component to deploy (e.g., frontend, gateway, open-weights)",
    )
    parser.add_argument(
        "--tmux",
        action="store_true",
        help="Wrap commands in tmux session management (default: just print commands)",
    )

    args = parser.parse_args()

    deployment_tag = args.deployment_tag
    config_paths = [
        p.resolve()
        for p in CONFIGS_DIR.glob("*.yaml")
        if p.stem.startswith(deployment_tag)
    ]
    if len(config_paths) == 0:
        raise FileNotFoundError(
            f"Configuration file starting with {deployment_tag} not found"
        )
    elif len(config_paths) != 1:
        raise ValueError(f"Multiple configuration files starting with {deployment_tag}")
    config_path = config_paths[0]

    print(generate_deployment_script(config_path, args.component, args.tmux))


if __name__ == "__main__":
    main()
