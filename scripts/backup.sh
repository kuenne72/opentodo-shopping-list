#!/bin/bash
# Consistent backup of the service database (SQLite online backup) into backups/.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
stamp=$(date +%Y%m%d-%H%M)
docker compose exec -T einkauf python - <<'PY' > "backups/einkauf-$stamp.db"
import sqlite3, sys, tempfile, os
src = sqlite3.connect("/data/einkauf.db")
fd, tmp = tempfile.mkstemp(); os.close(fd)
dst = sqlite3.connect(tmp); src.backup(dst); dst.close()
sys.stdout.buffer.write(open(tmp, "rb").read()); os.remove(tmp)
PY
umask 077
cp .env "backups/env-$stamp.txt"   # the key in .env is needed to read the stored tokens
ls -t backups/einkauf-*.db | tail -n +15 | xargs -r rm --   # keep the last 14
ls -t backups/env-*.txt   | tail -n +15 | xargs -r rm --
echo "Backup: backups/einkauf-$stamp.db"
