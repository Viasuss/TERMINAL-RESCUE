#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Cierre mensual de afiliados activos.
#   1. Genera output/ con cierre.py (lee data/ y logs/).
#   2. Limpia la base (duplicados, huerfanos, fechas) con limpieza.sql.
# Es repetible: puede correr varias veces seguidas.
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BASE_DIR"

# 1. Archivos de salida
python3 "$SCRIPT_DIR/cierre.py"

# 2. Base de datos
[ -f .env ] || cp .env.example .env
set -a; . ./.env; set +a
docker compose up -d cierre-db >/dev/null

echo ">> Esperando a cierre-db"
for _ in $(seq 1 60); do
    if docker compose exec -T cierre-db pg_isready -U "${POSTGRES_USER:-cierre}" -d "${POSTGRES_DB:-cierre}" >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

echo ">> Limpiando la base"
docker compose exec -T cierre-db psql -v ON_ERROR_STOP=1 -q \
    -U "${POSTGRES_USER:-cierre}" -d "${POSTGRES_DB:-cierre}" < "$SCRIPT_DIR/limpieza.sql"

echo "Cierre terminado"
