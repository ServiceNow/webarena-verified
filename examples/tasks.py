"""Invoke tasks for WebArena-Verified examples."""

import time

from invoke.tasks import task


@task
def demo_gitlab_start(c, password="demopass", port="8012"):
    """Start GitLab container for development and print root password when ready.

    Args:
        password: Root password to set (default: 'demopass')
        port: Port to expose GitLab on (default: '8012')
    """
    container_name = "wa-demo-gitlab"

    print(f"Starting {container_name} container...")
    print(f"Setting root password to: {password}\n")

    # Check if container already exists
    result = c.run(f"docker ps -a --filter name={container_name} --format '{{{{.Names}}}}'", hide=True, warn=True)
    if result and result.stdout.strip():
        print(f"Container {container_name} already exists. Removing it...")
        c.run(f"docker rm -f {container_name}", hide=True)

    # Start GitLab container and disable unneeded services for faster startup
    gitlab_config = (
        f"external_url 'http://localhost:{port}'; "
        "puma['worker_processes'] = 2; "
        "sidekiq['max_concurrency'] = 10; "
        "prometheus_monitoring['enable'] = false; "
        "alertmanager['enable'] = false; "
        "gitlab_exporter['enable'] = false; "
        "node_exporter['enable'] = false; "
        "redis_exporter['enable'] = false; "
        "postgres_exporter['enable'] = false; "
        "pgbouncer_exporter['enable'] = false; "
        "gitlab_kas['enable'] = false; "
        "sentinel['enable'] = false; "
    )

    c.run(
        f"docker run -d --rm "
        f"--hostname localhost "
        f"--publish {port}:{port} "
        f"--name {container_name} "
        f'--env GITLAB_ROOT_PASSWORD="{password}" '
        f'--env GITLAB_OMNIBUS_CONFIG="{gitlab_config}" '
        f"gitlab/gitlab-ce:18.5.0-ce.0"  # Using the latest version since 15.7 is no longer supported
    )

    print("\nWaiting for GitLab to start (this may take 2-3 minutes)...")
    print("Checking GitLab health status...\n")

    # Wait for GitLab web interface to be ready by checking HTTP endpoint
    max_attempts = 240  # 4 minutes with 1 second intervals
    for attempt in range(max_attempts):
        # Check if GitLab web interface is responding
        result = c.run(
            f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{port}/ 2>&1",
            hide=True,
            warn=True,
        )

        # GitLab returns 302 (redirect) when ready
        if result and result.ok and "302" in result.stdout:
            print("✓ GitLab is ready!")
            break

        # Also accept 200 as ready
        if result and result.ok and "200" in result.stdout:
            print("✓ GitLab is ready!")
            break

        if attempt % 10 == 0 and attempt > 0:
            print(f"  Still waiting... ({attempt}s elapsed)")

        time.sleep(1)
    else:
        print("\n⚠ Timeout waiting for GitLab to start. It may still be initializing.")
        print("You can check logs with: docker logs -f dummy-gitlab")
        print(f"Try accessing: http://localhost:{port}")
        return

    # Display the credentials
    print("\n" + "=" * 70)
    print("GitLab is ready!")
    print("=" * 70)
    print(f"URL: http://localhost:{port}")
    print("Username: root")
    print("\nRoot password:")
    print("-" * 70)
    print(f"Password: {password}")
    print("-" * 70)
    print("=" * 70)


@task
def demo_gitlab_stop(c):
    """Stop and remove the GitLab container."""
    container_name = "wa-demo-gitlab"

    # Check if container exists
    result = c.run(f"docker ps -a --filter name={container_name} --format '{{{{.Names}}}}'", hide=True, warn=True)

    if not result or not result.stdout.strip():
        print(f"Container '{container_name}' does not exist.")
        return

    print(f"Stopping and removing {container_name} container...")
    c.run(f"docker rm -f {container_name}")
    print("✓ GitLab container removed successfully!")
