# Folders UI

Eigenständiger Next.js-/React-Oberflächenentwurf für eine Übersicht aus
Clip-Projektordnern. Ordner können in der Oberfläche angelegt, umbenannt und
entfernt werden; die Generierung wird mit Fortschrittszuständen simuliert.

## Aktueller Stand

- Die angezeigten Projekte und Bilder sind Beispieldaten aus `lib/data.ts`.
- Neue Ordner existieren nur im React-Zustand der geöffneten Browserseite.
- Nach einem Neuladen werden lokale Änderungen zurückgesetzt.
- Es besteht keine Verbindung zur Flask-Anwendung oder Filmdatenbank.

## Lokal starten

Voraussetzungen sind eine aktuelle Node.js-Version und `pnpm`.

```powershell
pnpm install
pnpm dev
```

Anschließend die von Next.js ausgegebene lokale Adresse öffnen.

## Prüfen und produktiv bauen

```powershell
pnpm lint
pnpm build
pnpm start
```

## Wichtige Verzeichnisse

- `app/` – Next.js-Seite, Layout und globale Styles
- `components/` – Ordnerkarten, Menü, Lade- und Erstellungszustände
- `contexts/` – simulierte Generierungszustände
- `hooks/` – lokaler Projektzustand
- `lib/data.ts` – Beispieldaten
- `public/` – Vorschaubilder und Icons
