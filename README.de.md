# OpenTodo Shopping List (einkauf) – Einkaufsliste für OpenTodo

*English version: [README.md](README.md)*

Eine selbst gehostete Einkaufsliste für den ganzen Haushalt, gebaut als **Ergänzungsdienst** zu
[OpenTodo](https://github.com/OpenTodoApp/OpenTodo). OpenTodo bleibt unverändert und aktualisierbar:
der Dienst nutzt nur die REST-API, benutzerdefinierte Felder und Webhooks. Die Liste selbst liegt in
einem OpenTodo-Projekt und erscheint damit auch in OpenTodo und dessen Anbindungen.

> Inoffizielles Projekt, nicht mit OpenTodo verbunden. Entwickelt gegen die OpenTodo-REST-API v1.
> Stand: läuft im Alltag zu Hause; mit Ecken und Kanten ist zu rechnen.

## Funktionen

- Handy-Oberfläche (PWA, zum Home-Bildschirm hinzufügbar), Hell / Dunkel / Automatisch, Deutsch und Englisch
- Mehrere Personen, eine Liste: jede Person nutzt ihr eigenes OpenTodo-Konto und ihren API-Token
- Live-Aktualisierung auf allen Geräten (Webhook + Server-Sent Events)
- Schnellerfassung: `2 l Milch`, `500 g Hackfleisch`, Vorschläge beim Tippen, Katalog mit rund 240 Artikeln
- Abschnitte mit Symbolen und Farben, in der App bearbeitbar (Änderungen gehen nach OpenTodo)
- Läden mit eigenem Laufweg und eigener Abschnittsauswahl (Baumarkt ≠ Supermarkt)
- Artikel können Läden zugeordnet werden; unbekannte Artikel fragen beim ersten Mal nach dem Abschnitt
- Vorlagen („Wochenende"), Historie zuletzt gekaufter Artikel
- Ein kleiner Docker-Container, SQLite-Datenbank, Backup-Skript

## Voraussetzungen

- Eine laufende OpenTodo-Instanz mit Konto
- Docker mit Compose auf einem beliebigen Rechner, der OpenTodo erreicht (nicht zwingend derselbe Host)
- Für die App auf dem Handy: HTTPS (Reverse Proxy, Tailscale Serve, Caddy, …)

## Einrichtung

### 1. OpenTodo vorbereiten (einmalig)

1. Projekt **Einkauf** anlegen (oder **Shopping**; anderer Name über `EINKAUF_PROJECT_NAME`).
2. In diesem Projekt die benutzerdefinierten Felder **Menge** (Zahl), **Einheit** (Text) und optional
   **Preis** (Zahl) anlegen. Englische Namen (Quantity, Unit, Price) werden ebenfalls erkannt.
3. Für jede Person, die die Liste nutzt, einen API-Token mit vollem Zugriff erzeugen und das Projekt als
   Bearbeiter für sie freigeben (die Einladung muss in OpenTodo angenommen werden).

### 2. Dienst starten

```bash
git clone https://github.com/kuenne72/opentodo-shopping-list.git && cd opentodo-shopping-list
cp .env.example .env
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # in EINKAUF_SECRET eintragen
# .env bearbeiten: OPENTODO_URL, EINKAUF_SECRET, EINKAUF_LANG=de, EINKAUF_PROJECT_NAME=Einkauf
docker compose up -d --build
```

### 3. Verbinden

```bash
./scripts/cli.sh setup --sprache de          # findet Projekt und Felder, legt Standardabschnitte an, falls keine existieren
./scripts/cli.sh user set Anna               # fragt Annas OpenTodo-Token ab (verdeckt) und legt ihn verschlüsselt ab
./scripts/cli.sh --user Anna check           # Verbindungs- und Schreibtest
./scripts/cli.sh item import                 # spielt den Artikelkatalog ein
```

Danach `EINKAUF_SYNC_USER=Anna` in `.env` setzen.

Webhook für Live-Updates: in OpenTodo einen Webhook für das Einkaufsprojekt mit allen `task.*`-Ereignissen
anlegen. Ziel-URL je nachdem, wo OpenTodo läuft:

| OpenTodo läuft … | Webhook-Ziel |
|---|---|
| im selben Compose-Netz | `http://einkauf:8086/webhook` |
| in Docker auf demselben Host | `http://host.docker.internal:8086/webhook` |
| woanders | `https://<Adresse von einkauf>/webhook` |

Das Secret (`whsec_…`, wird nur einmal angezeigt) in `.env` als `EINKAUF_WEBHOOK_SECRET` eintragen und
`docker compose up -d` ausführen. Ohne Webhook aktualisiert sich die Liste trotzdem, alle
`EINKAUF_POLL_SECONDS`.

### 4. Öffnen

`http://<Host>:8086` – Namen wählen, weitere Personen unter *Stammdaten → Personen* hinzufügen.
Für die Installation auf dem Handy ist HTTPS nötig; Beispiel mit Tailscale:

```bash
tailscale serve --bg --https=8444 http://127.0.0.1:8086
```

## Betrieb

```bash
docker compose logs -f einkauf
./scripts/backup.sh           # SQLite-Sicherung nach backups/ (kopiert auch .env – Ordner privat halten)
./scripts/update.sh          # Update: Backup, git pull, neu bauen, Gesundheitsprüfung
```

Die Daten liegen in `./data/einkauf.db`. Sicherung immer **zusammen mit** `EINKAUF_SECRET`, sonst lassen
sich die abgelegten Tokens nicht entschlüsseln. Der Dienst hat keine eigene Anmeldung: nur in einem
vertrauenswürdigen Netz oder hinter einer Authentifizierung betreiben ([SECURITY.md](SECURITY.md)).

## Konfiguration

| Variable | Bedeutung |
|---|---|
| `OPENTODO_URL` | Adresse von OpenTodo (Pflicht) |
| `EINKAUF_SECRET` | Fernet-Schlüssel für die Token (Pflicht) |
| `EINKAUF_WEBHOOK_SECRET` | `whsec_…` des Webhooks |
| `EINKAUF_SYNC_USER` | Person, deren Token für den Abgleich genutzt wird |
| `EINKAUF_PROJECT_NAME` / `EINKAUF_PROJECT_ID` | welches Projekt die Einkaufsliste ist |
| `EINKAUF_LANG` | `de` oder `en`: Standardabschnitte und Katalog |
| `EINKAUF_POLL_SECONDS` | Intervall des Ersatzabgleichs (Standard 300) |
| `EINKAUF_PORT` | veröffentlichter Port (Standard 8086) |

## Aufbau

- `app/opentodo_client.py` REST-Client (Retry, Idempotency-Key) · `app/bootstrap.py` findet Projekt und Felder per Namen
- `app/core.py` Schnellerfassung, Liste, Zusammenführen, Vorlagen · `app/db.py` SQLite: Katalog, Läden, Vorlagen, Token
- `app/server.py` FastAPI: Webhook, Cache, SSE, JSON-API, statische App · `app/static/` die PWA (reines HTML/CSS/JS)
- Die Ladenzuordnung liegt in der Datenbank des Dienstes, weil OpenTodo-Labels an ein Konto gebunden sind und nicht geteilt werden.

## Entwicklung und Mitmachen

```bash
pip install -e ".[dev]" && python -m pytest -q
```

Siehe [CONTRIBUTING.md](CONTRIBUTING.md). Offen: Web-Push-Benachrichtigungen, automatisches Anlegen von
Projekt und Feldern, weitere Sprachen.

## Lizenz

[MIT](LICENSE)
