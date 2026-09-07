#!/usr/bin/env python3
"""One-shot JSON bridge between the bar and the shared tracker database."""
import json
import sys
import tracker


def main():
    db = None
    try:
        request = json.loads(sys.argv[1])
        db = tracker.connect(tracker.os.environ.get('TIME_TRACKER_DB', str(tracker.DEFAULT_DB)))
        db.execute('BEGIN IMMEDIATE')
        result = None
        if request.get('args'):
            result = tracker.execute(db, tracker.parser().parse_args(request['args']))
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
