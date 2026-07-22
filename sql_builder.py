import sqlite3
from contextlib import closing
from pathlib import Path

from models import db


DATABASE_PATH = Path(__file__).resolve().parent / "data" / "movies.db"
DATABASE_BACKUP_PATH = DATABASE_PATH.with_suffix(".db.pre-migration.bak")
LEGACY_DATABASE_PATH = (
    Path(__file__).resolve().parents[2]
    / "Term_3"
    / "Movie_SQL_HTML_API"
    / "data"
    / "movies.db"
)


def database_exists():
    """Return True if the SQLite database file already exists."""
    return DATABASE_PATH.is_file()


def configure_database(flask_app):
    """Connect the Flask application to the existing SQLite database."""
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"sqlite:///{DATABASE_PATH.as_posix()}"
    )
    flask_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(flask_app)


def initialize_database(flask_app):
    """Create the data directory, database file, and all declared tables."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    configure_database(flask_app)

    with flask_app.app_context():
        db.create_all()
    _import_legacy_term3_data()


def migrate_database(flask_app):
    """Apply pending SQLite schema migrations and ensure all tables exist."""
    _migrate_movie_imdb_uniqueness()
    _add_full_feature_columns()

    with flask_app.app_context():
        db.create_all()

    _import_legacy_term3_data()


def _add_full_feature_columns():
    """Add fields used by the complete web feature set to older databases."""
    if not DATABASE_PATH.is_file():
        return

    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        user_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(user)")
        }
        movie_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(movie)")
        }
        changes = []
        if "last_name" not in user_columns:
            changes.append("ALTER TABLE user ADD COLUMN last_name VARCHAR(100) NOT NULL DEFAULT ''")
        if "favorite_movie_id" not in user_columns:
            changes.append("ALTER TABLE user ADD COLUMN favorite_movie_id INTEGER")
        if "note" not in movie_columns:
            changes.append("ALTER TABLE movie ADD COLUMN note TEXT")

        if changes:
            _backup_database()
            for statement in changes:
                connection.execute(statement)
            connection.commit()


def _import_legacy_term3_data():
    """Import the shared Term 3 catalogue once for every legacy user.

    Term 3 exposed one global catalogue to every user. Term 4 owns movies per
    user, so copying the catalogue into each imported collection preserves the
    behavior users had before the migration.
    """
    if not DATABASE_PATH.is_file() or not LEGACY_DATABASE_PATH.is_file():
        return

    with (
        closing(sqlite3.connect(DATABASE_PATH)) as target,
        closing(sqlite3.connect(LEGACY_DATABASE_PATH)) as source,
    ):
        target.execute(
            "CREATE TABLE IF NOT EXISTS migration_state (key TEXT PRIMARY KEY)"
        )
        target.commit()
        marker = "legacy_term3_full_import_v1"
        if target.execute(
            "SELECT 1 FROM migration_state WHERE key = ?", (marker,)
        ).fetchone():
            return

        _backup_database()
        legacy_users = source.execute(
            "SELECT id, name, COALESCE(last_name, ''), my_favorite_movie FROM users"
        ).fetchall()
        legacy_movies = source.execute(
            "SELECT id, title, year, rating, poster, note, imdb_id FROM movies"
        ).fetchall()

        for _, first_name, last_name, favorite_legacy_id in legacy_users:
            row = target.execute(
                "SELECT id FROM user WHERE name = ? AND last_name = ?",
                (first_name, last_name),
            ).fetchone()
            if row:
                user_id = row[0]
            else:
                cursor = target.execute(
                    "INSERT INTO user (name, last_name) VALUES (?, ?)",
                    (first_name, last_name),
                )
                user_id = cursor.lastrowid

            imported_ids = {}
            for legacy_id, title, year, rating, poster, note, imdb_id in legacy_movies:
                existing = None
                if imdb_id:
                    existing = target.execute(
                        "SELECT id FROM movie WHERE user_id = ? AND imdb_id = ?",
                        (user_id, imdb_id),
                    ).fetchone()
                if not existing:
                    existing = target.execute(
                        "SELECT id FROM movie WHERE user_id = ? AND title = ? AND year = ?",
                        (user_id, title, year),
                    ).fetchone()
                if existing:
                    movie_id = existing[0]
                else:
                    cursor = target.execute(
                        """
                        INSERT INTO movie (
                            title, director, year, rating, poster_url,
                            imdb_id, note, user_id
                        ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?)
                        """,
                        (title, year, rating, poster, imdb_id, note, user_id),
                    )
                    movie_id = cursor.lastrowid
                imported_ids[legacy_id] = movie_id

            if favorite_legacy_id in imported_ids:
                target.execute(
                    "UPDATE user SET favorite_movie_id = ? WHERE id = ?",
                    (imported_ids[favorite_legacy_id], user_id),
                )

        target.execute("INSERT INTO migration_state (key) VALUES (?)", (marker,))
        target.commit()


def _migrate_movie_imdb_uniqueness():
    """Replace global IMDb uniqueness with uniqueness per user."""
    if not DATABASE_PATH.is_file():
        return

    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'movie'"
        ).fetchone()
        if not table_exists:
            return

        unique_indexes = []
        for index in connection.execute("PRAGMA index_list(movie)").fetchall():
            if not index[2]:
                continue
            columns = [
                column[2]
                for column in connection.execute(
                    f"PRAGMA index_info('{index[1]}')"
                ).fetchall()
            ]
            unique_indexes.append(columns)

    if ["imdb_id"] not in unique_indexes:
        return

    _backup_database()

    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE movie_new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    director VARCHAR(200),
                    year INTEGER,
                    rating FLOAT,
                    poster_url VARCHAR(500),
                    imdb_id VARCHAR(20),
                    user_id INTEGER NOT NULL,
                    CONSTRAINT uq_movie_user_imdb UNIQUE (user_id, imdb_id),
                    FOREIGN KEY(user_id) REFERENCES user (id)
                )
                """
            )
            connection.execute(
                """
                INSERT INTO movie_new (
                    id, title, director, year, rating,
                    poster_url, imdb_id, user_id
                )
                SELECT
                    id, title, director, year, rating,
                    poster_url, imdb_id, user_id
                FROM movie
                """
            )
            connection.execute("DROP TABLE movie")
            connection.execute("ALTER TABLE movie_new RENAME TO movie")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.execute("PRAGMA foreign_keys = ON")


def _backup_database():
    """Create one consistent backup before the first schema migration."""
    if DATABASE_BACKUP_PATH.exists():
        return

    with (
        closing(sqlite3.connect(DATABASE_PATH)) as source,
        closing(sqlite3.connect(DATABASE_BACKUP_PATH)) as target,
    ):
        source.backup(target)
