# Optimized GitLab configuration for development/testing
# This file can be mounted or copied into the container before first start

# External URL - Set to generic internal URL
# For K8s deployments, the actual external URL is handled by Ingress
external_url 'http://localhost:8023'

# Allow GitLab to be accessed from any hostname (important for K8s/proxy environments)
nginx['listen_addresses'] = ['0.0.0.0']
nginx['listen_port'] = 8023

# Trust proxy headers from reverse proxies (K8s Ingress, nginx, etc.)
# Using private networks + localhost (safer than 0.0.0.0/0)
gitlab_rails['trusted_proxies'] = [
  '10.0.0.0/8',      # Private network
  '172.16.0.0/12',   # Private network
  '192.168.0.0/16',  # Private network
  '127.0.0.1',       # Localhost
]

# Disable production monitoring services to reduce resource usage
prometheus_monitoring['enable'] = false
alertmanager['enable'] = false
gitlab_exporter['enable'] = false
postgres_exporter['enable'] = false
redis_exporter['enable'] = false
gitlab_kas['enable'] = false

# Puma configuration (~800MB)
puma['worker_processes'] = 4
puma['min_threads'] = 1
puma['max_threads'] = 4

# Sidekiq - good concurrency for background jobs (~600MB)
sidekiq['max_concurrency'] = 15

# Disable Grafana (not needed for testing)
grafana['enable'] = false

# Disable node_exporter (not needed for testing)
node_exporter['enable'] = false

# PostgreSQL - solid memory allocation (~1.5GB)
postgresql['max_connections'] = 50
postgresql['shared_buffers'] = '512MB'
postgresql['work_mem'] = '32MB'
postgresql['effective_cache_size'] = '1GB'
postgresql['maintenance_work_mem'] = '128MB'

# Redis - generous for caching (~512MB)
redis['maxclients'] = 200
redis['maxmemory'] = '512mb'
redis['maxmemory_policy'] = 'allkeys-lru'

# Disable usage statistics
gitlab_rails['usage_ping_enabled'] = false
gitlab_rails['seat_link_enabled'] = false

# Disable Gitaly backup (reduces reconfigure time)
gitaly['configuration'] = {
  backup: {
    go_cloud_url: '',
  },
}
