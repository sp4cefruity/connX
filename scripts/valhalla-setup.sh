#!/usr/bin/env bash
# Prepare self-hosted Valhalla routing (ADR 0007).
#
#   bash scripts/valhalla-setup.sh            # download the India Eastern Zone extract
#   bash scripts/valhalla-setup.sh --limits   # after the first start: raise the exclude-polygon limit
#
# Downloads the Geofabrik "Eastern Zone" extract of India (~236 MiB) into
# valhalla/custom_files/, which docker-compose mounts as /custom_files. The
# extract is used whole. On first start the valhalla container builds tiles
# from it (several minutes, a few GB of RAM); later starts reuse them.
# To rebuild after replacing the extract, delete valhalla/custom_files/valhalla_tiles*
# or run once with the env var force_rebuild=True.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="$ROOT/valhalla/custom_files"
URL="https://download.geofabrik.de/asia/india/eastern-zone-latest.osm.pbf"

if [ "${1:-}" = "--limits" ]; then
  CFG="$DIR/valhalla.json"
  [ -f "$CFG" ] || { echo "No $CFG yet: start the valhalla container once, then re-run." >&2; exit 1; }
  # Recommend's avoid zone is a strip along Route B, so its perimeter is long.
  # Valhalla's default cap (10 km) would refuse it; raise it to 200 km.
  python3 - "$CFG" <<'PY'
import json, sys
path = sys.argv[1]
cfg = json.load(open(path))
cfg.setdefault("service_limits", {})["max_exclude_polygons_length"] = 200000
json.dump(cfg, open(path, "w"), indent=2)
print("max_exclude_polygons_length set to 200000 m; restart the container to apply.")
PY
  exit 0
fi

mkdir -p "$DIR"
echo "Downloading $URL"
curl -L --fail -C - -o "$DIR/eastern-zone-latest.osm.pbf" "$URL"
echo "Done. Next: docker compose --profile valhalla up -d valhalla"
