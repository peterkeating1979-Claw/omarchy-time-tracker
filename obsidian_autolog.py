"""Durable delivery of completed sessions to Obsidian."""
import json
import os
import re
from pathlib import Path
import stat
import tempfile
from urllib.parse import quote
from uuid import uuid4

from obsidian_export import vault_directory, text, duration
from storage import secure_directory


def filename_part(value):
    # Keep readable Unicode while excluding path separators and Obsidian link syntax.
    value = re.sub(r'[\x00-\x1f\x7f/\\:*?"<>|\[\]#^]', '-', value)
    value = ' '.join(value.split()).strip(' .-')
    return value.encode('utf-8')[:80].decode('utf-8', errors='ignore').rstrip(' .-') or 'Unnamed'


def enqueue(db, session, vault, timezone):
    key = uuid4().hex
    base = ' - '.join((session['end'][:10], filename_part(session['company']),
                       filename_part(session['project'] or 'General company time')))
    payload = dict(session=session, timezone=timezone, filename_base=base)
    db.execute('INSERT INTO obsidian_jobs(session_id,job_key,vault,payload) VALUES (?,?,?,?)',
               (session['id'], key, vault, json.dumps(payload, ensure_ascii=False)))


def session_note(payload):
    s = payload['session']
    props = dict(type='time-tracker-session', session_id=s['id'], company=s['company'],
                 project=s['project'], started=s['start'], stopped=s['end'],
                 duration_seconds=s['seconds'], timezone=payload['timezone'], tags=['time-tracker'])
    lines = ['---'] + [f'{k}: {json.dumps(v, ensure_ascii=False)}' for k,v in props.items()]
    lines += ['---', '', '# Work session', '',
              '**Company:** '+text(s['company']),
              '**Project:** '+text(s['project'] or 'General company time'),
              '**Started:** '+text(s['start']), '**Stopped:** '+text(s['end']),
              '**Duration:** '+duration(s['seconds']), '**Timezone:** '+text(payload['timezone']), '']
    if s['note']:
        lines += ['## Notes', '', text(s['note']), '']
    return '\n'.join(lines).encode('utf-8')


def deliver(db, session_id):
    job = db.execute('SELECT * FROM obsidian_jobs WHERE session_id=?', (session_id,)).fetchone()
    if not job:
        return {}
    if job['path']:
        return dict(obsidian_path=job['path'], obsidian_uri='obsidian://open?path='+quote(job['path'], safe=''))
    try:
        payload = json.loads(job['payload'])
        s = payload['session']
        vault = vault_directory(job['vault'])
        folder = vault / 'Time Tracker'
        if folder.is_symlink():
            raise ValueError('The Time Tracker export folder cannot be a symlink.')
        folder = secure_directory(folder)
        if folder.parent != vault:
            raise ValueError('Export folder must remain inside the selected vault.')
        if 'filename_base' in payload:
            # Reserve a stable name before publishing, including across crashes/retries.
            if not db.in_transaction:
                db.execute('BEGIN IMMEDIATE')
            payload = json.loads(db.execute('SELECT payload FROM obsidian_jobs WHERE session_id=?',
                                           (session_id,)).fetchone()[0])
            if 'filename' not in payload:
                reserved = {json.loads(row[0]).get('filename') for row in db.execute(
                    'SELECT payload FROM obsidian_jobs WHERE vault=?', (job['vault'],))}
                base = payload['filename_base']
                filename = base + '.md'
                number = 2
                while filename in reserved or os.path.lexists(folder / filename):
                    filename = f'{base} ({number}).md'
                    number += 1
                payload['filename'] = filename
                db.execute('UPDATE obsidian_jobs SET payload=? WHERE session_id=?',
                           (json.dumps(payload, ensure_ascii=False), session_id))
            db.commit()
            filename = payload['filename']
            if Path(filename).name != filename or not filename.endswith('.md'):
                raise ValueError('Invalid session note filename.')
        else:
            # Older queued jobs must retain their original retry target.
            filename = f"{s['end'][:10]} Session {s['id']}-{job['job_key']}.md"
        path = folder / filename
        content = session_note(payload)
        fd, temporary = tempfile.mkstemp(prefix='.time-tracker-',suffix='.tmp',dir=folder)
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary,path)
            except FileExistsError:
                # A previous delivery may have completed before its receipt was saved.
                fd = os.open(path,os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd,'rb') as stream:
                    info=os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1:
                        raise ValueError('Existing session note is not a safe regular file.')
                    if stream.read(len(content)+1) != content:
                        raise ValueError('Existing session note differs. It has been preserved; move it aside before retrying.')
        finally:
            Path(temporary).unlink(missing_ok=True)
        directory_fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        db.execute('UPDATE obsidian_jobs SET path=?, error=NULL WHERE session_id=?',(str(path),session_id))
        db.commit()
        return dict(obsidian_path=str(path),obsidian_uri='obsidian://open?path='+quote(str(path),safe=''))
    except (OSError, ValueError) as exc:
        db.execute('UPDATE obsidian_jobs SET error=? WHERE session_id=?',(str(exc),session_id))
        db.commit()
        return dict(warning='Time is saved locally. Obsidian logging is pending: '+str(exc))
