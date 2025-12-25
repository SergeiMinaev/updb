from .core import (
	BASE_CMD,
	FNAME,
	TAG,
	_is_only_notice,
	exec_cmd,
	last_applied,
	check_last_applied,
	handle_notexist_last_applied,
	init_last_applied,
	update_last_applied,
	enumerate_migrations,
	apply,
	tables_list,
	dump_schema,
)


def run():
	from .cli import main

	main()


__all__ = [
	'BASE_CMD',
	'FNAME',
	'TAG',
	'_is_only_notice',
	'exec_cmd',
	'last_applied',
	'check_last_applied',
	'handle_notexist_last_applied',
	'init_last_applied',
	'update_last_applied',
	'enumerate_migrations',
	'apply',
	'tables_list',
	'dump_schema',
	'run',
]
