#!/bin/bash
#
# Verify Reddit (Postmill) database integrity after cleanup
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

PG_DATA="/usr/local/pgsql/data"
PG_CTL="/usr/bin/pg_ctl"

# Database credentials
DB_HOST="localhost"
DB_USER="postmill"
DB_PASS="postmill"
DB_NAME="postmill"

# psql command with credentials
run_psql() {
    PGPASSWORD="${DB_PASS}" psql -h "${DB_HOST}" -U "${DB_USER}" -d "${DB_NAME}" -t -A "$@"
}

# Start PostgreSQL
echo "[verify] Starting PostgreSQL..."
su - postgres -c "${PG_CTL} start -D ${PG_DATA} -w -t 60"

# Run verification queries
echo ""
echo "=== TABLE ROW COUNTS ==="

verify_count() {
    local table="$1"
    local min_expected="$2"
    local count
    count=$(run_psql -c "SELECT COUNT(*) FROM ${table};" 2>/dev/null || echo "ERROR")

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
verify_count "users" 600000 || ((ERRORS++))
verify_count "forums" 90 || ((ERRORS++))
verify_count "submissions" 120000 || ((ERRORS++))
verify_count "comments" 2500000 || ((ERRORS++))
verify_count "images" 30000 || ((ERRORS++))

echo ""
echo "=== DATABASE SIZE ==="
DB_SIZE=$(run_psql -c "SELECT pg_size_pretty(pg_database_size('${DB_NAME}'));" 2>/dev/null)
echo "  Total: ${DB_SIZE}"

echo ""
echo "=== SAMPLE DATA CHECK ==="
# Verify admin user exists
ADMIN_USER=$(run_psql -c "SELECT username FROM users WHERE admin = true ORDER BY id LIMIT 1;" 2>/dev/null)
if [ -n "$ADMIN_USER" ]; then
    echo "  Admin user: ${ADMIN_USER} ✓"
else
    echo "  Admin user: MISSING"
    ((ERRORS++))
fi

# Verify sample forum exists
FORUM=$(run_psql -c "SELECT name FROM forums ORDER BY id LIMIT 1;" 2>/dev/null)
if [ -n "$FORUM" ]; then
    echo "  Sample forum: ${FORUM} ✓"
else
    echo "  Sample forum: MISSING"
    ((ERRORS++))
fi

# Stop PostgreSQL
echo ""
echo "[verify] Stopping PostgreSQL..."
su - postgres -c "${PG_CTL} stop -D ${PG_DATA} -m fast -w -t 60"

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
