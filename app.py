from flask import Flask, abort, redirect, render_template, request, url_for

from data_manager import DataManager, DataManagerError, DuplicateMovieError
from models import Movie
from omdb_api import OMDbAPIError, get_movie_by_id, search_movies
from sql_builder import (
    configure_database,
    database_exists,
    initialize_database,
    migrate_database,
)

app = Flask(__name__)
data_manager = DataManager()


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(DataManagerError)
def handle_database_error(error):
    app.logger.error("Database operation failed: %s", error, exc_info=True)
    return render_template("500.html"), 500


@app.errorhandler(500)
def internal_server_error(error):
    app.logger.error("Unexpected server error: %s", error, exc_info=True)
    return render_template("500.html"), 500



@app.route("/")
def index():
    return render_template("index.html", users=data_manager.get_users())


@app.route("/users", methods=["POST"])
def create_user():
    name = request.form.get("name", "").strip()
    if name:
        data_manager.create_user(name)
    return redirect(url_for("index"))


@app.route("/users/<int:user_id>", methods=["GET"])
def user_detail(user_id):
    return user_movies(user_id)


@app.route("/users/<int:user_id>/movies", methods=["GET", "POST"])
def user_movies(user_id):
    user = data_manager.get_user(user_id)
    if user is None:
        abort(404)

    error = None
    status_code = 200
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            error = "Bitte gib einen Filmtitel ein."
            status_code = 400
        else:
            try:
                search_result = search_movies(title)[0]
                result = get_movie_by_id(search_result["imdbID"])
                year_text = result.get("Year", "")
                year = int(year_text[:4]) if year_text[:4].isdigit() else None
                rating_text = result.get("imdbRating", "")
                rating = float(rating_text) if rating_text != "N/A" else None
                poster = result.get("Poster")
                movie = Movie(
                    title=result["Title"],
                    director=(
                        result.get("Director")
                        if result.get("Director") != "N/A"
                        else None
                    ),
                    year=year,
                    rating=rating,
                    poster_url=poster if poster != "N/A" else None,
                    imdb_id=result.get("imdbID"),
                    user_id=user_id,
                )
                data_manager.add_movie(movie)
                return redirect(url_for("user_movies", user_id=user_id))
            except DuplicateMovieError as duplicate_error:
                error = str(duplicate_error)
                status_code = 409
            except (OMDbAPIError, IndexError, KeyError, ValueError) as api_error:
                error = str(api_error) or "Kein Film gefunden."

    return (
        render_template(
            "movies.html",
            user=user,
            movies=data_manager.get_movies(user_id),
            error=error,
        ),
        status_code,
    )


@app.route(
    "/users/<int:user_id>/movies/<int:movie_id>/update",
    methods=["POST"],
)
def update_movie(user_id, movie_id):
    new_title = request.form.get("title", "").strip()
    if not new_title:
        abort(400)
    if data_manager.update_movie(user_id, movie_id, new_title) is None:
        abort(404)
    return redirect(url_for("user_movies", user_id=user_id))


@app.route(
    "/users/<int:user_id>/movies/<int:movie_id>/delete",
    methods=["POST"],
)
def delete_movie(user_id, movie_id):
    if not data_manager.delete_movie(user_id, movie_id):
        abort(404)
    return redirect(url_for("user_movies", user_id=user_id))


@app.route("/add_movie", methods=["GET", "POST"])
@app.route("/users/<int:user_id>/add_movie", methods=["GET", "POST"])
def add_movie(user_id=None):
    query = request.values.get("query", "").strip()
    movies = []
    error = None

    if query:
        try:
            movies = search_movies(query)
        except OMDbAPIError as api_error:
            error = str(api_error)
    elif request.method == "POST":
        error = "Bitte gib einen Filmtitel ein."

    return render_template(
        "add_movie.html",
        movies=movies,
        query=query,
        error=error,
        user_id=user_id,
    )

def main():
    if database_exists():
        configure_database(app)
        migrate_database(app)
    else:
        initialize_database(app)

    app.run(debug=True)




if __name__ == "__main__":
    main()
