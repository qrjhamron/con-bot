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
            CREATE TABLE IF NOT EXISTS build_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT, game_id INTEGER NOT NULL,
                city_id INTEGER NOT NULL, building TEXT NOT NULL, status TEXT NOT NULL,
                created REAL NOT NULL, updated REAL NOT NULL, result TEXT);
            CREATE TABLE IF NOT EXISTS commander_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, game_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL, kind TEXT NOT NULL, args TEXT NOT NULL,
                dependencies TEXT NOT NULL, source TEXT NOT NULL, priority INTEGER NOT NULL,
                state TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', baseline TEXT,
                dedupe_key TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS commander_nodes_game ON commander_nodes(game_id,state);
            CREATE TABLE IF NOT EXISTS commander_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, game_id INTEGER NOT NULL,
                kind TEXT NOT NULL, data TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS commander_snapshots (
                game_id INTEGER PRIMARY KEY, snapshot TEXT NOT NULL, observed REAL NOT NULL);
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

    def unresolved_action(self, game_id, args):
        from .protocol import action_key
        key = action_key(args)
        if key is None:
            return None
        rows = self.db.execute("""SELECT steps.* FROM steps JOIN tasks ON tasks.id=steps.task_id
            WHERE tasks.game_id=? AND steps.status IN ('unknown','started') ORDER BY steps.id DESC""", (game_id,))
        return next((dict(r) for r in rows if action_key(json.loads(r['args'])) == key), None)

    def task(self, task_id):
        row = self.db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        return dict(row) if row else None

    def waiting_tasks(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM tasks WHERE status='waiting' ORDER BY id")]

    def enqueue_build(self, game_id, city_id, building):
        """Queue a building; an identical active entry returns its existing id."""
        name = str(building).strip()
        row = self.db.execute("""SELECT * FROM build_queue WHERE game_id=? AND city_id=?
            AND lower(building)=lower(?) AND status IN ('queued','building','unknown')""",
            (game_id, city_id, name)).fetchone()
        if row:
            position = self.db.execute("SELECT COUNT(*) FROM build_queue WHERE game_id=? AND status='queued' AND id<=?",
                                       (game_id, row['id'])).fetchone()[0]
            return {'queue_id': row['id'], 'queued': False, 'position': position}
        now = time.time()
        with self.db:
            cur = self.db.execute("""INSERT INTO build_queue
                (game_id,city_id,building,status,created,updated) VALUES (?,?,?,?,?,?)""",
                (game_id, city_id, name, 'queued', now, now))
        position = self.db.execute("SELECT COUNT(*) FROM build_queue WHERE game_id=? AND status='queued' AND id<=?",
                                   (game_id, cur.lastrowid)).fetchone()[0]
        return {'queue_id': cur.lastrowid, 'queued': True, 'position': position}

    def pending_builds(self, game_id):
        return [dict(r) for r in self.db.execute("""SELECT * FROM build_queue
            WHERE game_id=? AND status IN ('queued','unknown') ORDER BY id""", (game_id,))]

    def builds(self, game_id, limit=20):
        return [dict(r) for r in self.db.execute("SELECT * FROM build_queue WHERE game_id=? ORDER BY id DESC LIMIT ?",
                                                 (game_id, limit))]

    def set_build_status(self, queue_id, status, result=None):
        with self.db:
            self.db.execute("UPDATE build_queue SET status=?,updated=?,result=? WHERE id=?",
                            (status, time.time(), json.dumps(result, default=str, ensure_ascii=False)
                             if result is not None else None, queue_id))

    def cancel_queued_build(self, queue_id, game_id):
        with self.db:
            cursor = self.db.execute("""UPDATE build_queue SET status='cancelled',updated=?
                WHERE id=? AND game_id=? AND status IN ('queued','unknown')""", (time.time(), queue_id, game_id))
        return bool(cursor.rowcount)

    def recover(self):
        interrupted = [dict(r) for r in self.db.execute("SELECT * FROM tasks WHERE status IN ('queued','running')")]
        with self.db:
            self.db.execute("UPDATE steps SET status='unknown' WHERE status='started'")
            self.db.execute("UPDATE tasks SET status='interrupted' WHERE status IN ('queued','running')")
            self.db.execute("UPDATE build_queue SET status='queued',updated=? WHERE status='building'", (time.time(),))
            self.db.execute("UPDATE commander_nodes SET state='outcome_unknown',detail='Pengiriman terinterupsi saat restart',updated=? WHERE state='dispatching'", (time.time(),))
        for task in interrupted:
            history = self.history(task['game_id'])
            evidence = [{'name': step['name'], 'args': json.loads(step['args']),
                         'status': step['status'], 'result': step['result']} for step in self.steps(task['id'])]
            history.append({'role': 'assistant', 'content':
                f"Pemulihan tugas #{task['id']}: tugas terinterupsi saat proses berhenti. "
                "Jangan ulangi tindakan berhasil atau belum diketahui. Jurnal tindakan (data): "
                + json.dumps(evidence, ensure_ascii=False)})
            self.save_history(task['game_id'], history)

    @staticmethod
    def _node(row):
        if row is None:
            return None
        value = dict(row)
        for key in ('args', 'dependencies', 'baseline'):
            value[key] = json.loads(value[key]) if value[key] else ({} if key != 'dependencies' else [])
        return value

    def commander_nodes(self, game_id, limit=200):
        return [self._node(r) for r in self.db.execute(
            "SELECT * FROM commander_nodes WHERE game_id=? AND (state NOT IN ('completed','failed','cancelled','expired') OR id IN (SELECT id FROM commander_nodes WHERE game_id=? AND state IN ('completed','failed','cancelled','expired') ORDER BY id DESC LIMIT ?)) ORDER BY (state IN ('completed','failed','cancelled','expired')),priority,id", (game_id, game_id, limit))]

    def campaigns(self, game_id, limit=30):
        values = [json.loads(r[0]) for r in self.db.execute('SELECT value FROM preferences WHERE key LIKE ?',
                                                          (f'campaign:{game_id}:%',))]
        return sorted(values, key=lambda c: c['created_at'], reverse=True)[:limit]

    def enqueue_campaign(self, game_id, player_id, plan, source="manual"):
        from .commander_queue import TERMINAL
        army_ids = {aid for r in plan['routes'] for aid in r.get('army_ids', [r['army_id']])}
        unit_ids = {uid for r in plan['routes'] for node in r['nodes'] for uid in node['args'].get('unit_ids', [])}
        if any(n['state'] not in TERMINAL and (n['args'].get('army_id') in army_ids or
               army_ids.intersection(n['args'].get('army_ids', [])) or unit_ids.intersection(n['args'].get('unit_ids', [])))
               for n in self.commander_nodes(game_id)):
            raise ValueError('Pasukan sudah punya rute di queue. Selesaikan atau batalkan rute sebelumnya.')
        now = time.time()
        routes = []
        with self.db:
            for route in plan['routes']:
                dependencies, ids = [], []
                for node in route['nodes']:
                    args, kind = node['args'], node['kind']
                    key = json.dumps([player_id, kind, args, dependencies, source], sort_keys=True)
                    cursor = self.db.execute("""INSERT INTO commander_nodes
                        (game_id,player_id,kind,args,dependencies,source,priority,state,dedupe_key,created,updated)
                        VALUES (?,?,?,?,?,?,1,'queued',?,?,?)""",
                        (game_id, player_id, kind, json.dumps(args), json.dumps(dependencies), source, key, now, now))
                    ids.append(cursor.lastrowid)
                    dependencies = [cursor.lastrowid]
                routes.append({'army_id': route['army_id'], 'army_ids': route.get('army_ids', [route['army_id']]),
                               'node_ids': ids, 'province_ids': route['province_ids']})
            campaign_id = routes[0]['node_ids'][0]
            result = {'campaign_id': campaign_id, 'game_id': game_id, 'player_id': player_id,
                      'mode': plan['mode'], 'routes': routes, 'created_at': now,
                      'coordinated': plan.get('coordinated', False), 'rally_province': plan.get('rally_province')}
            self.db.execute('INSERT OR REPLACE INTO preferences VALUES (?,?)',
                            (f'campaign:{game_id}:{campaign_id}', json.dumps(result)))
            self.db.execute('INSERT OR REPLACE INTO preferences VALUES (?,?)',
                            (f'commander_next:{game_id}', '0'))
        return result

    def commander_node(self, node_id, game_id):
        return self._node(self.db.execute('SELECT * FROM commander_nodes WHERE id=? AND game_id=?',
                                         (node_id, game_id)).fetchone())

    def enqueue_commander(self, game_id, player_id, kind, args, dependencies=None, source='manual', priority=3):
        dependencies = list(dependencies or [])
        for dependency in dependencies:
            prior = self.commander_node(dependency, game_id)
            if not prior or prior['player_id'] != player_id:
                raise ValueError('Dependency harus berasal dari pemain dan game yang sama.')
        key = json.dumps([player_id, kind, args, dependencies, source], sort_keys=True)
        with self.db:
            row = self.db.execute("""SELECT * FROM commander_nodes WHERE game_id=? AND dedupe_key=?
                AND state NOT IN ('completed','cancelled','failed') ORDER BY id DESC LIMIT 1""", (game_id, key)).fetchone()
            if row:
                return self._node(row)
            now = time.time()
            cursor = self.db.execute("""INSERT INTO commander_nodes
                (game_id,player_id,kind,args,dependencies,source,priority,state,dedupe_key,created,updated)
                VALUES (?,?,?,?,?,?,?,'queued',?,?,?)""",
                (game_id, player_id, kind, json.dumps(args), json.dumps(dependencies), source, priority, key, now, now))
        return self.commander_node(cursor.lastrowid, game_id)

    def set_commander_node(self, node_id, state, detail='', baseline=None):
        with self.db:
            if baseline is None:
                self.db.execute('UPDATE commander_nodes SET state=?,detail=?,updated=? WHERE id=?',
                                (state, detail, time.time(), node_id))
            else:
                self.db.execute('UPDATE commander_nodes SET state=?,detail=?,baseline=?,updated=? WHERE id=?',
                                (state, detail, json.dumps(baseline), time.time(), node_id))

    def observe_commander(self, game_id, snapshot):
        from .commander_state import changes
        row = self.db.execute('SELECT snapshot FROM commander_snapshots WHERE game_id=?', (game_id,)).fetchone()
        events = changes(json.loads(row[0]) if row else None, snapshot)
        now = time.time()
        with self.db:
            for kind, data in events:
                self.db.execute('INSERT INTO commander_events (game_id,kind,data,created) VALUES (?,?,?,?)',
                                (game_id, kind, json.dumps(data), now))
            self.db.execute('INSERT OR REPLACE INTO commander_snapshots VALUES (?,?,?)',
                            (game_id, json.dumps(snapshot), now))
            key = f'contact_history:{game_id}:{snapshot["player_id"]}'
            history = self.preference(key, {})
            for contact in snapshot.get('visible_contacts', []):
                history[contact['army_id']] = dict(contact, observed_at=now)
            if history:
                self.db.execute('INSERT OR REPLACE INTO preferences VALUES (?,?)', (key, json.dumps(history)))
        return events

    def commander_events(self, game_id, limit=30):
        return [dict(r, data=json.loads(r['data'])) for r in self.db.execute(
            'SELECT * FROM commander_events WHERE game_id=? ORDER BY id DESC LIMIT ?', (game_id, limit))]

    def close(self):
        self.db.close()
