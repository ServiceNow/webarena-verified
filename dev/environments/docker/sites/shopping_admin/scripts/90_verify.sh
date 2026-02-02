#!/bin/bash
#
# Verify Shopping Admin (Magento) database integrity after cleanup
# Starts MySQL, runs checks, then stops it
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

MYSQL_DATA="/var/lib/mysql"
MYSQL="mysql -u magentouser -pMyPassword -N -B magentodb"

# Start MySQL
echo "[verify] Starting MySQL..."
mysqld_safe --skip-grant-tables &
sleep 10

# Run verification queries
echo ""
echo "=== TABLE ROW COUNTS ==="

verify_count() {
    local table="$1"
    local min_expected="$2"
    local count
    count=$($MYSQL -e "SELECT COUNT(*) FROM ${table};" 2>/dev/null || echo "ERROR")

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
verify_count "customer_entity" 60 || ((ERRORS++))
verify_count "catalog_product_entity" 2000 || ((ERRORS++))
verify_count "catalog_category_entity" 35 || ((ERRORS++))
verify_count "sales_order" 300 || ((ERRORS++))
verify_count "review" 300 || ((ERRORS++))
verify_count "admin_user" 1 || ((ERRORS++))
verify_count "cms_page" 5 || ((ERRORS++))
verify_count "cms_block" 15 || ((ERRORS++))

echo ""
echo "=== DATABASE SIZE ==="
DB_SIZE=$($MYSQL -e "SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) FROM information_schema.tables WHERE table_schema = 'magentodb';" 2>/dev/null)
echo "  Total: ${DB_SIZE} MB"

echo ""
echo "=== SAMPLE DATA CHECK ==="
# Verify admin user exists
ADMIN_USER=$($MYSQL -e "SELECT username FROM admin_user WHERE user_id = 1;" 2>/dev/null)
if [ "$ADMIN_USER" = "admin" ]; then
    echo "  Admin user: exists ✓"
else
    echo "  Admin user: MISSING"
    ((ERRORS++))
fi

# Verify sample product exists
PRODUCT=$($MYSQL -e "SELECT sku FROM catalog_product_entity ORDER BY entity_id LIMIT 1;" 2>/dev/null)
if [ -n "$PRODUCT" ]; then
    echo "  Sample product: ${PRODUCT} ✓"
else
    echo "  Sample product: MISSING"
    ((ERRORS++))
fi

# Stop MySQL
echo ""
echo "[verify] Stopping MySQL..."
mysqladmin shutdown 2>/dev/null || killall mysqld 2>/dev/null || true
sleep 5

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
