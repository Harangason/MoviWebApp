# MoviWebApp

Eine Flask-Webanwendung zum Verwalten persönlicher Lieblingsfilme mit
Filmdaten und Postern aus der OMDb-API.

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
