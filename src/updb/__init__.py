#!/usr/bin/env python
import os
import re
import sys
import shlex
import subprocess

sys.path.insert(0, os.getcwd())
import updb_conf as conf


BASE_CMD= f'psql -tA -U {conf.USER} {conf.DBNAME} -c'
FNAME = conf.FNAME
TAG = '# '


def _is_only_notice(stderr_bytes):
	if stderr_bytes == b'':
		return False
	lines = stderr_bytes.decode(errors='replace').splitlines()
	non_empty = [line.strip() for line in lines if line.strip() != '']
	return len(non_empty) > 0 and all(line.startswith('NOTICE:') for line in non_empty)


def exec_cmd(cmd):
	if isinstance(cmd, (list, tuple)):
		run_cmd = list(cmd)
	else:
		run_cmd = shlex.split(cmd)
	r = subprocess.run(run_cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
	if r.stderr != b'' and not _is_only_notice(r.stderr):
		print(r.stderr)
		sys.exit()
	return r


def last_applied():
	cmd = ["psql", "-tA", "-U", conf.USER, conf.DBNAME, "-c", "select public.last_migration_n()"]
	r = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
	if b'does not exist' in r.stderr: return None
	if r.stderr != b'' and not _is_only_notice(r.stderr):
		print(r.stderr)
		sys.exit()
	return int(r.stdout.strip())


def check_last_applied():
	if last_applied() is None:
		handle_notexist_last_applied()
		last_applied()


def handle_notexist_last_applied():
	print('>>> It looks like this database has no applied migrations yet.',
		'I will set the migration counter to zero. If this is a mistake, do not continue!')
	if input('Continue? ').lower() == 'y':
		init_last_applied()
	else:
		print('Closing.')
		sys.exit()


def init_last_applied():
	update_last_applied(0)


def update_last_applied(n):
	lines = open(FNAME).readlines()
	last_applied = '#LAST_APPLIED: ' + str(n) + '\n'
	if lines[0].startswith('#LAST_APPLIED'):
		lines[0] = last_applied
	else:
		lines = [last_applied + '\n'] + lines
	open(FNAME, 'w').write(''.join(lines))
	q = 'create or replace function public.last_migration_n() '\
		f"RETURNS int LANGUAGE sql PARALLEL SAFE AS 'select {n}'";
	cmd = f'{BASE_CMD} "{q}"'
	exec_cmd(cmd)
	print(f'>>> Migration counter was set to {n}.')


def enumerate_migrations():
	f = open(FNAME)
	lines = f.readlines()
	f.close()
	new = ''
	n = 1
	for line in lines:
		if line.startswith(TAG):
			n = int(line.strip(TAG)) + 1
	ln = 0
	while ln < len(lines):
		line = lines[ln]
		nextline = lines[ln+1] if ln+1 < len(lines) else ''
		if (line.strip() == '' and not nextline.startswith(TAG)):
			new += f'\n{TAG}{n}'
			n += 1
		new += line
		ln += 1

	print(new)
	if	input('\n>>> Correct? ').lower() == 'y':
		f = open(FNAME, 'w')
		f.write(new)
		f.close()
		print('>>> OK. Now lets apply.')
	else:
		sys.exit()


def apply():
	lines = open(FNAME).readlines()
	last_n = last_applied()
	print('>>> Last applied migration number:', last_n)
	is_any_unapplied_found = False
	for line in lines:
		if line.startswith(TAG):
			n = int(line.strip(TAG))
			if n > last_n:
				is_any_unapplied_found = True
				q = ''.join(lines).split(f'\n{TAG}{n}')[1].split(TAG)[0].strip()
				print(f'\n>>> This query will be executed:\n{q}')
				if input('\n>>> Apply? ').lower() == 'y':
					cmd = ["psql", "-tA", "-U", conf.USER, conf.DBNAME, "-c", q]
					exec_cmd(cmd)
					update_last_applied(n)
					print('>>> Applied successfully.\n')
				else:
					sys.exit()
	if not is_any_unapplied_found:
		print('>>> No unapplied migrations found.')


def tables_list():
	cmd = f'{BASE_CMD} "select table_name from information_schema.tables where table_schema = \'public\'";'
	r = exec_cmd(cmd)
	tables = r.stdout.decode().split('\n')
	return [str(table).strip() for table in tables if table.strip() != '']


def dump_schema():
	if not os.path.exists(conf.SCHEMA_DIR):
		print('Error: schema dir', conf.SCHEMA_DIR, 'does not exists.')
		sys.exit()
	elif not os.path.isdir(conf.SCHEMA_DIR):
		print('Error:', conf.SCHEMA_DIR, 'is not a directory.')
		sys.exit()

	cmd = f'pg_dump --schema-only -U {conf.USER} {conf.DBNAME}'
	r = exec_cmd(cmd)
	open(f'{conf.SCHEMA_DIR}/schema.sql', 'w').write(r.stdout.decode())

	for table in tables_list():
		print(f'Saving schema of {table} to {conf.SCHEMA_DIR}/{table}.sql')
		cmd = f'pg_dump --schema-only -U {conf.USER} {conf.DBNAME} -t {table} -O'
		r = exec_cmd(cmd)
		s = r.stdout.decode()
		fin = ''
		for line in s.split('\n'):
			if (not line.startswith('--')
					and not line.startswith('SET ')
					and not line.startswith('SELECT pg_catalog.set_config')
					#and line.strip() != ''
			):
				fin += line + '\n'
		fin = re.sub(r'\n\n+', '\n\n', fin)
		fin = re.sub(r'^\n+', '', fin)
		open(f'{conf.SCHEMA_DIR}/{table}.sql', 'w').write(fin)

def run():
	check_last_applied()
	enumerate_migrations()
	apply()
	if conf.DUMP_SCHEMA:
		dump_schema()

if __name__ == '__main__':
	run()
