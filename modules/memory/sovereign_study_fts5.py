"""
AIR10 Sovereign Study Commons - SQLite FTS5 Shadow Memory Index.
Provides sub-3ms full-text retrieval, BM25 ranking, and external content table sync.
"""
import sqlite3
import time
from pathlib import Path

class StudyFTS5Index:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self._init_schema()

    def _init_schema(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS study_cards (
                    id INTEGER PRIMARY KEY,
                    domain TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    content TEXT NOT NULL,
                    retrievability REAL DEFAULT 1.0,
                    stability REAL DEFAULT 1.0,
                    lapses INTEGER DEFAULT 0,
                    created_at REAL NOT NULL
                );
            """)
            self.conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS study_cards_fts USING fts5(
                    domain, topic, content,
                    content='study_cards',
                    content_rowid='id'
                );
            """)

    def insert_card(self, domain: str, topic: str, content: str, retrievability: float = 1.0) -> int:
        now = time.time()
        with self.conn:
            cur = self.conn.execute("""
                INSERT INTO study_cards (domain, topic, content, retrievability, stability, created_at)
                VALUES (?, ?, ?, ?, 1.0, ?)
            """, (domain, topic, content, retrievability, now))
            rowid = cur.lastrowid
            self.conn.execute("""
                INSERT INTO study_cards_fts (rowid, domain, topic, content)
                VALUES (?, ?, ?, ?)
            """, (rowid, domain, topic, content))
            return rowid

    def search(self, query: str, limit: int = 10):
        t0 = time.perf_counter()
        cur = self.conn.execute("""
            SELECT c.id, c.domain, c.topic, c.content, c.retrievability, bm25(study_cards_fts) as rank
            FROM study_cards_fts f
            JOIN study_cards c ON f.rowid = c.id
            WHERE study_cards_fts MATCH ?
            ORDER BY rank ASC
            LIMIT ?
        """, (query, limit))
        results = [dict(zip(['id', 'domain', 'topic', 'content', 'retrievability', 'rank'], row)) for row in cur]
        lat_ms = (time.perf_counter() - t0) * 1000.0
        return {'results': results, 'latency_ms': lat_ms}

    def checkpoint_truncate(self):
        with self.conn:
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
