import os
from pathlib import Path

import requests


OMDB_URL = "https://www.omdbapi.com/"
API_KEY_FILES = (
    Path(__file__).with_name(".env"),
    Path(__file__).resolve().parents[3] / "OMDB_API_KEY.env",
)


class OMDbAPIError(Exception):
    """Raised when the OMDb search cannot be completed."""


def _get_api_key():
    api_key = os.getenv("OMDB_API_KEY", "").strip()
    if api_key:
        return api_key

    for api_key_file in API_KEY_FILES:
        if not api_key_file.exists():
            continue

        value = api_key_file.read_text(encoding="utf-8").strip()
        if "=" in value:
            name, value = value.split("=", 1)
            if name.strip() != "OMDB_API_KEY":
                value = ""
        api_key = value.strip().strip('"').strip("'")
        if api_key:
            break

    if not api_key:
        raise OMDbAPIError(
            "Der OMDb-API-Schlüssel fehlt. Setze OMDB_API_KEY oder trage ihn "
            "in der lokalen .env-Datei ein."
        )

    return api_key


def _request_omdb(params):
    """Send one authenticated request and validate the OMDb response."""
    try:
        response = requests.get(
            OMDB_URL,
            params={"apikey": _get_api_key(), **params},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as error:
        raise OMDbAPIError("OMDb ist momentan nicht erreichbar.") from error

    if data.get("Response") == "False":
        message = data.get("Error", "Kein Film gefunden.")
        if message == "Movie not found!":
            message = "Kein Film gefunden."
        raise OMDbAPIError(message)

    return data


def search_movies(query):
    """Return movie search results from OMDb for a title query."""
    data = _request_omdb({"s": query, "type": "movie"})
    return data.get("Search", [])


def get_movie_by_id(imdb_id):
    """Return detailed OMDb information for one IMDb identifier."""
    return _request_omdb({"i": imdb_id, "plot": "short"})
