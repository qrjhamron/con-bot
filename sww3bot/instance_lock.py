"""Prevent CLI and Telegram processes from replaying the same task journal."""
import os
from pathlib import Path


class InstanceLock:
    def __init__(self, db_path):
        path = Path(db_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = open(str(path) + '.lock', 'a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self.file.write(b'0')
                self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise ValueError('Bot atau CLI lain sedang memakai database ini. Hentikan proses tersebut dahulu.') from None

    def close(self):
        self.file.close()
