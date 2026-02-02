# Performance GitLab configuration for responsive testing
# Target: ~8-10GB RAM
# Use case: Multi-user testing, faster CI, complex workflows

# External URL - Set to generic internal URL
# For K8s deployments, the actual external URL is handled by Ingress
external_url 'http://localhost:8023'

# Allow GitLab to be accessed from any hostname (important for K8s/proxy environments)
nginx['listen_addresses'] = ['0.0.0.0']
nginx['listen_port'] = 8023

# Trust proxy headers from reverse proxies (K8s Ingress, nginx, etc.)
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

# Puma configuration (~1.5GB)
puma['worker_processes'] = 6
puma['min_threads'] = 2
puma['max_threads'] = 8

# Sidekiq - high concurrency for fast background jobs (~1GB)
sidekiq['max_concurrency'] = 25

# Disable Grafana (not needed for testing)
grafana['enable'] = false

# Disable node_exporter (not needed for testing)
node_exporter['enable'] = false

# PostgreSQL - generous allocation (~3GB)
postgresql['max_connections'] = 100
postgresql['shared_buffers'] = '1GB'
postgresql['work_mem'] = '64MB'
postgresql['effective_cache_size'] = '2GB'
postgresql['maintenance_work_mem'] = '256MB'

# Redis - generous for caching (~1GB)
redis['maxclients'] = 500
redis['maxmemory'] = '1gb'
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
