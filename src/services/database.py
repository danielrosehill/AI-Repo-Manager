"""SQLite database for persistent repository storage."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models.repository import Repository


class Database:
    """SQLite database for repository metadata and sync state."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            # check_same_thread=False allows use across threads (safe with our commit-per-operation pattern)
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS repositories (
                full_name TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                pushed_at TEXT,
                is_private INTEGER NOT NULL DEFAULT 0,
                html_url TEXT,
                clone_url TEXT,
                default_branch TEXT DEFAULT 'main',
                topics TEXT,
                local_path TEXT,
                readme_content TEXT,
                last_synced TEXT,
                embedded_at TEXT,
                needs_embedding INTEGER NOT NULL DEFAULT 1,
                source TEXT DEFAULT 'github',
                source_subtype TEXT
            );

            CREATE TABLE IF NOT EXISTS sync_state (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_repos_updated ON repositories(updated_at);
            CREATE INDEX IF NOT EXISTS idx_repos_needs_embedding ON repositories(needs_embedding);
            CREATE INDEX IF NOT EXISTS idx_repos_source ON repositories(source);
        """)
        conn.commit()

        # Run migrations for existing databases
        self._migrate_db()

    def _migrate_db(self):
        """Run database migrations for existing databases."""
        conn = self._get_conn()

        # Check existing columns
        cursor = conn.execute("PRAGMA table_info(repositories)")
        rows = cursor.fetchall()
        # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
        # Access by index since row_factory might not work for PRAGMA
        columns = set()
        for row in rows:
            try:
                columns.add(row["name"])
            except (KeyError, TypeError):
                # Fallback: PRAGMA returns tuples with name at index 1
                columns.add(row[1])

        if "source" not in columns:
            try:
                conn.execute("ALTER TABLE repositories ADD COLUMN source TEXT DEFAULT 'github'")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists

        if "source_subtype" not in columns:
            try:
                conn.execute("ALTER TABLE repositories ADD COLUMN source_subtype TEXT")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def get_last_sync_time(self) -> Optional[datetime]:
        """Get the last time we synced with GitHub."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT value FROM sync_state WHERE key = 'last_sync'"
        ).fetchone()
        if row:
            return datetime.fromisoformat(row["value"])
        return None

    def set_last_sync_time(self, dt: datetime):
        """Set the last sync time."""
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO sync_state (key, value) VALUES ('last_sync', ?)",
            (dt.isoformat(),)
        )
        conn.commit()

    def get_repository(self, full_name: str) -> Optional[Repository]:
        """Get a repository by full name."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM repositories WHERE full_name = ?",
            (full_name,)
        ).fetchone()
        if row:
            return self._row_to_repo(row)
        return None

    def get_all_repositories(self) -> list[Repository]:
        """Get all repositories from the database."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM repositories ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_repo(row) for row in rows]

    def get_repos_needing_embedding(self) -> list[Repository]:
        """Get repositories that need embedding updates."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM repositories WHERE needs_embedding = 1"
        ).fetchall()
        return [self._row_to_repo(row) for row in rows]

    def upsert_repository(self, repo: Repository, from_github: bool = False):
        """Insert or update a repository."""
        conn = self._get_conn()

        # Check if repo exists and if it changed
        existing = conn.execute(
            "SELECT updated_at, pushed_at FROM repositories WHERE full_name = ?",
            (repo.full_name,)
        ).fetchone()

        needs_embedding = 1
        if existing:
            # Only re-embed if repo was updated (pushed_at changed)
            old_pushed = existing["pushed_at"]
            new_pushed = repo.created_at.isoformat()  # We'll use pushed_at when available
            if old_pushed == new_pushed and not from_github:
                needs_embedding = 0

        topics_str = ",".join(repo.topics) if repo.topics else ""

        conn.execute("""
            INSERT OR REPLACE INTO repositories (
                full_name, name, description, created_at, updated_at, pushed_at,
                is_private, html_url, clone_url, default_branch, topics,
                local_path, readme_content, last_synced, needs_embedding
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            repo.full_name,
            repo.name,
            repo.description,
            repo.created_at.isoformat(),
            repo.created_at.isoformat(),  # updated_at
            repo.created_at.isoformat(),  # pushed_at (will be updated from GitHub)
            1 if repo.is_private else 0,
            repo.html_url,
            repo.clone_url,
            repo.default_branch,
            topics_str,
            repo.local_path,
            repo.readme_content,
            datetime.now().isoformat(),
            needs_embedding,
        ))
        conn.commit()

    def upsert_from_github(
        self,
        full_name: str,
        name: str,
        description: Optional[str],
        created_at: datetime,
        updated_at: datetime,
        pushed_at: datetime,
        is_private: bool,
        html_url: str,
        clone_url: str,
        default_branch: str,
        topics: list[str],
        local_path: Optional[str] = None,
    ) -> bool:
        """
        Upsert repository from GitHub API data.
        Returns True if the repo is new or changed (needs embedding).
        """
        conn = self._get_conn()

        # Check if repo exists and if pushed_at changed
        existing = conn.execute(
            "SELECT pushed_at FROM repositories WHERE full_name = ?",
            (full_name,)
        ).fetchone()

        needs_embedding = 1
        if existing:
            old_pushed = existing["pushed_at"]
            if old_pushed == pushed_at.isoformat():
                # No changes since last sync
                needs_embedding = 0

        topics_str = ",".join(topics) if topics else ""

        conn.execute("""
            INSERT INTO repositories (
                full_name, name, description, created_at, updated_at, pushed_at,
                is_private, html_url, clone_url, default_branch, topics,
                local_path, last_synced, needs_embedding
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(full_name) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                updated_at = excluded.updated_at,
                pushed_at = excluded.pushed_at,
                is_private = excluded.is_private,
                html_url = excluded.html_url,
                clone_url = excluded.clone_url,
                default_branch = excluded.default_branch,
                topics = excluded.topics,
                local_path = COALESCE(excluded.local_path, local_path),
                last_synced = excluded.last_synced,
                needs_embedding = CASE
                    WHEN excluded.pushed_at != repositories.pushed_at THEN 1
                    ELSE repositories.needs_embedding
                END
        """, (
            full_name,
            name,
            description,
            created_at.isoformat(),
            updated_at.isoformat(),
            pushed_at.isoformat(),
            1 if is_private else 0,
            html_url,
            clone_url,
            default_branch,
            topics_str,
            local_path,
            datetime.now().isoformat(),
            needs_embedding,
        ))
        conn.commit()

        return needs_embedding == 1

    def update_readme(self, full_name: str, readme_content: str):
        """Update README content for a repository."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE repositories SET readme_content = ? WHERE full_name = ?",
            (readme_content, full_name)
        )
        conn.commit()

    def update_local_path(self, full_name: str, local_path: Optional[str]):
        """Update local path for a repository."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE repositories SET local_path = ? WHERE full_name = ?",
            (local_path, full_name)
        )
        conn.commit()

    def mark_embedded(self, full_name: str):
        """Mark a repository as embedded."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE repositories SET embedded_at = ?, needs_embedding = 0 WHERE full_name = ?",
            (datetime.now().isoformat(), full_name)
        )
        conn.commit()

    def mark_embedded_batch(self, full_names: list[str]):
        """Mark multiple repositories as embedded."""
        conn = self._get_conn()
        now = datetime.now().isoformat()
        conn.executemany(
            "UPDATE repositories SET embedded_at = ?, needs_embedding = 0 WHERE full_name = ?",
            [(now, fn) for fn in full_names]
        )
        conn.commit()

    def delete_repository(self, full_name: str):
        """Delete a repository from the database."""
        conn = self._get_conn()
        conn.execute("DELETE FROM repositories WHERE full_name = ?", (full_name,))
        conn.commit()

    def get_repo_count(self) -> int:
        """Get total number of repositories."""
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) as count FROM repositories").fetchone()
        return row["count"]

    def get_repositories_by_source(self, source: str) -> list[Repository]:
        """Get repositories filtered by source."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM repositories WHERE source = ? ORDER BY created_at DESC",
            (source,)
        ).fetchall()
        return [self._row_to_repo(row) for row in rows]

    def clear_all_embeddings(self):
        """Clear all embeddings and mark all repos as needing embedding."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE repositories SET embedded_at = NULL, needs_embedding = 1"
        )
        conn.commit()

    def delete_repositories_by_source(self, source: str):
        """Delete all repositories from a specific source."""
        conn = self._get_conn()
        conn.execute("DELETE FROM repositories WHERE source = ?", (source,))
        conn.commit()

    def upsert_local_repo(
        self,
        full_name: str,
        name: str,
        description: Optional[str],
        local_path: str,
        is_private: bool,
        source: str,
        source_subtype: Optional[str] = None,
        topics: Optional[list[str]] = None,
        html_url: Optional[str] = None,
    ) -> bool:
        """
        Upsert repository from local filesystem scan.
        Returns True if the repo is new (needs embedding).
        """
        conn = self._get_conn()
        now = datetime.now()

        # Check if repo exists
        existing = conn.execute(
            "SELECT full_name FROM repositories WHERE full_name = ?",
            (full_name,)
        ).fetchone()

        needs_embedding = 1 if not existing else 0
        topics_str = ",".join(topics) if topics else ""

        conn.execute("""
            INSERT INTO repositories (
                full_name, name, description, created_at, updated_at, pushed_at,
                is_private, html_url, clone_url, default_branch, topics,
                local_path, last_synced, needs_embedding, source, source_subtype
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(full_name) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                is_private = excluded.is_private,
                html_url = COALESCE(excluded.html_url, html_url),
                topics = COALESCE(NULLIF(excluded.topics, ''), topics),
                local_path = excluded.local_path,
                last_synced = excluded.last_synced,
                source = excluded.source,
                source_subtype = excluded.source_subtype
        """, (
            full_name,
            name,
            description,
            now.isoformat(),
            now.isoformat(),
            now.isoformat(),
            1 if is_private else 0,
            html_url,
            "",  # clone_url
            "main",
            topics_str,
            local_path,
            now.isoformat(),
            needs_embedding,
            source,
            source_subtype,
        ))
        conn.commit()

        return needs_embedding == 1

    def _row_to_repo(self, row: sqlite3.Row) -> Repository:
        """Convert database row to Repository object."""
        topics = row["topics"].split(",") if row["topics"] else []

        # Handle source column that may not exist in older databases
        try:
            source = row["source"] or "github"
        except (KeyError, IndexError):
            source = "github"

        try:
            source_subtype = row["source_subtype"]
        except (KeyError, IndexError):
            source_subtype = None

        return Repository(
            name=row["name"],
            full_name=row["full_name"],
            description=row["description"],
            created_at=datetime.fromisoformat(row["created_at"]),
            topics=topics,
            clone_url=row["clone_url"] or "",
            html_url=row["html_url"] or "",
            is_local=bool(row["local_path"]),
            local_path=row["local_path"],
            readme_content=row["readme_content"],
            is_embedded=row["embedded_at"] is not None,
            is_private=bool(row["is_private"]),
            default_branch=row["default_branch"] or "main",
            source=source,
            source_subtype=source_subtype,
        )
