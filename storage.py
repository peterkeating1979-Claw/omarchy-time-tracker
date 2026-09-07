"""Local storage boundaries for a single-user Linux desktop plugin."""
import os
from pathlib import Path
import stat


def secure_directory(path, private=False):
    path = Path(path).expanduser().absolute()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = path.resolve(strict=True)
    for index, directory in enumerate((path, *path.parents)):
        info = directory.stat()
        if info.st_uid not in (0, os.geteuid()) or (index == 0 and info.st_uid != os.geteuid()):
            raise ValueError('Storage directory must be owned by you, with trusted parent directories.')
        # A sticky ancestor such as /tmp cannot replace a user-owned child.
        sticky_ancestor = index > 0 and info.st_mode & stat.S_ISVTX
        if info.st_mode & 0o022 and not sticky_ancestor:
            raise ValueError('Storage directory is writable by other users. Choose a private directory.')
    if private:
        path.chmod(0o700)
    return path


def private_file(path, create=False, database=False):
    flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
    if create:
        flags |= os.O_CREAT
    try:
        fd = os.open(path, flags, 0o600)
    except FileNotFoundError:
        if not create:
            return
        raise
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1:
            raise ValueError('Storage files must be regular files owned by you, without hard links.')
        if database and info.st_size and os.read(fd, 16) != b'SQLite format 3\x00':
            raise ValueError('The selected database is not a SQLite database.')
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)
