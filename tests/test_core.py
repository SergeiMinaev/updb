import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
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

from updb import core


class CoreTests(unittest.TestCase):
    def test_enumerate_without_writing_file(self):
        source = "#LAST_APPLIED: 1\n\n# 1\nselect 1;\n\nselect 2;\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "migrations.sql"
            path.write_text(source)
            with patch.object(core, "FNAME", str(path)), patch(
                "builtins.input", side_effect=AssertionError("unexpected prompt")
            ):
                numbered = core.enumerate_migrations(
                    assume_yes=True,
                    write_file=False,
                )

            self.assertIn("# 2\nselect 2;", numbered)
            self.assertEqual(path.read_text(), source)

    def test_apply_uses_one_transaction_for_migration_and_counter(self):
        migrations = "#LAST_APPLIED: 0\n\n# 1\ncreate table example(id int);\n"
        commands = []

        def record(command):
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, b"", b"")

        with patch.object(core, "last_applied", return_value=0), patch.object(
            core, "exec_cmd", side_effect=record
        ):
            core.apply(
                migrations,
                assume_yes=True,
                write_file=False,
            )

        self.assertEqual(len(commands), 1)
        self.assertIn("ON_ERROR_STOP=1", commands[0])
        self.assertIn("--single-transaction", commands[0])
        query = commands[0][-1]
        self.assertIn("create table example(id int);", query)
        self.assertIn("select 1", query)

    def test_noninteractive_mode_does_not_initialize_database(self):
        with patch.object(core, "last_applied", return_value=None), patch(
            "builtins.input", side_effect=AssertionError("unexpected prompt")
        ):
            with self.assertRaises(SystemExit) as error:
                core.check_last_applied(assume_yes=True)

        self.assertEqual(error.exception.code, 1)

    def test_failed_command_returns_nonzero_exit_code(self):
        result = subprocess.CompletedProcess(
            ["psql"],
            7,
            b"",
            b"migration failed",
        )
        with patch.object(core.subprocess, "run", return_value=result):
            with self.assertRaises(SystemExit) as error:
                core.exec_cmd(["psql"])

        self.assertEqual(error.exception.code, 7)

    def test_database_connection_error_is_not_treated_as_missing_counter(self):
        result = subprocess.CompletedProcess(
            ["psql"],
            2,
            b"",
            b'psql: error: database "test" does not exist',
        )
        with patch.object(core.subprocess, "run", return_value=result):
            with self.assertRaises(SystemExit) as error:
                core.last_applied()

        self.assertEqual(error.exception.code, 2)

    def test_missing_counter_function_is_detected(self):
        result = subprocess.CompletedProcess(
            ["psql"],
            1,
            b"",
            b"ERROR: function public.last_migration_n() does not exist",
        )
        with patch.object(core.subprocess, "run", return_value=result):
            self.assertIsNone(core.last_applied())

    def test_counter_file_is_not_changed_when_database_update_fails(self):
        source = "#LAST_APPLIED: 3\n\n# 3\nselect 3;\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "migrations.sql"
            path.write_text(source)
            with patch.object(core, "FNAME", str(path)), patch.object(
                core,
                "exec_cmd",
                side_effect=SystemExit(1),
            ):
                with self.assertRaises(SystemExit):
                    core.update_last_applied(4)

            self.assertEqual(path.read_text(), source)


if __name__ == "__main__":
    unittest.main()
