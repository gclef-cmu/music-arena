import argparse
import logging

from ..docker import component_execute_command


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("component_name", type=str)
    parser.add_argument("-e", "--entrypoint")
    parser.add_argument("-s", "--skip_build", action="store_true")
    parser.add_argument("-p", "--port", type=int, default=8080)
    parser.add_argument("cmd", type=str, nargs="*")
    args, unknown_args = parser.parse_known_args()

    logging.basicConfig(level=logging.INFO)

    port_mapping = []
    requires_host_mapping = False
    if args.component_name == "gateway":
        port_mapping = [(args.port, 8080)]
        requires_host_mapping = True

    component_execute_command(
        component_name=args.component_name,
        cmd=args.cmd + unknown_args,
        entrypoint=args.entrypoint,
        skip_build=args.skip_build,
        port_mapping=port_mapping,
        requires_host_mapping=requires_host_mapping,
    )


if __name__ == "__main__":
    main()
