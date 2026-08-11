#### Not production ready at all. Use at your own risk.

# Updb - simple DB migration manager for non-bloated projects

How it works? In short, a single migrations.sql file is used to store recent migrations. There is no need to create tons of up.sql and down.sql.

Only PostgreSQL is supported.

# Key points

1) Do not create VCS inside of another VCS. There is no need to create tons of up.sql and down.sql files. It doesn't help. You can store all the migrations in a single migrations.sql file.
2) Oldest migrations are not needed so you can keep only 10-20 recent migrations in migrations.sql. All migrations are stored in Git any way.
3) Using a single file for storing 10-20 recent migrations can help you to observe what is happening to the DB schema. It's easier to read one file instead of 10-20 separated ones. You can read migrations.sql from time to time to gain a better understanding of how your project is going.
4) How often do you use a down.sql?

# Installation
```
pip install updb
```

# Usage
1) Create updb_conf.py and specify DBNAME and other settings (see example.updb_conf.py).
2) Write some migrations in migrations.sql file (just pure SQL, see example1.migrations.sql and example2.migrations.sql). Migrations should be separated by an empty line.
3) Run `updb` command. The script will enumerate new migrations and apply them.
4) The number of last applied migration will be stored in `public.last_migration_n()` function.
Additionally it will appeared in migrations.sql at the first line.
5) Optionally per-table schema will be dumped to schema/{table}.sql files and full DB schema - to schema/schema.sql .
6) When you want to create new migrations, just add it to migrations.sql and run `updb` again.
7) If you need to create an empty DB for tests, use schema/schema.sql . Older versions are available via Git.

# Non-interactive usage

Use `--yes` to enumerate and apply all pending migrations without confirmation prompts:

```bash
updb --yes
```

For deployments, `--no-write-migrations` keeps `migrations.sql` unchanged. Migration
numbers are still assigned deterministically and the applied number is stored in the
database:

```bash
updb --yes --no-write-migrations
```

Non-interactive mode does not initialize a database without a migration counter. Run
`updb set 0` manually after verifying the database configuration. Every migration and
the corresponding counter update are executed in one transaction. PostgreSQL errors
stop the command with a non-zero exit code.

Suggested directory structure:
```
./project/db/migrations.sql
./project/db/schema/{table}.sql
```
