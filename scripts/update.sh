#!/bin/bash
# Update an installation: backup, pull the latest version, rebuild, wait until healthy.
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/backup.sh
git pull --ff-only
docker compose up -d --build
echo -n "Waiting for the service "
for _ in $(seq 1 30); do
  if [ "$(docker inspect -f '{{.State.Health.Status}}' einkauf 2>/dev/null)" = "healthy" ]; then
    echo "- healthy"; docker compose logs --tail=5 einkauf; exit 0
  fi
  echo -n "."; sleep 3
done
echo; echo "Not healthy yet, check: docker compose logs einkauf"; exit 1
