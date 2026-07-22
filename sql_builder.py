import sqlite3
from contextlib import closing
from pathlib import Path

from models import db


DATABASE_PATH = Path(__file__).resolve().parent / "data" / "movies.db"
DATABASE_BACKUP_PATH = DATABASE_PATH.with_suffix(".db.pre-migration.bak")


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


def migrate_database(flask_app):
    """Apply pending SQLite schema migrations and ensure all tables exist."""
    _migrate_movie_imdb_uniqueness()

    with flask_app.app_context():
        db.create_all()


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
