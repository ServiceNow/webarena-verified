# OpenStreetMap Website Setup Notes

## Source Files

Location: `/Volumes/ed1/webarena/`

| File | Description |
|------|-------------|
| `openstreetmap-website-web.tar.gz` | Web runtime Docker image |
| `openstreetmap-website-db.tar.gz` | PostgreSQL Docker image |
| `openstreetmap-website.tar.gz` | Rails application source code |

## Docker Images

### openstreetmap-website-web:original (1.91 GB)

Rails runtime environment based on Ubuntu 22.04.

**Contains:** Ruby 3.0, Node.js 18, Yarn, PostgreSQL client, Osmosis, app dependencies pre-installed.

**Workdir:** `/app` - expects Rails app to be mounted here.

```bash
docker load -i /Volumes/ed1/webarena/openstreetmap-website-web.tar.gz
docker tag openstreetmap-website-web:latest openstreetmap-website-web:original
docker rmi openstreetmap-website-web:latest
```

### openstreetmap-website-db:original (284 MB)

PostgreSQL 11 database. **No pre-populated data** - just an init script that creates the `openstreetmap` user.

```sql
CREATE USER openstreetmap SUPERUSER PASSWORD 'openstreetmap';
```

Schema comes from Rails migrations (`rails db:migrate`).

```bash
docker load -i /Volumes/ed1/webarena/openstreetmap-website-db.tar.gz
docker tag openstreetmap-website-db:latest openstreetmap-website-db:original
docker rmi openstreetmap-website-db:latest
```

## Rails Application

`openstreetmap-website.tar.gz` - Full OpenStreetMap Rails app source code.

**Version:** `d4a014d3a6ca3f8f7d03528d39e4707dc256bc60` (2023-05-25)
https://github.com/openstreetmap/openstreetmap-website/commit/d4a014d3a6ca3f8f7d03528d39e4707dc256bc60

```bash
tar -xzf /Volumes/ed1/webarena/openstreetmap-website.tar.gz -C /path/to/destination
```

Includes its own `Dockerfile` and `docker-compose.yml`.

## Importing OSM Data (Relations, Ways, Nodes)

The OSM website database is empty by default. To populate it with map data (including relations), use Osmosis.

**Data source:** `osm_dump/us-northeast-latest.osm.pbf` (1.4 GB)

### 1. Truncate existing data (clean import)

```bash
osmosis --truncate-apidb \
  host="localhost" \
  database="openstreetmap" \
  user="openstreetmap" \
  password="" \
  validateSchemaVersion="no"
```

### 2. Import PBF file

```bash
osmosis --read-pbf file=/path/to/us-northeast-latest.osm.pbf \
  --log-progress \
  --write-apidb \
  host="localhost" \
  database="openstreetmap" \
  user="openstreetmap" \
  password="" \
  validateSchemaVersion="no"
```

### 3. Fix sequences (required for editing)

After import, reset PostgreSQL sequences so new edits get proper IDs:

```sql
SELECT setval('current_nodes_id_seq', (SELECT MAX(node_id) FROM current_nodes));
SELECT setval('current_ways_id_seq', (SELECT MAX(way_id) FROM current_ways));
SELECT setval('current_relations_id_seq', (SELECT MAX(relation_id) FROM current_relations));
SELECT setval('changesets_id_seq', (SELECT MAX(id) FROM changesets));
```

### 4. Optimize database (optional)

```bash
vacuumdb -d openstreetmap -afvz
reindexdb -d openstreetmap
```

### Notes

