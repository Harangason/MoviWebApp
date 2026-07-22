import os

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

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
app.secret_key = os.getenv("MOVIWEB_SECRET_KEY", "local-moviweb-session-key")
data_manager = DataManager()


@app.errorhandler(404)
def page_not_found(error):
    if request.path.startswith("/api/"):
        return jsonify(error="Nicht gefunden."), 404
    return render_template("404.html"), 404


@app.errorhandler(DataManagerError)
def handle_database_error(error):
    app.logger.error("Database operation failed: %s", error, exc_info=True)
    if request.path.startswith("/api/"):
        return jsonify(error=str(error)), 500
    return render_template("500.html"), 500


@app.errorhandler(500)
def internal_server_error(error):
    app.logger.error("Unexpected server error: %s", error, exc_info=True)
    if request.path.startswith("/api/"):
        return jsonify(error="Interner Serverfehler."), 500
    return render_template("500.html"), 500



@app.route("/")
def index():
    return render_template("index.html", users=data_manager.get_users())


@app.route("/users", methods=["POST"])
def create_user():
    name = request.form.get("name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    if name:
        data_manager.create_user(name, last_name)
    return redirect(url_for("index"))


@app.route("/users/<int:user_id>/update", methods=["POST"])
def update_user(user_id):
    name = request.form.get("name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    if not name:
        flash("Der Vorname darf nicht leer sein.", "error")
        return redirect(url_for("index"))
    result = data_manager.update_user(user_id, name, last_name)
    if result is None:
        abort(404)
    if result is False:
        flash("Ein Profil mit diesem Namen existiert bereits.", "error")
    else:
        flash("Das Profil wurde aktualisiert.", "success")
    return redirect(url_for("index"))


@app.route("/users/<int:user_id>/delete", methods=["POST"])
def delete_user(user_id):
    if not data_manager.delete_user(user_id):
        abort(404)
    if session.get("active_user_id") == user_id:
        session.pop("active_user_id", None)
    flash("Das Profil und seine Filmsammlung wurden gelöscht.", "success")
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

    filters, filter_error = _collection_filters(request.args)
    if filter_error and error is None:
        error = filter_error
        status_code = 400
    movies = data_manager.get_movies(user_id, **filters)
    random_movie = (
        data_manager.get_random_movie(user_id)
        if request.args.get("show") == "random"
        else None
    )

    return (
        render_template(
            "movies.html",
            user=user,
            movies=movies,
            stats=data_manager.get_collection_stats(user_id),
            histogram_movies=data_manager.get_movies(user_id, sort_by="rating"),
            random_movie=random_movie,
            filters=filters,
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
    note = request.form.get("note", "").strip()
    if not new_title:
        abort(400)
    if data_manager.update_movie(user_id, movie_id, new_title, note) is None:
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


@app.route("/users/<int:user_id>/favorite", methods=["POST"])
def set_favorite_movie(user_id):
    movie_id_text = request.form.get("movie_id", "").strip()
    movie_id = int(movie_id_text) if movie_id_text.isdigit() else None
    result = data_manager.set_favorite_movie(user_id, movie_id)
    if result is None:
        abort(404)
    if result is False:
        abort(400)
    return redirect(url_for("user_movies", user_id=user_id))


@app.route("/users/<int:user_id>/export", methods=["GET"])
def export_collection(user_id):
    user = data_manager.get_user(user_id)
    if user is None:
        abort(404)
    response = make_response(
        render_template(
            "export.html",
            user=user,
            movies=data_manager.get_movies(user_id),
            stats=data_manager.get_collection_stats(user_id),
        )
    )
    response.headers["Content-Disposition"] = (
        f'attachment; filename="movies-{user_id}.html"'
    )
    return response


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


def _collection_filters(values):
    """Validate collection controls and return DataManager keyword arguments."""
    filters = {
        "search": values.get("search", "").strip(),
        "sort_by": values.get("sort", "title").strip(),
        "min_rating": None,
        "start_year": None,
        "end_year": None,
    }
    if filters["sort_by"] not in {"title", "rating", "year"}:
        filters["sort_by"] = "title"
    try:
        if values.get("min_rating", "").strip():
            filters["min_rating"] = float(values["min_rating"])
        if values.get("start_year", "").strip():
            filters["start_year"] = int(values["start_year"])
        if values.get("end_year", "").strip():
            filters["end_year"] = int(values["end_year"])
    except (TypeError, ValueError):
        return filters, "Bitte verwende gültige Zahlen für Bewertung und Jahre."
    if (
        filters["start_year"] is not None
        and filters["end_year"] is not None
        and filters["start_year"] > filters["end_year"]
    ):
        return filters, "Das Startjahr darf nicht nach dem Endjahr liegen."
    return filters, None


def _movie_payload(movie):
    return {
        "id": movie.id,
        "title": movie.title,
        "director": movie.director,
        "year": movie.year,
        "rating": movie.rating,
        "poster": movie.poster_url,
        "poster_url": movie.poster_url,
        "imdb_id": movie.imdb_id,
        "note": movie.note,
        "user_id": movie.user_id,
    }


def _user_payload(user):
    return {
        "id": user.id,
        "name": user.name,
        "last_name": user.last_name,
        "display_name": user.display_name,
        "favorite_movie_id": user.favorite_movie_id,
        "movie_count": len(user.movies),
    }


def _stats_payload(stats):
    return {
        "count": stats["count"],
        "average_rating": stats["average_rating"],
        "median_rating": stats["median_rating"],
        "earliest_year": stats["earliest_year"],
        "latest_year": stats["latest_year"],
        "best_movie": (
            _movie_payload(stats["best_movie"]) if stats["best_movie"] else None
        ),
        "worst_movie": (
            _movie_payload(stats["worst_movie"]) if stats["worst_movie"] else None
        ),
    }


def _active_api_user(payload=None):
    payload = payload or {}
    candidate = request.args.get("user_id") or payload.get("user_id")
    if candidate is not None and str(candidate).isdigit():
        user = data_manager.get_user(int(candidate))
    else:
        user = data_manager.get_user(session.get("active_user_id"))
        if user is None:
            users = data_manager.get_users()
            user = users[0] if users else None
    if user:
        session["active_user_id"] = user.id
    return user


def _api_error(message, status=400):
    return jsonify(error=message), status


@app.route("/api/users", methods=["GET", "POST"])
def api_users():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name", "")).strip()
        if not name:
            return _api_error("Ein Vorname ist erforderlich.")
        user = data_manager.create_user(
            name,
            str(payload.get("last_name", "")).strip(),
        )
        return jsonify(_user_payload(user)), 201
    return jsonify(users=[_user_payload(user) for user in data_manager.get_users()])


@app.route("/api/users/<int:user_id>", methods=["GET", "PATCH", "PUT", "DELETE"])
def api_user_detail(user_id):
    user = data_manager.get_user(user_id)
    if user is None:
        abort(404)
    if request.method == "GET":
        return jsonify(user=_user_payload(user))
    if request.method == "DELETE":
        data_manager.delete_user(user_id)
        if session.get("active_user_id") == user_id:
            session.pop("active_user_id", None)
        return "", 204

    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    if not name:
        return _api_error("Ein Vorname ist erforderlich.")
    result = data_manager.update_user(
        user_id,
        name,
        str(payload.get("last_name", "")).strip(),
    )
    if result is False:
        return _api_error("Ein Profil mit diesem Namen existiert bereits.", 409)
    return jsonify(user=_user_payload(result))


@app.route("/api/users/active", methods=["GET", "POST"])
def api_active_user():
    payload = request.get_json(silent=True) or {}
    if request.method == "POST":
        candidate = payload.get("id")
        if not str(candidate).isdigit():
            return _api_error("Eine gültige Nutzer-ID ist erforderlich.")
        user = data_manager.get_user(int(candidate))
        if user is None:
            abort(404)
        session["active_user_id"] = user.id
    else:
        user = _active_api_user()
    if user is None:
        return _api_error("Es ist kein Nutzer vorhanden.", 404)
    return jsonify(_user_payload(user))


@app.route("/api/movies", methods=["GET"])
@app.route("/api/users/<int:user_id>/movies", methods=["GET"])
def api_movies(user_id=None):
    user = data_manager.get_user(user_id) if user_id else _active_api_user()
    if user is None:
        abort(404)
    filters, error = _collection_filters(request.args)
    if error:
        return _api_error(error)
    movies = data_manager.get_movies(user.id, **filters)
    return jsonify(user=_user_payload(user), movies=[_movie_payload(m) for m in movies])


@app.route("/api/users/<int:user_id>/movies", methods=["POST"])
def api_add_movie(user_id):
    if data_manager.get_user(user_id) is None:
        abort(404)
    payload = request.get_json(silent=True) or {}
    imdb_id = str(payload.get("imdb_id", "")).strip()
    title = str(payload.get("title", "")).strip()
    try:
        if not imdb_id:
            if not title:
                return _api_error("Filmtitel oder IMDb-ID ist erforderlich.")
            results = search_movies(title)
            if not results:
                return _api_error("Kein Film gefunden.", 404)
            imdb_id = results[0]["imdbID"]
        movie = _movie_from_omdb(imdb_id, user_id)
        movie.note = str(payload.get("note", "")).strip() or None
        data_manager.add_movie(movie)
    except DuplicateMovieError as error:
        return _api_error(str(error), 409)
    except (OMDbAPIError, IndexError, KeyError, ValueError) as error:
        return _api_error(str(error) or "Filmdaten konnten nicht geladen werden.", 502)
    return jsonify(movie=_movie_payload(movie)), 201


@app.route(
    "/api/users/<int:user_id>/movies/<int:movie_id>",
    methods=["PATCH", "PUT", "DELETE"],
)
def api_movie_detail(user_id, movie_id):
    if request.method == "DELETE":
        if not data_manager.delete_movie(user_id, movie_id):
            abort(404)
        return "", 204
    payload = request.get_json(silent=True) or {}
    title = payload.get("title")
    note = payload.get("note")
    if title is not None:
        title = str(title).strip()
        if not title:
            return _api_error("Der Titel darf nicht leer sein.")
    movie = data_manager.update_movie(user_id, movie_id, title, note)
    if movie is None:
        abort(404)
    return jsonify(movie=_movie_payload(movie))


@app.route("/api/users/<int:user_id>/favorite", methods=["POST"])
def api_favorite(user_id):
    payload = request.get_json(silent=True) or {}
    movie_id = payload.get("movie_id")
    if movie_id is not None and not str(movie_id).isdigit():
        return _api_error("Ungültige Film-ID.")
    result = data_manager.set_favorite_movie(
        user_id,
        int(movie_id) if movie_id is not None else None,
    )
    if result is None:
        abort(404)
    if result is False:
        return _api_error("Der Film gehört nicht zu diesem Nutzer.")
    return jsonify(user=_user_payload(data_manager.get_user(user_id)))


@app.route("/api/movies/stats")
@app.route("/api/users/<int:user_id>/movies/stats")
def api_movie_stats(user_id=None):
    user = data_manager.get_user(user_id) if user_id else _active_api_user()
    if user is None:
        abort(404)
    return jsonify(stats=_stats_payload(data_manager.get_collection_stats(user.id)))


@app.route("/api/movies/random")
@app.route("/api/users/<int:user_id>/movies/random")
def api_random_movie(user_id=None):
    user = data_manager.get_user(user_id) if user_id else _active_api_user()
    if user is None:
        abort(404)
    movie = data_manager.get_random_movie(user.id)
    return jsonify(movie=_movie_payload(movie) if movie else None)


@app.route("/api/movies/sorted")
@app.route("/api/movies/histogram")
@app.route("/api/movies/search")
@app.route("/api/movies/filter")
def api_legacy_movie_views():
    user = _active_api_user()
    if user is None:
        abort(404)
    values = request.args.to_dict()
    if request.path.endswith("/sorted"):
        values["sort"] = values.get("by", "title")
    elif request.path.endswith("/histogram"):
        values["sort"] = "rating"
    elif request.path.endswith("/search"):
        values["search"] = values.get("term", "")
    filters, error = _collection_filters(values)
    if error:
        return _api_error(error)
    return jsonify(
        movies=[
            _movie_payload(movie)
            for movie in data_manager.get_movies(user.id, **filters)
        ]
    )


@app.route("/api/movies/add", methods=["POST"])
def api_legacy_add_movie():
    user = _active_api_user(request.get_json(silent=True) or {})
    if user is None:
        abort(404)
    return api_add_movie(user.id)


@app.route("/api/movies/delete", methods=["POST"])
def api_legacy_delete_movie():
    payload = request.get_json(silent=True) or {}
    user = _active_api_user(payload)
    movie = data_manager.get_movie_by_title(user.id, str(payload.get("title", ""))) if user else None
    if movie is None:
        abort(404)
    data_manager.delete_movie(user.id, movie.id)
    return jsonify(deleted=True)


@app.route("/api/movies/update", methods=["POST"])
def api_legacy_update_movie():
    payload = request.get_json(silent=True) or {}
    user = _active_api_user(payload)
    movie = data_manager.get_movie_by_title(user.id, str(payload.get("title", ""))) if user else None
    if movie is None:
        abort(404)
    data_manager.update_movie(user.id, movie.id, note=str(payload.get("note", "")))
    return jsonify(movie=_movie_payload(movie))

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
