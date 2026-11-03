#!/bin/bash
# Run the CLI inside the running container: ./scripts/cli.sh --user Anna list
cd "$(dirname "$0")/.."
exec docker compose exec einkauf einkauf "$@"
