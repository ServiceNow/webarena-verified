#!/bin/bash
#
# Verify GitLab database integrity after cleanup
# Starts PostgreSQL, runs checks, then stops it
#
set -euo pipefail

BUILD_DRY_RUN="${BUILD_DRY_RUN:-false}"

if [ "$BUILD_DRY_RUN" = "true" ]; then
    echo "[dry-run] Skipping verification"
    exit 0
fi

echo "========================================"
echo "[verify] Starting database verification..."
echo "========================================"

PG_DATA="/var/opt/gitlab/postgresql/data"
PG_CTL="/opt/gitlab/embedded/bin/pg_ctl"
PSQL="/opt/gitlab/embedded/bin/psql -h /var/opt/gitlab/postgresql -d gitlabhq_production -t -A"

# Start PostgreSQL
echo "[verify] Starting PostgreSQL..."
su - gitlab-psql -s /bin/sh -c "${PG_CTL} start -D ${PG_DATA} -w -t 60"

# Run verification queries
echo ""
echo "=== TABLE ROW COUNTS ==="

verify_count() {
    local table="$1"
    local min_expected="$2"
    local count
    count=$(su - gitlab-psql -s /bin/sh -c "${PSQL} -c \"SELECT COUNT(*) FROM ${table};\"" 2>/dev/null || echo "ERROR")

    if [ "$count" = "ERROR" ]; then
        echo "  ${table}: ERROR - query failed"
        return 1
    elif [ "$count" -lt "$min_expected" ]; then
        echo "  ${table}: ${count} (WARN: expected >= ${min_expected})"
        return 1
    else
        echo "  ${table}: ${count} ✓"
        return 0
    fi
}

ERRORS=0

# Core tables with minimum expected counts
verify_count "users" 100 || ((ERRORS++))
verify_count "projects" 50 || ((ERRORS++))
verify_count "namespaces" 100 || ((ERRORS++))
verify_count "issues" 1000 || ((ERRORS++))
verify_count "merge_requests" 1000 || ((ERRORS++))
verify_count "notes" 1000 || ((ERRORS++))
verify_count "members" 10 || ((ERRORS++))
verify_count "uploads" 100 || ((ERRORS++))

echo ""
echo "=== DATABASE SIZE ==="
DB_SIZE=$(su - gitlab-psql -s /bin/sh -c "${PSQL} -c \"SELECT pg_size_pretty(pg_database_size('gitlabhq_production'));\"" 2>/dev/null)
echo "  Total: ${DB_SIZE}"

echo ""
echo "=== WAL STATUS ==="
WAL_SIZE=$(du -sh ${PG_DATA}/pg_wal/ 2>/dev/null | cut -f1)
echo "  WAL directory: ${WAL_SIZE}"

echo ""
echo "=== SAMPLE DATA CHECK ==="
# Verify root user exists
ROOT_USER=$(su - gitlab-psql -s /bin/sh -c "${PSQL} -c \"SELECT username FROM users WHERE id = 1;\"" 2>/dev/null)
if [ "$ROOT_USER" = "root" ]; then
    echo "  Root user: exists ✓"
else
    echo "  Root user: MISSING"
    ((ERRORS++))
fi

# Stop PostgreSQL
echo ""
echo "[verify] Stopping PostgreSQL..."
su - gitlab-psql -s /bin/sh -c "${PG_CTL} stop -D ${PG_DATA} -m fast -w -t 60"

echo ""
echo "========================================"
if [ "$ERRORS" -gt 0 ]; then
    echo "[verify] FAILED - ${ERRORS} error(s) found"
    echo "========================================"
    exit 1
else
    echo "[verify] PASSED - All checks OK"
    echo "========================================"
fi
