# OpenTodo Shopping List (einkauf) – Shopping list for OpenTodo / Einkaufsliste für OpenTodo

*Deutsche Fassung: [README.de.md](README.de.md)*

A self-hosted shopping list for the whole household, built as a **companion service** to
[OpenTodo](https://github.com/OpenTodoApp/OpenTodo). OpenTodo stays unmodified and updatable:
this service only talks to its REST API, custom fields and webhooks. The shopping list itself lives
in an OpenTodo project, so it also shows up in OpenTodo and its integrations.

> Unofficial project, not affiliated with OpenTodo. Developed against the OpenTodo REST API v1.
> Status: works in daily use at home; expect rough edges.

## Features

- Mobile-first web app (PWA, add to home screen), light / dark / automatic theme, German and English
- Several people, one list: each person uses their own OpenTodo account and API token
- Live updates across devices (webhook + server-sent events)
- Quick entry: `2 l milk`, `500 g minced meat`, suggestions while typing, built-in catalog of about 240 items
- Sections with icons and colors, editable in the app (changes are written to OpenTodo)
- Stores with their own walking order and section selection (a hardware store needs other sections than a supermarket)
- Items can be assigned to stores; unknown items ask for a section when first added
- Templates ("weekend shopping"), history of recently bought items
- Runs as one small Docker container, SQLite database, backup script

## What you need

- A running OpenTodo instance and an account on it
- Docker with Compose, on any machine that can reach OpenTodo (it does not have to be the same host)
- For installing the app on phones: HTTPS (reverse proxy, Tailscale Serve, Caddy, …)

## Setup

### 1. Prepare OpenTodo (once)

1. Create a project named **Shopping** (or **Einkauf**; any name works if you set `EINKAUF_PROJECT_NAME`).
2. Add these custom fields to that project: **Quantity** (number), **Unit** (text) and optionally
   **Price** (number). German names (Menge, Einheit, Preis) are recognised as well.
3. Create an API token with full access for every person who will use the list, and share the project
   with them as editor (they have to accept the invitation in OpenTodo).

### 2. Start the service

```bash
git clone https://github.com/kuenne72/opentodo-shopping-list.git && cd opentodo-shopping-list
cp .env.example .env
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # paste into EINKAUF_SECRET
# edit .env: OPENTODO_URL, EINKAUF_SECRET, EINKAUF_LANG
docker compose up -d --build
```

### 3. Connect it

```bash
./scripts/cli.sh setup --sprache en          # finds project and fields, creates default sections if there are none
./scripts/cli.sh user set Anna               # asks for Anna's OpenTodo token (hidden), stores it encrypted
./scripts/cli.sh --user Anna check           # connection and write test
./scripts/cli.sh item import                 # loads the item catalog
```

Then set `EINKAUF_SYNC_USER=Anna` in `.env`.

Webhook for live updates: in OpenTodo create a webhook for the shopping project with all `task.*`
events. Target URL, depending on where OpenTodo runs:

| OpenTodo runs … | Webhook target |
|---|---|
| in the same Compose network | `http://einkauf:8086/webhook` |
| in Docker on the same host | `http://host.docker.internal:8086/webhook` |
| elsewhere | `https://<your einkauf address>/webhook` |

Copy the secret (`whsec_…`, shown once) to `EINKAUF_WEBHOOK_SECRET` in `.env` and run
`docker compose up -d`. Without the webhook the list still updates, every `EINKAUF_POLL_SECONDS`.

### 4. Open it

`http://<host>:8086` – choose your name, then add the other people under *Master data → People*.
Phones need HTTPS to install the app; example with Tailscale:

```bash
tailscale serve --bg --https=8444 http://127.0.0.1:8086
```

## Operation

```bash
docker compose logs -f einkauf
./scripts/backup.sh          # SQLite backup into backups/ (also copies .env – keep that folder private)
./scripts/update.sh         # update: backup, git pull, rebuild, health check
```

Data lives in `./data/einkauf.db`. Back it up **together with** `EINKAUF_SECRET`, otherwise the stored
tokens cannot be decrypted. The service has no login of its own: run it in a trusted network or behind
authentication ([SECURITY.md](SECURITY.md)).

## Configuration

| Variable | Meaning |
|---|---|
| `OPENTODO_URL` | address of OpenTodo (required) |
| `EINKAUF_SECRET` | Fernet key that encrypts the tokens (required) |
| `EINKAUF_WEBHOOK_SECRET` | `whsec_…` of the webhook |
| `EINKAUF_SYNC_USER` | person whose token is used for sync |
| `EINKAUF_PROJECT_NAME` / `EINKAUF_PROJECT_ID` | which project is the shopping list |
| `EINKAUF_LANG` | `de` or `en`: default sections and catalog |
| `EINKAUF_POLL_SECONDS` | fallback sync interval (default 300) |
| `EINKAUF_PORT` | published port (default 8086) |

## How it works

- `app/opentodo_client.py` REST client (retry, idempotency key) · `app/bootstrap.py` finds project and fields by name
- `app/core.py` quick-entry parser, list, merging, templates · `app/db.py` SQLite: catalog, stores, templates, tokens
- `app/server.py` FastAPI: webhook, cache, SSE, JSON API, static app · `app/static/` the PWA (plain HTML/CSS/JS)
- Store assignment is kept in the service database, because OpenTodo labels belong to a single account and are not shared.

## Development and contributing

```bash
pip install -e ".[dev]" && python -m pytest -q
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Ideas that are not done yet: Web Push notifications, automatic
creation of project and custom fields, more UI languages.

## License

[MIT](LICENSE)
