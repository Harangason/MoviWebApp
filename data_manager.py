from models import db, User, Movie
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

    def create_user(self, name):
        user = User(name=name)
        db.session.add(user)
        self._commit()
        return user

    def get_users(self):
        try:
            return User.query.all()
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

    def get_movies(self, user_id):
        try:
            return Movie.query.filter_by(user_id=user_id).all()
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

        return {
            "count": count,
            "average_rating": (
                round(average_rating, 1)
                if average_rating is not None
                else None
            ),
            "earliest_year": earliest_year,
            "latest_year": latest_year,
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

    def update_movie(self, user_id, movie_id, new_title):
        movie = self.get_movie(user_id, movie_id)
        if movie is None:
            return None
        movie.title = new_title
        self._commit()
        return movie

    def delete_movie(self, user_id, movie_id):
        movie = self.get_movie(user_id, movie_id)
        if movie is None:
            return False
        db.session.delete(movie)
        self._commit()
        return True

