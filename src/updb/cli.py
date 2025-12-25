import sys

from . import core


def _cmd_status():
	n = core.last_applied()
	if n is None:
		print('>>> No applied migrations yet.')
	else:
		print('>>> Last applied migration number:', n)


def _cmd_set(argv):
	if len(argv) < 1:
		print('>>> Usage: updb set <n>')
		sys.exit(1)
	try:
		n = int(argv[0])
	except ValueError:
		print('>>> Error: n must be an integer.')
		sys.exit(1)
	if n < 0:
		print('>>> Error: n must be >= 0.')
		sys.exit(1)
	core.update_last_applied(n)


def _cmd_dec(argv):
	if len(argv) > 0:
		print('>>> Usage: updb dec')
		sys.exit(1)
	cur = core.last_applied()
	if cur is None:
		print('>>> No applied migrations yet.')
		return
	new_n = cur - 1
	if new_n < 0:
		print('>>> Error: result would be < 0.')
		sys.exit(1)
	core.update_last_applied(new_n)


def _cmd_apply():
	core.check_last_applied()
	core.enumerate_migrations()
	core.apply()
	if core.conf.DUMP_SCHEMA:
		core.dump_schema()


def main(argv=None):
	argv = list(sys.argv[1:] if argv is None else argv)
	if argv:
		cmd = argv[0]
		args = argv[1:]
		if cmd == 'status':
			_cmd_status()
			return
		if cmd == 'set':
			_cmd_set(args)
			return
		if cmd == 'dec':
			_cmd_dec(args)
			return
	_cmd_apply()


if __name__ == '__main__':
	main()
