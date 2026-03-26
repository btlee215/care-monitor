import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from scorer import ScoredPost


class Database:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS surfaced_posts (
                post_id TEXT PRIMARY KEY,
                subreddit TEXT,
                tier INTEGER,
                title TEXT,
                url TEXT,
                author TEXT,
                score INTEGER,
                priority_label TEXT,
                reason TEXT,
                body_snippet TEXT,
                created_utc REAL,
                surfaced_at TEXT
            );

            CREATE TABLE IF NOT EXISTS subreddit_activity (
                subreddit TEXT PRIMARY KEY,
                last_match_at TEXT,
                last_checked_at TEXT
            );

            CREATE TABLE IF NOT EXISTS engagement_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT,
                post_url TEXT,
                subreddit TEXT,
                responded_at TEXT,
                response_text TEXT,
                notes TEXT
            );
        """)
        self.conn.commit()

    def is_seen(self, post_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM surfaced_posts WHERE post_id = ?", (post_id,)
        ).fetchone()
        return row is not None

    def record_surfaced(self, post: ScoredPost):
        now = datetime.now(tz=timezone.utc).isoformat()
        snippet = post.body[:200] if post.body else ""
        self.conn.execute(
            """INSERT OR IGNORE INTO surfaced_posts
               (post_id, subreddit, tier, title, url, author, score, priority_label,
                reason, body_snippet, created_utc, surfaced_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                post.post_id, post.subreddit, post.tier, post.title, post.url,
                post.author, post.score, post.priority_label, post.reason,
                snippet, post.created_utc, now,
            ),
        )
        self.conn.commit()

    def update_subreddit_checked(self, subreddit: str, had_match: bool):
        now = datetime.now(tz=timezone.utc).isoformat()
        match_val = now if had_match else None
        self.conn.execute(
            """INSERT INTO subreddit_activity (subreddit, last_match_at, last_checked_at)
               VALUES (?, ?, ?)
               ON CONFLICT(subreddit) DO UPDATE SET
                 last_checked_at = excluded.last_checked_at,
                 last_match_at = COALESCE(excluded.last_match_at, last_match_at)""",
            (subreddit, match_val, now),
        )
        self.conn.commit()

    def get_silent_subreddits(self, days: int) -> list:
        cutoff = datetime.now(tz=timezone.utc)
        from datetime import timedelta
        cutoff = (cutoff - timedelta(days=days)).isoformat()
        rows = self.conn.execute(
            """SELECT subreddit FROM subreddit_activity
               WHERE last_match_at IS NULL OR last_match_at < ?""",
            (cutoff,),
        ).fetchall()
        return [r["subreddit"] for r in rows]

    def log_engagement(
        self,
        post_id: str,
        post_url: str,
        subreddit: str,
        response_text: str,
        notes: str,
    ):
        now = datetime.now(tz=timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO engagement_log (post_id, post_url, subreddit, responded_at, response_text, notes)
               VALUES (?,?,?,?,?,?)""",
            (post_id, post_url, subreddit, now, response_text, notes),
        )
        self.conn.commit()

    def list_engagements(self) -> list:
        rows = self.conn.execute(
            "SELECT * FROM engagement_log ORDER BY responded_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()
