import argparse
import logging

from ..dataclass import SystemKey
from ..docker import system_execute_command, system_port


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("system_key", type=str)
    parser.add_argument("-s", "--skip_build", action="store_true")
    parser.add_argument("-g", "--gpu_id", type=str)
    parser.add_argument("-p", "--port", type=int)
    parser.add_argument("cmd", type=str)
    args, unknown_args = parser.parse_known_args()

    logging.basicConfig(level=logging.INFO)

    # Parse command
    system_key = SystemKey.from_string(args.system_key)
    cmd_name = args.cmd
    port_mapping = []
    if cmd_name == "build":
        cmd = []
    elif cmd_name == "generate":
        cmd = ["python", "-m", "music_arena.cli.system-generate"] + unknown_args
    elif cmd_name == "serve":
        if args.port is not None:
            host_port = args.port
            container_port = host_port
        else:
            host_port = system_port(system_key)
            container_port = 8080
        port_mapping = [(host_port, container_port)]
        cmd = [
            "python",
            "-m",
            "music_arena.cli.system-serve",
            "--port",
            str(container_port),
        ] + unknown_args
    else:
        # For any other command, pass it along with the unknown args
        cmd = [cmd_name] + unknown_args

    system_execute_command(
        system_key=system_key,
        cmd=cmd,
        skip_build=args.skip_build,
        gpu_id=args.gpu_id,
        port_mapping=port_mapping,
    )


if __name__ == "__main__":
    main()
