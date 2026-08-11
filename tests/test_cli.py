import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.modules.setdefault(
    "updb_conf",
    SimpleNamespace(
        USER="postgres",
        DBNAME="test",
        FNAME="migrations.sql",
        DUMP_SCHEMA=False,
        SCHEMA_DIR="schema",
    ),
)

from updb import cli


class CliTests(unittest.TestCase):
    def test_yes_and_no_write_are_passed_to_apply_flow(self):
        with patch.object(cli.core, "check_last_applied") as check, patch.object(
            cli.core,
            "enumerate_migrations",
            return_value="# 1\nselect 1;",
        ) as enumerate_migrations, patch.object(cli.core, "apply") as apply:
            cli.main(["--yes", "--no-write-migrations"])

        check.assert_called_once_with(assume_yes=True)
        enumerate_migrations.assert_called_once_with(
            assume_yes=True,
            write_file=False,
        )
        apply.assert_called_once_with(
            "# 1\nselect 1;",
            assume_yes=True,
            write_file=False,
        )

    def test_set_command_is_preserved(self):
        with patch.object(cli.core, "update_last_applied") as update:
            cli.main(["set", "12"])

        update.assert_called_once_with(12, write_file=True)

    def test_dec_command_is_preserved(self):
        with patch.object(cli.core, "last_applied", return_value=12), patch.object(
            cli.core,
            "update_last_applied",
        ) as update:
            cli.main(["dec"])

        update.assert_called_once_with(11, write_file=True)


if __name__ == "__main__":
    unittest.main()
