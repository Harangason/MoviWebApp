# MoviWebApp

Eine Flask-Webanwendung zum Verwalten persönlicher Lieblingsfilme mit
Filmdaten und Postern aus der OMDb-API.

## Funktionen

- Profile anlegen, bearbeiten und samt Filmsammlung löschen
- Vor- und Nachnamen sowie persönlicher Lieblingsfilm
- persönliche Filmsammlungen mit OMDb-Suche, Postern und IMDb-Daten
- eigene Filmtitel und Notizen bearbeiten, Filme löschen
- Sammlung durchsuchen sowie nach Bewertung und Jahr filtern und sortieren
- Zufallsfilm, Durchschnitt, Median, bester/schlechtester Film und Histogramm
- eigenständige HTML-Sammlung exportieren
- JSON-API unter `/api/users` und kompatible Term-3-Endpunkte unter `/api/movies`
- automatische, einmalige Übernahme der Nutzer und Filme aus dem Term-3-Projekt

Vor der ersten Schema- oder Datenmigration wird im Ordner `data` automatisch
eine Sicherung mit der Endung `.pre-migration.bak` angelegt.

## Lokal starten

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

Port `5001` ist der Standard, da Port `5000` auf diesem Rechner bereits von
einem anderen lokalen Projekt verwendet wird. Bei Bedarf kann ein anderer
Port gesetzt werden:

```powershell
$env:MOVIWEB_PORT = "5050"
python app.py
```

Der OMDb-Schlüssel wird aus der lokalen, von Git ignorierten `.env` gelesen:

```text
OMDB_API_KEY=dein_schluessel
```