- `--write-apidb` is ~20x slower than osm2pgsql (designed for rendering, not API)
- Osmosis is pre-installed in the web container at `/usr/local/bin/osmosis`
- No official rake task exists yet ([Issue #282](https://github.com/openstreetmap/openstreetmap-website/issues/282))

### References

- [CONFIGURE.md - Database Population](https://github.com/openstreetmap/openstreetmap-website/blob/master/doc/CONFIGURE.md)
- [Issue #282 - Create rake task for populating database](https://github.com/openstreetmap/openstreetmap-website/issues/282)
- [Osmosis Wiki](https://wiki.openstreetmap.org/wiki/Osmosis)
- [Osmosis Detailed Usage](https://wiki.openstreetmap.org/wiki/Osmosis/Detailed_Usage_0.46)

## Combined Image (Web + PostgreSQL + Tile Server + Routing)

Single container with Rails app, two PostgreSQL instances, tile server, and OSRM routing.

**Base images:**
- `am1n3e/openstreetmap-website-web:base` (pushed to Docker Hub)
- `overv/openstreetmap-tile-server@sha256:b6a79da39b6d0758368f7c62d22e49dd3ec59e78b194a5ef9dee2723b1f3fa79`
- `ghcr.io/project-osrm/osrm-backend:v5.27.1`

**Architecture:**
```
Combined Image
├── PostgreSQL 14 (port 5432) → OpenStreetMap website DB
├── PostgreSQL 15 (port 5433) → Tile server DB (gis)
├── Rails (port 3000) → OSM website
├── Apache + mod_tile (port 8080) → Tile endpoint /tile/{z}/{x}/{y}.png
├── renderd → Tile rendering daemon
├── osrm-car (port 5000) → Car routing API
├── osrm-bike (port 5001) → Bike routing API
└── osrm-foot (port 5002) → Foot routing API
```

**Build:**
```bash
docker build --platform linux/amd64 -t openstreetmap-website:combined contributing/environments/docker/sites/map
```

**Run (without tile data):**
```bash
docker run --rm -d --name osm-website --platform linux/amd64 \
  -p 3030:3000 \
  openstreetmap-website:combined
```

**Run (with tile data):**
```bash
docker run --rm -d --name osm-website --platform linux/amd64 \
  -p 3030:3000 \
  -p 8080:8080 \
  -v /Volumes/ed1/webarena/extracted/projects/ogma3/docker/volumes/osm-data/_data:/data/database \
  -v osm-tiles:/data/tiles \
  -v osm-style:/data/style \
  openstreetmap-website:combined
```

**Run (with tile data + routing):**
```bash
docker run --rm -d --name osm-website --platform linux/amd64 \
  -p 3030:3000 \
  -p 5000:5000 \
  -p 5001:5001 \
  -p 5002:5002 \
  -p 8080:8080 \
  -v /Volumes/ed1/webarena/extracted/projects/ogma3/docker/volumes/osm-data/_data:/data/database \
  -v /Volumes/ed1/webarena/extracted/car:/data/routing/car \
  -v /Volumes/ed1/webarena/extracted/bike:/data/routing/bike \
  -v /Volumes/ed1/webarena/extracted/foot:/data/routing/foot \
  -v osm-tiles:/data/tiles \
  -v osm-style:/data/style \
  openstreetmap-website:combined
```

**Access:**
- Website: http://localhost:3030/
- Tiles: http://localhost:8080/tile/{z}/{x}/{y}.png
- Routing car (direct): http://localhost:5000/route/v1/driving/{coords}
- Routing bike (direct): http://localhost:5001/route/v1/driving/{coords}
- Routing foot (direct): http://localhost:5002/route/v1/driving/{coords}
- Routing (via proxy): http://localhost:8080/osrm/routed-{car,bike,foot}/route/v1/driving/{coords}

**Services (managed by Supervisor):**
| Service | Port | Description |
|---------|------|-------------|
| PostgreSQL 14 | 5432 | Website database |
| PostgreSQL 15 | 5433 | Tile database (gis) |
| Rails | 3000 | OpenStreetMap website |
| Apache + mod_tile | 8080 | Tile server HTTP + routing proxy |
| renderd | - | Tile rendering daemon |
| osrm-car | 5000 | OSRM car routing API |
| osrm-bike | 5001 | OSRM bike routing API |
| osrm-foot | 5002 | OSRM foot routing API |

**Features:**
- PostgreSQL 14 for website, PostgreSQL 15 for tiles
- Clones app at exact commit `d4a014d3a6ca3f8f7d03528d39e4707dc256bc60`
- Auto-runs migrations on first start
- Tile data mounted at runtime (39 GB)
- OpenStreetMap Carto style included
- OSRM routing with MLD algorithm (car: 5.8 GB, bike: 7.0 GB, foot: 7.4 GB)
- Website UI uses local routing via Apache proxy

**Environment Variables:**
| Variable | Default | Description |
|----------|---------|-------------|
| `OSM_TILE_URL` | `http://localhost:8080/tile/` | Tile server URL for website |
| `OSM_OSRM_URL` | `http://localhost:8080/osrm/` | OSRM routing URL for website |

The Apache server at port 8080 proxies routing requests:
- `/osrm/routed-car/*` → `localhost:5000/*`
- `/osrm/routed-bike/*` → `localhost:5001/*`
- `/osrm/routed-foot/*` → `localhost:5002/*`

## Testing OSRM Routing

**Test standalone OSRM container (validation):**
```bash
docker run --rm -p 5000:5000 \
  -v /Volumes/ed1/webarena/extracted/car:/data \
  ghcr.io/project-osrm/osrm-backend:v5.27.1 \
  osrm-routed --algorithm mld --max-table-size 1000 -t 4 /data/us-northeast-latest.osrm
```

**Test routing API (NYC to Brooklyn):**
```bash
curl "http://localhost:5000/route/v1/driving/-74.006,40.7128;-73.9352,40.7306?overview=full&steps=true"
```

**Expected response:** JSON with route geometry, distance, and duration.

## Next Steps

- [x] Extract Rails app and review docker-compose.yml
- [x] Start containers and run migrations
- [x] Document data population process
- [x] Add tile server to combined image
- [ ] Create optimized images
- [ ] Import OSM data into combined image
- [ ] Test tile rendering with mounted data

---

# Map Backend Server (Tile, Geocoding, Routing)

Cloud-init based deployment for tile server, geocoding, and routing services.

## Docker Images

| Image | Tag | Service | Port |
|-------|-----|---------|------|
| `overv/openstreetmap-tile-server` | sha256:b6a79da39b6d0758368f7c62d22e49dd3ec59e78b194a5ef9dee2723b1f3fa79 | Tile server | 8080 |
| `mediagis/nominatim` | 4.2 | Geocoding (search) | 8085 |
| `ghcr.io/project-osrm/osrm-backend` | v5.27.1 | Routing (car) | 5000 |
| `ghcr.io/project-osrm/osrm-backend` | v5.27.1 | Routing (bike) | 5001 |
| `ghcr.io/project-osrm/osrm-backend` | v5.27.1 | Routing (foot) | 5002 |

## S3 Data

Bucket: `s3://webarena-map-server-data/`

Local source: `/Volumes/ed1/webarena/`

| File | Local Path | Extract Location | Status |
|------|------------|------------------|--------|
| `osm_tile_server.tar` | `/Volumes/ed1/webarena/osm_tile_server.tar` | `/var/lib/docker/volumes` (strip 5 components) | ✓ |
| `nominatim_volumes.tar` | `/Volumes/ed1/webarena/nominatim_volumes.tar` | `/var/lib/docker/volumes` (strip 5 components) | ✓ |
| `osm_dump.tar` | `/Volumes/ed1/webarena/osm_dump.tar` | `/opt/osm_dump` | ✓ |
| `osrm_routing.tar` | `/Volumes/ed1/webarena/osrm_routing.tar` | `/opt/osrm` | ✓ |

## Extracted Data Details

Local extraction: `/Volumes/ed1/webarena/extracted/`

### osm_tile_server.tar (39 GB extracted)

PostgreSQL 15 database with pre-rendered tile data.

| Archive Path | Data Path |
|--------------|-----------|
| `projects/ogma3/docker/volumes/osm-data/_data/` | PostgreSQL data directory |

Extracted location:
```
/Volumes/ed1/webarena/extracted/projects/ogma3/docker/volumes/osm-data/_data/postgres/
```

### nominatim_volumes.tar (83 GB extracted)

PostgreSQL 14 database with geocoding index + flatnode cache.

| Archive Path | Size | Data Path |
|--------------|------|-----------|
| `projects/metis2/docker/docker/volumes/nominatim-data/_data/` | 35 GB | PostgreSQL data |
| `projects/metis2/docker/docker/volumes/nominatim-flatnode/_data/` | 48 GB | Flatnode cache |

Extracted locations:
```
/Volumes/ed1/webarena/extracted/projects/metis2/docker/docker/volumes/nominatim-data/_data/
/Volumes/ed1/webarena/extracted/projects/metis2/docker/docker/volumes/nominatim-flatnode/_data/
```

### osm_dump.tar (1.8 GB extracted)

| File | Size | Description |
|------|------|-------------|
| `us-northeast-latest.osm.pbf` | 1.4 GB | OpenStreetMap data extract for US Northeast region |
| `wikimedia-importance.sql.gz` | 375 MB | Wikipedia importance rankings for geocoding relevance |

Extracted location:
```
/Volumes/ed1/webarena/extracted/osm_dump/
```

### osrm_routing.tar (20.2 GB extracted)

Pre-processed OSRM routing graphs for MLD algorithm.

| Profile | Size | Data Path |
|---------|------|-----------|
| car | 5.8 GB | `car/us-northeast-latest.osrm.*` |
| bike | 7.0 GB | `bike/us-northeast-latest.osrm.*` |
| foot | 7.4 GB | `foot/us-northeast-latest.osrm.*` |

Extracted locations:
```
/Volumes/ed1/webarena/extracted/car/
/Volumes/ed1/webarena/extracted/bike/
/Volumes/ed1/webarena/extracted/foot/
```

## Service Endpoints

```
Tile server:  http://<ip>:8080/tile/{z}/{x}/{y}.png
Geocoding:    http://<ip>:8085/search?q=<query>&format=json
Routing car:  http://<ip>:5000/route/v1/car/<coords>
Routing bike: http://<ip>:5001/route/v1/bike/<coords>
Routing foot: http://<ip>:5002/route/v1/foot/<coords>
```

## Docker Volume Mounts

| Container | Volume/Path | Mount Point |
|-----------|-------------|-------------|
| tile | `osm-data` | `/data/database/` |
| tile | `osm-tiles` | `/data/tiles/` |
| nominatim | `/opt/osm_dump` | `/nominatim/data` |
| nominatim | `nominatim-data` | `/var/lib/postgresql/14/main` |
| nominatim | `nominatim-flatnode` | `/nominatim/flatnode` |
| osrm-car | `/opt/osrm/car` | `/data` |
| osrm-bike | `/opt/osrm/bike` | `/data` |
| osrm-foot | `/opt/osrm/foot` | `/data` |

## Resource Requirements

- Minimum 200GB disk space
- 4GB swap recommended
- Memory limits per container: tile (2GB), nominatim (4GB), osrm (4GB each)
