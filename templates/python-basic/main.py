import os
import sys


def cmd_hello(args: list[str]) -> int:
    name = args[0] if args else "world"
    print(f"Hello, {name}!")
    print(f"config: {os.environ['CPTOOLS_PLUGIN_CONFIG_DIR']}")
    print(f"data:   {os.environ['CPTOOLS_PLUGIN_DATA_DIR']}")
    print(f"cache:  {os.environ['CPTOOLS_PLUGIN_CACHE_DIR']}")
    return 0


COMMANDS = {"hello": cmd_hello}


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"usage: main.py <{'|'.join(COMMANDS)}>", file=sys.stderr)
        sys.exit(2)
    sys.exit(COMMANDS[sys.argv[1]](sys.argv[2:]))