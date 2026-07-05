#!/usr/bin/env bash
# Daily comparables refresh (run by cron on the dev box).
#
# Re-scrapes RE/MAX Malta, re-flags + de-dups, exports the clean geo-located
# listings, and ATOMICALLY reloads the production PostGIS `listings` table on the
# VM (staging table + in-transaction swap, so /api/comparables never sees an empty
# table). Any step failing aborts the whole run (set -e) — a partial scrape never
# clobbers good production data.
#
# Install (dev box):
#   crontab -e  ->  0 4 * * * /home/ubuntu/pricemap/scripts/refresh_comparables.sh \
#                     >> /home/ubuntu/pricemap/data/refresh_comparables.log 2>&1
set -euo pipefail

REPO=/home/ubuntu/pricemap
PY="$REPO/.venv/bin/python"
CSV="$REPO/data/exports/mt_listings.csv"
COLS="external_id,source,listing_type,property_type,locality,lat,lon,area_sqm,bedrooms,price_eur,price_per_sqm,url,listing_date"
# psql inside the VM's postgres container (SKIP_IMAGES keeps the daily scrape lean).
DC="docker compose -f docker-compose.prod.yml exec -T postgres psql -U casaval -d casaval"

log() { echo "[$(date -u +%FT%TZ)] $*"; }

cd "$REPO/scripts"

log "1/5 scrape RE/MAX Malta"
SKIP_IMAGES=1 "$PY" run_scrapers.py remax

log "2/5 flag suspicious"
"$PY" flag_suspicious.py >/dev/null

log "3/5 dedup"
"$PY" dedup_remax.py --apply >/dev/null

log "4/5 export CSV"
"$PY" export_listings_csv.py

log "5/5 atomic reload into VM PostGIS"
ssh hetzner "cd /root/pricemap && $DC -c 'TRUNCATE listings_staging'"
ssh hetzner "cd /root/pricemap && $DC -c \"COPY listings_staging ($COLS) FROM STDIN WITH (FORMAT csv, HEADER true)\"" < "$CSV"
ssh hetzner "cd /root/pricemap && $DC -c 'BEGIN; TRUNCATE listings; INSERT INTO listings ($COLS) SELECT $COLS FROM listings_staging; COMMIT;'"
# Refresh planner stats after the bulk reload so the GiST/btree indexes are used.
ssh hetzner "cd /root/pricemap && $DC -c 'ANALYZE listings;'"
N=$(ssh hetzner "cd /root/pricemap && $DC -tAc 'SELECT count(*) FROM listings'")

log "done — listings reloaded, $N rows"
