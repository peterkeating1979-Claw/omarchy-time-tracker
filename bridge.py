#!/usr/bin/env python3
"""One-shot JSON bridge between the bar and the shared tracker database."""
import json
import sys
import tracker


def parse_request(raw):
    if len(raw.encode('utf-8')) > 16384:
        raise ValueError('Request exceeds 16 KiB.')
    request = json.loads(raw)
    if not isinstance(request, dict) or set(request) - {'args'}:
        raise ValueError('Expected a JSON object containing only args.')
    args = request.get('args', [])
    if not isinstance(args, list) or len(args) > 20 or any(not isinstance(a, str) or len(a) > 4096 for a in args):
        raise ValueError('Expected at most 20 string arguments, each at most 4096 characters.')
    allowed = {'add-company', 'companies', 'add-project', 'projects', 'select', 'start', 'stop', 'status', 'report', 'records', 'timezone', 'vault', 'auto-obsidian', 'retry-obsidian', 'delete-record', 'clear-records'}
    if args and (args[0] not in allowed or any(a in ('-h', '--help', '--db') for a in args)):
        raise ValueError('Unsupported bar request.')
    return tracker.parser().parse_args(args) if args else None


def main():
    db = None
    try:
        if len(sys.argv) != 2:
            raise ValueError('Expected one JSON request.')
        args = parse_request(sys.argv[1])
        db = tracker.connect(tracker.os.environ.get('TIME_TRACKER_DB', str(tracker.DEFAULT_DB)))
        db.execute('BEGIN IMMEDIATE')
        result = None
        if args:
            result = tracker.execute(db, args)
        status = tracker.execute(db, tracker.parser().parse_args(['status']))
        companies = [dict(r) for r in db.execute('SELECT * FROM companies ORDER BY name')]
        projects = [dict(r) for r in db.execute('SELECT * FROM projects ORDER BY name')]
        db.commit()
        print(json.dumps(dict(ok=True, result=result, status=status, companies=companies, projects=projects)))
    except Exception as exc:
        if db:
            db.rollback()
        print(json.dumps(dict(ok=False, error=str(exc))))
        return 1
    finally:
        if db:
            db.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
