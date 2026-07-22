from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    movies = db.relationship(
        "Movie",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan",
    )


class Movie(db.Model):
    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "imdb_id",
            name="uq_movie_user_imdb",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    director = db.Column(db.String(200))
    year = db.Column(db.Integer)
    rating = db.Column(db.Float)
    poster_url = db.Column(db.String(500))
    imdb_id = db.Column(db.String(20))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
