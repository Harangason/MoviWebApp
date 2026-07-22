import os

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
                movie = _movie_from_omdb(search_result["imdbID"], user_id)
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
        users=data_manager.get_users(),
    )


@app.route("/add_movie/save", methods=["POST"])
def save_movie():
    imdb_id = request.form.get("imdb_id", "").strip()
    user_id_text = request.form.get("user_id", "").strip()

    if not imdb_id or not user_id_text.isdigit():
        abort(400)

    user_id = int(user_id_text)
    if data_manager.get_user(user_id) is None:
        abort(404)

    result = None
    try:
        result = get_movie_by_id(imdb_id)
        movie = _movie_from_omdb(imdb_id, user_id, result=result)
        data_manager.add_movie(movie)
    except DuplicateMovieError as duplicate_error:
        return (
            render_template(
                "add_movie.html",
                movies=[result] if result else [],
                query=result.get("Title", "") if result else "",
                error=str(duplicate_error),
                user_id=user_id,
                users=data_manager.get_users(),
            ),
            409,
        )
    except (OMDbAPIError, KeyError, ValueError) as api_error:
        return (
            render_template(
                "add_movie.html",
                movies=[],
                query="",
                error=str(api_error) or "Filmdaten konnten nicht geladen werden.",
                user_id=user_id,
                users=data_manager.get_users(),
            ),
            502,
        )

    return redirect(url_for("user_detail", user_id=user_id))


def _movie_from_omdb(imdb_id, user_id, result=None):
    """Build a Movie model from one detailed OMDb response."""
    result = result or get_movie_by_id(imdb_id)
    year_text = result.get("Year", "")
    year = int(year_text[:4]) if year_text[:4].isdigit() else None
    rating_text = result.get("imdbRating")
    rating = (
        float(rating_text)
        if rating_text and rating_text != "N/A"
        else None
    )
    director = result.get("Director")
    poster = result.get("Poster")

    return Movie(
        title=result["Title"],
        director=director if director and director != "N/A" else None,
        year=year,
        rating=rating,
        poster_url=poster if poster and poster != "N/A" else None,
        imdb_id=result.get("imdbID") or imdb_id,
        user_id=user_id,
    )

def main():
    if database_exists():
        configure_database(app)
        migrate_database(app)
    else:
        initialize_database(app)

    host = os.getenv("MOVIWEB_HOST", "127.0.0.1")
    port = int(os.getenv("MOVIWEB_PORT", "5001"))
    debug = os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}
    app.run(host=host, port=port, debug=debug)




if __name__ == "__main__":
    main()
