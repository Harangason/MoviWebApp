# MoviWebApp

Eine Flask-Webanwendung zum Verwalten persönlicher Filmsammlungen. Filmdaten,
Bewertungen und Poster werden über die OMDb-API geladen. Zusätzlich enthält
das Projekt unter `folders-ui` einen eigenständigen Next.js-Entwurf für
Clip-Projektordner.

## Funktionen der Flask-Anwendung

- Profile anlegen, bearbeiten und samt Filmsammlung löschen
- Vor- und Nachnamen sowie persönlicher Lieblingsfilm
- persönliche Filmsammlungen mit OMDb-Suche, Postern und IMDb-Daten
- eigene Filmtitel und Notizen bearbeiten, Filme löschen
- Sammlung durchsuchen sowie nach Bewertung und Jahr filtern und sortieren
- Zufallsfilm, Durchschnitt, Median, bester/schlechtester Film und Histogramm
- eigenständige HTML-Sammlung exportieren
- JSON-API unter `/api/users` und kompatible Term-3-Endpunkte unter `/api/movies`
- automatische, einmalige Übernahme der Nutzer und Filme aus dem Term-3-Projekt

## Projektstruktur

- `app.py` – Flask-Anwendung, Webrouten und JSON-API
- `data_manager.py` – Datenbankzugriffe und Geschäftslogik
- `models.py` – SQLAlchemy-Modelle für Nutzer und Filme
- `sql_builder.py` – Datenbankaufbau und Migrationen
- `omdb_api.py` – Anbindung an die OMDb-API
- `templates/` – HTML-Templates der Flask-Oberfläche
- `static/` – Stylesheets der Flask-Oberfläche
- `tests/` – automatisierte Anwendungs- und API-Tests
- `folders-ui/` – eigenständiger Next.js-/React-Entwurf für Clip-Projektordner
- `folders-ui.zip` – Archiv des mitgelieferten UI-Entwurfs

Vor der ersten Schema- oder Datenmigration wird im Ordner `data` automatisch
eine Sicherung mit der Endung `.pre-migration.bak` angelegt.

## Flask-Anwendung lokal starten

```powershell
cd H:\OneDrive\AI_with_Python\Masterschool\Codio\Term_4\MoviWebApp
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Danach im Browser öffnen:

```text
http://127.0.0.1:5001/
```

Bei Bedarf kann ein anderer Port gesetzt werden:

```powershell
$env:MOVIWEB_PORT = "5050"
python app.py
```

Der OMDb-Schlüssel wird aus der lokalen, von Git ignorierten `.env` gelesen:

```text
OMDB_API_KEY=dein_schluessel
```

## Tests ausführen

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Clip-Ordner-Entwurf separat starten

`folders-ui` ist ein eigenständiges Next.js-Projekt und nicht mit dem
Flask-Server oder seiner Datenbank verbunden. Der Entwurf verwendet
Beispieldaten und speichert Änderungen nur im Zustand der geöffneten
Browserseite.

Voraussetzungen sind eine aktuelle Node.js-Version und `pnpm`:

```powershell
cd folders-ui
pnpm install
pnpm dev
```

Anschließend die von Next.js ausgegebene lokale Adresse öffnen.
