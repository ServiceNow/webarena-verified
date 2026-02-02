# Map

OpenStreetMap-based mapping platform with tiles, geocoding, and routing.

| Property | Value |
|----------|-------|
| Port | 3030 |
| Env-Ctrl Port | 3031 |
| Image | `am1n3e/webarena-verified-map` |
| Container | `webarena-verified-map` |

## Optimization

Unlike other environments where the focus was on reducing image size, the Map environment optimization focuses on **usability**. The [original WebArena setup](https://github.com/web-arena-x/webarena/blob/main/webarena-map-backend-boot-init.yaml) required deploying 5 separate containers:

- Tile server (`overv/openstreetmap-tile-server`)
- Nominatim geocoding server (`mediagis/nominatim:4.2`)
- 3 OSRM routing servers for car, bike, and foot

Each container needed its own configuration, data volumes, and orchestration. The optimized image consolidates all services into a **single container** with unified management through env-ctrl, making deployment straightforward.

## Quick Start

```bash
# Using Docker Compose
docker compose up -d map

# Using Invoke
inv envs.docker.pull --site map
inv envs.docker.start --site map
```

Access at: http://localhost:3030

## Architecture

The map environment is a combined image with multiple services:

| Service | Internal Port | Description |
|---------|---------------|-------------|
| Rails | 3000 | OpenStreetMap website |
| PostgreSQL 14 | 5432 | Website database |
| PostgreSQL 15 | 5433 | Tile database (gis) |
| Apache + mod_tile | 8080 | Tile server |
| renderd | - | Tile rendering daemon |
| OSRM (car) | 5000 | Car routing API |
| OSRM (bike) | 5001 | Bike routing API |
| OSRM (foot) | 5002 | Foot routing API |

## Data Requirements

Map requires external data files for tiles and routing:

```bash
# Download map data
inv envs.docker.data-download --site map

# Set up volumes
inv envs.docker.setup --site map --data-dir ./data
```

### Data Sizes

| Data | Size | Description |
|------|------|-------------|
| Tile database | ~39 GB | PostgreSQL with pre-rendered tiles |
| Car routing | ~5.8 GB | OSRM routing graph |
| Bike routing | ~7.0 GB | OSRM routing graph |
| Foot routing | ~7.4 GB | OSRM routing graph |

## Service Endpoints

When running with full data:

| Endpoint | URL |
|----------|-----|
| Website | http://localhost:3030/ |
| Tiles | http://localhost:8080/tile/{z}/{x}/{y}.png |
| Routing (car) | http://localhost:5000/route/v1/driving/{coords} |
| Routing (bike) | http://localhost:5001/route/v1/driving/{coords} |
| Routing (foot) | http://localhost:5002/route/v1/driving/{coords} |
| Routing (proxy) | http://localhost:8080/osrm/routed-{car,bike,foot}/route/v1/driving/{coords} |

## Testing Routing

```bash
# Test routing API (NYC to Brooklyn)
curl "http://localhost:5000/route/v1/driving/-74.006,40.7128;-73.9352,40.7306?overview=full&steps=true"
```

## Resource Requirements

- **Disk:** Minimum 200GB for full tile and routing data
- **Memory:** 4GB+ recommended
- **Swap:** 4GB recommended
