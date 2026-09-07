"""Explicit, append-only Markdown report exports to a user-selected vault."""
from datetime import datetime, date, time, timedelta
import html
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import quote
from uuid import uuid4
from zoneinfo import ZoneInfo

from storage import secure_directory


def vault_directory(path):
    vault = Path(path).expanduser()
    if not vault.is_dir():
        raise ValueError('Choose an existing local Obsidian vault folder.')
    return secure_directory(vault)


def text(value):
    value = html.escape(str(value), quote=False).replace('\r', ' ').replace('\n', ' ')
    for char in '\\`*_{}[]()#+-.!|~':
        value = value.replace(char, '\\' + char)
    return value


def duration(seconds):
    s = max(0, int(seconds))
    return f'{s//3600:02d}:{s//60%60:02d}:{s%60:02d}'


def export_obsidian(db, report, vault_path, now, company=None, project=None):
    import tracker
    vault = vault_directory(vault_path)
    folder = vault / 'Time Tracker'
    if folder.is_symlink():
        raise ValueError('The Time Tracker export folder cannot be a symlink.')
    folder = secure_directory(folder)
    if folder.parent != vault:
        raise ValueError('Export folder must remain inside the selected vault.')
    tz = ZoneInfo(report['timezone'])
    generated = datetime.fromtimestamp(now, tz)
    properties = dict(type='time-tracker-report', period=report['period'],
                      start=report['start'], end_exclusive=report['end_exclusive'],
                      timezone=report['timezone'], generated=generated.isoformat(),
                      company=company, project=project, total_seconds=report['total_seconds'],
                      provisional=report['includes_running_timer'], tags=['time-tracker'])
    lines = ['---'] + [f'{key}: {json.dumps(value, ensure_ascii=False)}' for key, value in properties.items()] + ['---', '', '# '+report['period'].capitalize()+' work report', '']
    last = date.fromisoformat(report['end_exclusive']) - timedelta(days=1)
    lines += [f"**Period:** {report['start']} to {last.isoformat()}",
              '**Scope:** '+text(company or 'All companies')+(' / '+text(project) if project else ''),
              '**Total time:** '+duration(report['total_seconds']),
              '**Timezone:** '+text(report['timezone']), '']
    if report['includes_running_timer']:
        lines += ['> Provisional: includes the active timer through '+text(generated.isoformat())+'. The timer is still running.', '']

    def table(title, headers, rows):
        lines.extend(['## '+title, '', '| '+' | '.join(headers)+' |', '| '+' | '.join(['---']*len(headers))+' |'])
        for row in rows:
            lines.append('| '+' | '.join(text(v) for v in row)+' |')
        lines.append('')

    table('Company totals', ['Company','Time'], [(r['company'],duration(r['seconds'])) for r in report['companies']])
    table('Project totals', ['Company','Project','Time'], [(r['company'],r['project'] or 'General company time',duration(r['seconds'])) for r in report['projects']])
    table('Daily detail', ['Date','Company','Project','Time'], [(r['date'],r['company'],r['project'] or 'General company time',duration(r['seconds'])) for r in report['daily']])
    lo = datetime.combine(date.fromisoformat(report['start']), time.min, tz).timestamp()
    hi = datetime.combine(date.fromisoformat(report['end_exclusive']), time.min, tz).timestamp()
    cid = tracker.company(db, company)['id'] if company else None
    pid = tracker.project(db, cid, project) if project else None
    rows = db.execute('''SELECT s.*, c.name AS company, p.name AS project FROM sessions s
        JOIN companies c ON c.id=s.company_id LEFT JOIN projects p ON p.id=s.project_id
        WHERE s.start < ? AND COALESCE(s.end, ?) > ?
        AND (? IS NULL OR s.company_id=?) AND (? IS NULL OR s.project_id=?) ORDER BY s.start, s.id''',
        (hi, now, lo, cid, cid, pid, pid))
    records = []
    for r in rows:
        end = r['end'] if r['end'] is not None else now
        records.append((r['id'], r['company'], r['project'] or 'General company time',
                        datetime.fromtimestamp(r['start'], tz).isoformat(),
                        datetime.fromtimestamp(end, tz).isoformat()+(' (running snapshot)' if r['end'] is None else ''),
                        duration(min(hi,end)-max(lo,r['start'])), r['note']))
    table('Session records', ['ID','Company','Project','Started','Stopped / snapshot','Time in period','Notes'], records)
    if not records:
        lines += ['No work records match this selection.', '']
    lines += ['Each export is a separate snapshot. Session timestamps are the original start/stop times; time in period is clipped to the selected range. Company, project and daily totals describe the same time and should not be added together.', '']
    path = folder / f"{report['start']} {report['period']} {generated.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:12]}.md"
    fd, temporary = tempfile.mkstemp(prefix='.time-tracker-', suffix='.tmp', dir=folder)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write('\n'.join(lines))
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return dict(obsidian_path=str(path), obsidian_uri='obsidian://open?path='+quote(str(path), safe=''))
