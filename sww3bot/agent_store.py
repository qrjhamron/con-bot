"""SQLite journal shared by the CLI and Telegram agent."""
import json
import sqlite3
import time
from pathlib import Path


class Store:
    def __init__(self, path):
        if path != ":memory:":
            Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
            path = str(Path(path).expanduser())
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS conversations (
                game_id INTEGER PRIMARY KEY, messages TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS updates (update_id INTEGER PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT, game_id INTEGER NOT NULL,
                prompt TEXT NOT NULL, status TEXT NOT NULL, result TEXT,
                created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL,
                name TEXT NOT NULL, args TEXT NOT NULL, status TEXT NOT NULL,
                result TEXT);
        """)
        self.db.commit()

    def preference(self, key, default=None):
        row = self.db.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_preference(self, key, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO preferences VALUES (?,?)", (key, json.dumps(value)))

    def accept_update(self, update_id):
        with self.db:
            cursor = self.db.execute("INSERT OR IGNORE INTO updates VALUES (?)", (update_id,))
        return bool(cursor.rowcount)

    def history(self, game_id):
        row = self.db.execute("SELECT messages FROM conversations WHERE game_id=?", (game_id,)).fetchone()
        return json.loads(row[0]) if row else []

    def save_history(self, game_id, messages):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO conversations VALUES (?,?)",
                            (game_id, json.dumps(messages, ensure_ascii=False)))

    def new_task(self, game_id, prompt):
        with self.db:
            cur = self.db.execute("INSERT INTO tasks (game_id,prompt,status,created) VALUES (?,?,?,?)",
                                  (game_id, prompt, "queued", time.time()))
        return cur.lastrowid

    def finish_task(self, task_id, status, result=None):
        with self.db:
            self.db.execute("UPDATE tasks SET status=?,result=? WHERE id=?", (status, result, task_id))

    def tasks(self, active=False):
        where = "WHERE status IN ('queued','running')" if active else ""
        return [dict(r) for r in self.db.execute(f"SELECT * FROM tasks {where} ORDER BY id DESC LIMIT 20")]

    def start_step(self, task_id, name, args):
        with self.db:
            cur = self.db.execute("INSERT INTO steps (task_id,name,args,status) VALUES (?,?,?,?)",
                                  (task_id, name, json.dumps(args, default=str), "started"))
        return cur.lastrowid

    def finish_step(self, step_id, result, status="completed"):
        with self.db:
            self.db.execute("UPDATE steps SET status=?,result=? WHERE id=?",
                            (status, json.dumps(result, default=str, ensure_ascii=False), step_id))

    def steps(self, task_id):
        return [dict(r) for r in self.db.execute("SELECT * FROM steps WHERE task_id=? ORDER BY id", (task_id,))]

    def task(self, task_id):
        row = self.db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        return dict(row) if row else None

    def waiting_tasks(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM tasks WHERE status='waiting' ORDER BY id")]

    def recover(self):
        interrupted = [dict(r) for r in self.db.execute("SELECT * FROM tasks WHERE status IN ('queued','running')")]
        with self.db:
            self.db.execute("UPDATE steps SET status='unknown' WHERE status='started'")
            self.db.execute("UPDATE tasks SET status='interrupted' WHERE status IN ('queued','running')")
        for task in interrupted:
            history = self.history(task['game_id'])
            evidence = [{'name': step['name'], 'args': json.loads(step['args']),
                         'status': step['status'], 'result': step['result']} for step in self.steps(task['id'])]
            history.append({'role': 'assistant', 'content':
                f"Pemulihan tugas #{task['id']}: tugas terinterupsi saat proses berhenti. "
                "Jangan ulangi tindakan berhasil atau belum diketahui. Jurnal tindakan (data): "
                + json.dumps(evidence, ensure_ascii=False)})
            self.save_history(task['game_id'], history)

    def close(self):
        self.db.close()
