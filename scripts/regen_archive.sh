#!/usr/bin/env bash
# Regenerate every CSCS daily archive page (inlines app.js/styles.css/steppers).
# Batched to fit the ~45s shell timeout. Adjust MAXDAY if the curriculum grows.
set -e
cd "$(dirname "$0")/.."
MAXDAY=${1:-90}
for n in $(seq 1 $MAXDAY); do python3 generate_daily.py --day "$n" >/dev/null; done
python3 generate_daily.py >/dev/null      # final: real Manila-today index + cscs_today.html
echo "Regenerated days 1..$MAXDAY + today index."
