from models import db, User, Movie


class DataManager:
    def create_user(self, name):
        user = User(name=name)
        db.session.add(user)
        db.session.commit()
        return user

    def get_users(self):
        return User.query.all()

    def get_user(self, user_id):
        return db.session.get(User, user_id)

    def get_movies(self, user_id):
        return Movie.query.filter_by(user_id=user_id).all()

    def get_movie(self, user_id, movie_id):
        return Movie.query.filter_by(id=movie_id, user_id=user_id).first()

    def add_movie(self, movie):
        db.session.add(movie)
        db.session.commit()
        return movie

    def update_movie(self, user_id, movie_id, new_title):
        movie = self.get_movie(user_id, movie_id)
        if movie is None:
            return None
        movie.title = new_title
        db.session.commit()
        return movie

    def delete_movie(self, user_id, movie_id):
        movie = self.get_movie(user_id, movie_id)
        if movie is None:
            return False
        db.session.delete(movie)
        db.session.commit()
        return True

