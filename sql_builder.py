from pathlib import Path

from models import db


DATABASE_PATH = Path(__file__).resolve().parent / "data" / "movies.db"


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
