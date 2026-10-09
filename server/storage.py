"""Local SQLite passage library and reading history; no network dependency."""
from contextlib import contextmanager
import csv
import json
from pathlib import Path
import sqlite3


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS passages (
                    id TEXT PRIMARY KEY, document TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS readings (
                    session_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL,
                    learner TEXT NOT NULL, passage_title TEXT NOT NULL,
                    summary TEXT NOT NULL, detail TEXT
                );
                CREATE INDEX IF NOT EXISTS reading_time ON readings(timestamp);
                CREATE TABLE IF NOT EXISTS recordings (
                    session_id TEXT NOT NULL, segment_id TEXT NOT NULL,
                    time_offset REAL NOT NULL, duration REAL NOT NULL, wav BLOB NOT NULL,
                    PRIMARY KEY(session_id, segment_id)
                );
                CREATE TABLE IF NOT EXISTS migrations (name TEXT PRIMARY KEY);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def migrate_csv(self, path: Path, passages: dict) -> None:
        """Import the old CSV once without modifying it or replacing saved details."""
        if not path.exists():
            return
        with self.connect() as db:
            if db.execute("SELECT 1 FROM migrations WHERE name='legacy_csv'").fetchone():
                return
            with path.open(encoding='utf-8-sig', newline='') as source:
                for row in csv.DictReader(source):
                    if not row.get('session_id'):
                        continue
                    title = passages.get(row.get('passage_id'), {}).get('title', row.get('passage_id', ''))
                    row['passage_title'] = title
                    db.execute('INSERT OR IGNORE INTO readings VALUES (?, ?, ?, ?, ?, NULL)',
                               (row['session_id'], row.get('timestamp', ''), row.get('learner', ''),
                                title, json.dumps(row, ensure_ascii=False)))
            db.execute("INSERT INTO migrations VALUES ('legacy_csv')")

    def passages(self) -> list[dict]:
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT document FROM passages ORDER BY rowid')]

    def add_passage(self, passage: dict) -> None:
        with self.connect() as db:
            db.execute('INSERT INTO passages VALUES (?, ?)', (passage['id'], json.dumps(passage, ensure_ascii=False)))

    def add_passages(self, passages: list[dict]) -> None:
        with self.connect() as db:
            db.executemany('INSERT INTO passages VALUES (?, ?)',
                           [(p['id'], json.dumps(p, ensure_ascii=False)) for p in passages])

    def save(self, summary: dict, detail: dict) -> None:
        with self.connect() as db:
            db.execute('''INSERT INTO readings VALUES (?, ?, ?, ?, ?, ?)
                          ON CONFLICT(session_id) DO UPDATE SET timestamp=excluded.timestamp,
                          learner=excluded.learner, passage_title=excluded.passage_title,
                          summary=excluded.summary, detail=excluded.detail''',
                       (summary['session_id'], summary['timestamp'], summary['learner'], summary['passage_title'],
                        json.dumps(summary, ensure_ascii=False), json.dumps(detail, ensure_ascii=False)))

    def history(self, query: str = '', limit: int = 20, offset: int = 0) -> list[dict]:
        search = '%' + query.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'
        with self.connect() as db:
            rows = db.execute("""SELECT summary, EXISTS(SELECT 1 FROM recordings WHERE recordings.session_id=readings.session_id) FROM readings
                WHERE learner LIKE ? ESCAPE '!' OR passage_title LIKE ? ESCAPE '!'
                ORDER BY timestamp DESC, rowid DESC LIMIT ? OFFSET ?""", (search, search, limit, offset))
            return [dict(json.loads(row[0]), has_recording=bool(row[1])) for row in rows]

    def reading(self, session_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute('SELECT summary, detail FROM readings WHERE session_id=?', (session_id,)).fetchone()
        if row is None:
            return None
        return dict(summary=json.loads(row[0]), reading=json.loads(row[1]) if row[1] else None, recordings=self.recordings(session_id))

    def recordings(self, session_id: str) -> list[dict]:
        with self.connect() as db:
            return [dict(segment_id=r[0], time_offset=r[1], duration=r[2]) for r in db.execute(
                'SELECT segment_id, time_offset, duration FROM recordings WHERE session_id=? ORDER BY time_offset, rowid', (session_id,))]

    def save_recording(self, session_id: str, segment_id: str, offset: float, duration: float, wav: bytes):
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM readings WHERE session_id=?', (session_id,)).fetchone():
                return False
            db.execute('INSERT INTO recordings VALUES (?, ?, ?, ?, ?) ON CONFLICT(session_id, segment_id) DO UPDATE SET time_offset=excluded.time_offset, duration=excluded.duration, wav=excluded.wav',
                       (session_id, segment_id, offset, duration, wav))
        return True

    def recording(self, session_id: str, segment_id: str) -> bytes | None:
        with self.connect() as db:
            row = db.execute('SELECT wav FROM recordings WHERE session_id=? AND segment_id=?', (session_id, segment_id)).fetchone()
        return bytes(row[0]) if row else None

    def delete_recordings(self, session_id: str):
        with self.connect() as db:
            db.execute('DELETE FROM recordings WHERE session_id=?', (session_id,))

    def backup(self) -> bytes:
        """SQLite backup includes committed WAL changes in a portable snapshot."""
        with self.connect() as source:
            target = sqlite3.connect(':memory:')
            try:
                source.backup(target)
                return target.serialize()
            finally:
                target.close()
