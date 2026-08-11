import argparse

from . import core


def _parser():
    parser = argparse.ArgumentParser(prog="updb")
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="apply all pending migrations without confirmation prompts",
    )
    parser.add_argument(
        "--no-write-migrations",
        action="store_true",
        help="do not modify migrations.sql",
    )
    parser.add_argument("command", nargs="?", choices=("apply", "status", "set", "dec"))
    parser.add_argument("value", nargs="?")
    return parser


def _cmd_status(value):
    if value is not None:
        _parser().error("status does not accept arguments")
    number = core.last_applied()
    if number is None:
        print(">>> No applied migrations yet.")
    else:
        print(">>> Last applied migration number:", number)


def _number(value, command):
    if value is None:
        _parser().error(f"{command} requires a migration number")
    try:
        number = int(value)
    except ValueError:
        _parser().error("migration number must be an integer")
    if number < 0:
        _parser().error("migration number must be >= 0")
    return number


def _cmd_set(value, write_file):
    core.update_last_applied(_number(value, "set"), write_file=write_file)


def _cmd_dec(value, write_file):
    if value is not None:
        _parser().error("dec does not accept arguments")
    current = core.last_applied()
    if current is None:
        print(">>> No applied migrations yet.")
        return
    if current == 0:
        _parser().error("migration number cannot be less than zero")
    core.update_last_applied(current - 1, write_file=write_file)


def _cmd_apply(assume_yes, write_file):
    core.check_last_applied(assume_yes=assume_yes)
    migrations_text = core.enumerate_migrations(
        assume_yes=assume_yes,
        write_file=write_file,
    )
    core.apply(
        migrations_text,
        assume_yes=assume_yes,
        write_file=write_file,
    )
    if core.conf.DUMP_SCHEMA:
        core.dump_schema()


def main(argv=None):
    args = _parser().parse_args(argv)
    write_file = not args.no_write_migrations
    command = args.command or "apply"
    if command == "status":
        _cmd_status(args.value)
    elif command == "set":
        _cmd_set(args.value, write_file)
    elif command == "dec":
        _cmd_dec(args.value, write_file)
    else:
        if args.value is not None:
            _parser().error("apply does not accept arguments")
        _cmd_apply(args.yes, write_file)


if __name__ == "__main__":
    main()
