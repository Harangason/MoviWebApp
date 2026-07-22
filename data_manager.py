from models import db, User, Movie
import random
import statistics

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


class DataManagerError(Exception):
    """Raised when a database operation cannot be completed."""


class DuplicateMovieError(DataManagerError):
    """Raised when a movie already exists in the database."""


class DataManager:
    @staticmethod
    def _commit(duplicate_message=None):
        try:
            db.session.commit()
        except IntegrityError as error:
            db.session.rollback()
            if duplicate_message:
                raise DuplicateMovieError(duplicate_message) from error
            raise DataManagerError(
                "Die Datenbankänderung verletzt eine Eindeutigkeitsregel."
            ) from error
        except SQLAlchemyError as error:
            db.session.rollback()
            raise DataManagerError(
                "Die Datenbankänderung konnte nicht gespeichert werden."
            ) from error

    def create_user(self, name, last_name=""):
        name = name.strip()
        last_name = last_name.strip()
        existing = User.query.filter_by(name=name, last_name=last_name).first()
        if existing:
            return existing
        user = User(name=name, last_name=last_name)
        db.session.add(user)
        self._commit()
        return user

    def get_users(self):
        try:
            return User.query.order_by(User.name, User.last_name).all()
        except SQLAlchemyError as error:
            db.session.rollback()
            raise DataManagerError(
                "Die Nutzer konnten nicht geladen werden."
            ) from error

    def get_user(self, user_id):
        try:
            return db.session.get(User, user_id)
        except SQLAlchemyError as error:
            db.session.rollback()
            raise DataManagerError(
                "Der Nutzer konnte nicht geladen werden."
            ) from error

    def update_user(self, user_id, name, last_name=""):
        user = self.get_user(user_id)
        if user is None:
            return None
        name = name.strip()
        last_name = last_name.strip()
        duplicate = User.query.filter(
            User.id != user_id,
            func.lower(User.name) == name.lower(),
            func.lower(User.last_name) == last_name.lower(),
        ).first()
        if duplicate:
            return False
        user.name = name
        user.last_name = last_name
        self._commit()
        return user

    def delete_user(self, user_id):
        user = self.get_user(user_id)
        if user is None:
            return False
        user.favorite_movie_id = None
        db.session.flush()
        db.session.delete(user)
        self._commit()
        return True

    def get_movies(
        self,
        user_id,
        search="",
        min_rating=None,
        start_year=None,
        end_year=None,
        sort_by="title",
    ):
        try:
            query = Movie.query.filter_by(user_id=user_id)
            if search:
                query = query.filter(Movie.title.ilike(f"%{search}%"))
            if min_rating is not None:
                query = query.filter(Movie.rating >= min_rating)
            if start_year is not None:
                query = query.filter(Movie.year >= start_year)
            if end_year is not None:
                query = query.filter(Movie.year <= end_year)

            orderings = {
                "rating": (Movie.rating.desc(), Movie.title.asc()),
                "year": (Movie.year.desc(), Movie.title.asc()),
                "title": (Movie.title.asc(),),
            }
            return query.order_by(*orderings.get(sort_by, orderings["title"])).all()
        except SQLAlchemyError as error:
            db.session.rollback()
            raise DataManagerError(
                "Die Filme konnten nicht geladen werden."
            ) from error

    def get_collection_stats(self, user_id):
        """Return compact aggregate data for a user's collection."""
        try:
            count, average_rating, earliest_year, latest_year = (
                db.session.query(
                    func.count(Movie.id),
                    func.avg(Movie.rating),
                    func.min(Movie.year),
                    func.max(Movie.year),
                )
                .filter(Movie.user_id == user_id)
                .one()
            )
        except SQLAlchemyError as error:
            db.session.rollback()
            raise DataManagerError(
                "Die Sammlungsstatistik konnte nicht geladen werden."
            ) from error

        movies = self.get_movies(user_id, sort_by="rating")
        rated_movies = [movie for movie in movies if movie.rating is not None]
        ratings = [movie.rating for movie in rated_movies]
        return {
            "count": count,
            "average_rating": (
                round(average_rating, 1)
                if average_rating is not None
                else None
            ),
            "earliest_year": earliest_year,
            "latest_year": latest_year,
            "median_rating": round(statistics.median(ratings), 1) if ratings else None,
            "best_movie": rated_movies[0] if rated_movies else None,
            "worst_movie": rated_movies[-1] if rated_movies else None,
        }

    def get_movie(self, user_id, movie_id):
        try:
            return Movie.query.filter_by(id=movie_id, user_id=user_id).first()
        except SQLAlchemyError as error:
            db.session.rollback()
            raise DataManagerError(
                "Der Film konnte nicht geladen werden."
            ) from error

    def add_movie(self, movie):
        db.session.add(movie)
        self._commit("Dieser Film ist bereits in der Sammlung vorhanden.")
        return movie

    def update_movie(self, user_id, movie_id, new_title=None, note=None):
        movie = self.get_movie(user_id, movie_id)
        if movie is None:
            return None
        if new_title is not None:
            movie.title = new_title
        if note is not None:
            movie.note = note or None
        self._commit()
        return movie

    def delete_movie(self, user_id, movie_id):
        movie = self.get_movie(user_id, movie_id)
        if movie is None:
            return False
        user = self.get_user(user_id)
        if user and user.favorite_movie_id == movie.id:
            user.favorite_movie_id = None
        db.session.delete(movie)
        self._commit()
        return True

    def get_movie_by_title(self, user_id, title):
        try:
            return Movie.query.filter(
                Movie.user_id == user_id,
                func.lower(Movie.title) == title.strip().lower(),
            ).first()
        except SQLAlchemyError as error:
            db.session.rollback()
            raise DataManagerError("Der Film konnte nicht geladen werden.") from error

    def get_random_movie(self, user_id):
        movies = self.get_movies(user_id)
        return random.choice(movies) if movies else None

    def set_favorite_movie(self, user_id, movie_id):
        user = self.get_user(user_id)
        if user is None:
            return None
        if movie_id is not None and self.get_movie(user_id, movie_id) is None:
            return False
        user.favorite_movie_id = movie_id
        self._commit()
        return True

