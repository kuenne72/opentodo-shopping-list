# Contributing

Contributions are welcome – bug reports, translations, catalog entries, code.
Beiträge sind willkommen – Fehlermeldungen, Übersetzungen, Artikelkatalog, Code.

## Development setup

```bash
git clone https://github.com/kuenne72/opentodo-shopping-list && cd opentodo-shopping-list
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest -q
```

Run against your own OpenTodo instance:

```bash
cp .env.example .env     # fill in OPENTODO_URL and EINKAUF_SECRET
set -a; source .env; set +a
uvicorn app.server:app --reload --port 8086
```

## Guidelines

- Keep OpenTodo untouched: this project only uses its REST API, custom fields and webhooks.
- Every change comes with a test where practical (`tests/` uses a fake OpenTodo via `httpx.MockTransport`).
- User-visible text must exist in German and English: UI texts in `app/static/i18n.js`, server messages in
  `app/messages.py`, catalog in `seed/items.<lang>.csv`. A new language is one more block in each of them.
- No secrets, tokens, real host names or personal data in code, tests, issues or screenshots.
- UI changes: bump the cache name in `app/static/sw.js` so installed apps pick up the new files.

## Good first contributions

- New or corrected catalog entries in `seed/` (CSV, semicolon separated)
- Further UI languages (see above) and catalogs
- Web Push notifications (not started)
- Creating the project and custom fields automatically (`einkauf setup`) if the OpenTodo API allows it

## License

By contributing you agree that your contribution is licensed under the MIT License.
