from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class User(db.Model):
    __table_args__ = (
        db.UniqueConstraint("name", "last_name", name="uq_user_full_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False, default="")
    favorite_movie_id = db.Column(
        db.Integer,
        db.ForeignKey("movie.id", ondelete="SET NULL"),
        nullable=True,
    )
    movies = db.relationship(
        "Movie",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan",
        foreign_keys="Movie.user_id",
    )
    favorite_movie = db.relationship(
        "Movie",
        foreign_keys=[favorite_movie_id],
        post_update=True,
    )

    @property
    def display_name(self):
        return " ".join(part for part in (self.name, self.last_name) if part)


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
    note = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
