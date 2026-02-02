#!/bin/sh
#
# Custom entrypoint for Shopping container
# Applies resource optimizations from environment variables, then calls original entrypoint
#

set -e

# Apply Nginx worker optimization
if [ -n "$NGINX_WORKER_PROCESSES" ]; then
    sed -i "s/worker_processes.*/worker_processes $NGINX_WORKER_PROCESSES;/" /etc/nginx/nginx.conf
    echo "[entrypoint] Nginx workers set to: $NGINX_WORKER_PROCESSES"
fi

# Apply MySQL optimizations
if [ -n "$MYSQL_INNODB_BUFFER_POOL_SIZE" ] || [ -n "$MYSQL_MAX_CONNECTIONS" ]; then
    cat > /etc/my.cnf.d/optimize.cnf << EOF
[mysqld]
innodb_buffer_pool_size = ${MYSQL_INNODB_BUFFER_POOL_SIZE:-256M}
max_connections = ${MYSQL_MAX_CONNECTIONS:-20}
EOF
    echo "[entrypoint] MySQL buffer pool: ${MYSQL_INNODB_BUFFER_POOL_SIZE:-256M}, max connections: ${MYSQL_MAX_CONNECTIONS:-20}"
fi

# Apply Elasticsearch heap optimization
if [ -n "$ES_JAVA_OPTS" ]; then
    # Update supervisor config to pass ES_JAVA_OPTS
    if grep -q "ES_JAVA_OPTS" /etc/supervisor.d/elasticsearch.ini; then
        echo "[entrypoint] ES_JAVA_OPTS already configured"
    else
        sed -i "s|command=su elastico -c \"ES_JAVA_HOME=/usr elasticsearch\"|command=su elastico -c \"ES_JAVA_HOME=/usr ES_JAVA_OPTS='$ES_JAVA_OPTS' elasticsearch\"|" /etc/supervisor.d/elasticsearch.ini
        echo "[entrypoint] Elasticsearch heap set to: $ES_JAVA_OPTS"
    fi
fi

# Call original entrypoint
exec /docker-entrypoint.sh "$@"
