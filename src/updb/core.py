import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.getcwd())
import updb_conf as conf


BASE_CMD = f"psql -X -v ON_ERROR_STOP=1 -tA -U {conf.USER} {conf.DBNAME} -c"
FNAME = conf.FNAME
TAG = "# "


def _is_only_notice(stderr_bytes):
    if stderr_bytes == b"":
        return False
    lines = stderr_bytes.decode(errors="replace").splitlines()
    non_empty = [line.strip() for line in lines if line.strip() != ""]
    return len(non_empty) > 0 and all(line.startswith("NOTICE:") for line in non_empty)


def _fail(message, exit_code=1):
    print(message, file=sys.stderr)
    raise SystemExit(exit_code or 1)


def _psql_command(query, single_transaction=False):
    command = [
        "psql",
        "-X",
        "-v",
        "ON_ERROR_STOP=1",
        "-tA",
        "-U",
        conf.USER,
        conf.DBNAME,
    ]
    if single_transaction:
        command.append("--single-transaction")
    command.extend(["-c", query])
    return command


def exec_cmd(cmd):
    run_cmd = list(cmd) if isinstance(cmd, (list, tuple)) else shlex.split(cmd)
    result = subprocess.run(run_cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    if result.returncode != 0:
        error = result.stderr.decode(errors="replace").strip()
        _fail(error or f"Command failed with exit code {result.returncode}", result.returncode)
    return result


def _parse_last_applied_output(stdout_bytes):
    text = stdout_bytes.decode(errors="replace")
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.isdigit():
            return int(line)
    raise ValueError(text.strip())


def last_applied():
    query = "select public.last_migration_n()"
    result = subprocess.run(
        _psql_command(query),
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    if result.returncode != 0:
        if b"function public.last_migration_n() does not exist" in result.stderr:
            return None
        error = result.stderr.decode(errors="replace").strip()
        _fail(error or f"psql failed with exit code {result.returncode}", result.returncode)
    try:
        return _parse_last_applied_output(result.stdout)
    except ValueError as error:
        _fail(f"Error: unexpected output from psql: {error}")


def check_last_applied(assume_yes=False):
    if last_applied() is not None:
        return
    if assume_yes:
        _fail(
            ">>> Migration counter does not exist. "
            "Initialize it manually with `updb set 0`."
        )
    handle_notexist_last_applied()


def handle_notexist_last_applied():
    print(
        ">>> It looks like this database has no applied migrations yet. "
        "I will set the migration counter to zero. If this is a mistake, do not continue!"
    )
    if input("Continue? ").lower() == "y":
        init_last_applied()
        return
    _fail("Closing.")


def init_last_applied():
    update_last_applied(0)


def _last_applied_query(number):
    return (
        "create or replace function public.last_migration_n() "
        f"returns int language sql parallel safe as 'select {number}';"
    )


def _write_last_applied(number):
    with open(FNAME) as migrations_file:
        lines = migrations_file.readlines()
    last_applied_line = f"#LAST_APPLIED: {number}\n"
    if lines and lines[0].startswith("#LAST_APPLIED"):
        lines[0] = last_applied_line
    else:
        lines = [last_applied_line, "\n", *lines]
    with open(FNAME, "w") as migrations_file:
        migrations_file.write("".join(lines))


def update_last_applied(number, write_file=True):
    exec_cmd(_psql_command(_last_applied_query(number)))
    if write_file:
        _write_last_applied(number)
    print(f">>> Migration counter was set to {number}.")


def _enumerated_migrations(lines):
    migration_numbers = [
        int(match.group(1))
        for line in lines
        if (match := re.fullmatch(r"# (\d+)\s*", line))
    ]
    number = max(migration_numbers, default=0) + 1
    result = ""
    for index, line in enumerate(lines):
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if line.strip() == "" and next_line and not next_line.startswith(TAG):
            result += f"\n{TAG}{number}"
            number += 1
        result += line
    return result


def enumerate_migrations(assume_yes=False, write_file=True):
    with open(FNAME) as migrations_file:
        numbered = _enumerated_migrations(migrations_file.readlines())

    print(numbered)
    if not assume_yes and input("\n>>> Correct? ").lower() != "y":
        _fail("Closing.")
    if write_file:
        with open(FNAME, "w") as migrations_file:
            migrations_file.write(numbered)
    print(">>> OK. Now lets apply.")
    return numbered


def _migrations(migrations_text):
    markers = list(re.finditer(r"(?m)^# (\d+)\s*$", migrations_text))
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(migrations_text)
        yield int(marker.group(1)), migrations_text[marker.end():end].strip()


def _migration_transaction(query, number):
    query = query.rstrip()
    if query and not query.endswith(";"):
        query += ";"
    return f"{query}\n{_last_applied_query(number)}"


def apply(migrations_text=None, assume_yes=False, write_file=True):
    if migrations_text is None:
        with open(FNAME) as migrations_file:
            migrations_text = migrations_file.read()

    last_number = last_applied()
    if last_number is None:
        _fail(">>> Migration counter does not exist.")
    print(">>> Last applied migration number:", last_number)
    unapplied_found = False
    for number, query in _migrations(migrations_text):
        if number <= last_number:
            continue
        unapplied_found = True
        print(f"\n>>> This query will be executed:\n{query}")
        if not assume_yes and input("\n>>> Apply? ").lower() != "y":
            _fail("Closing.")
        exec_cmd(
            _psql_command(
                _migration_transaction(query, number),
                single_transaction=True,
            )
        )
        if write_file:
            _write_last_applied(number)
        print(">>> Applied successfully.\n")
    if not unapplied_found:
        print(">>> No unapplied migrations found.")


def tables_list():
    query = (
        "select table_name from information_schema.tables "
        "where table_schema = 'public'"
    )
    result = exec_cmd(_psql_command(query))
    return [table.strip() for table in result.stdout.decode().splitlines() if table.strip()]


def dump_schema():
    if not os.path.exists(conf.SCHEMA_DIR):
        _fail(f"Error: schema dir {conf.SCHEMA_DIR} does not exist.")
    if not os.path.isdir(conf.SCHEMA_DIR):
        _fail(f"Error: {conf.SCHEMA_DIR} is not a directory.")

    result = exec_cmd(["pg_dump", "--schema-only", "-U", conf.USER, conf.DBNAME])
    with open(f"{conf.SCHEMA_DIR}/schema.sql", "w") as schema_file:
        schema_file.write(result.stdout.decode())

    for table in tables_list():
        path = f"{conf.SCHEMA_DIR}/{table}.sql"
        print(f"Saving schema of {table} to {path}")
        result = exec_cmd(
            ["pg_dump", "--schema-only", "-U", conf.USER, conf.DBNAME, "-t", table, "-O"]
        )
        schema = ""
        for line in result.stdout.decode().splitlines():
            if (
                not line.startswith("--")
                and not line.startswith("SET ")
                and not line.startswith("SELECT pg_catalog.set_config")
            ):
                schema += line + "\n"
        schema = re.sub(r"\n\n+", "\n\n", schema)
        schema = re.sub(r"^\n+", "", schema)
        with open(path, "w") as schema_file:
            schema_file.write(schema)
