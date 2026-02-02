"""Main invoke tasks file. Use `inv --list` to see available tasks."""

from invoke import Collection, Context, task

from dev import contributing_tasks as dev_tasks
from dev.environments import tasks as envs_tasks
from examples import tasks as demo_tasks

# Service config: display name, port env var, default port
SERVICES = {
    "shopping_admin": ("Shopping Admin", "WA_SHOPPING_ADMIN_PORT", 7780),
    "shopping": ("Shopping", "WA_SHOPPING_PORT", 7770),
    "gitlab": ("GitLab", "WA_GITLAB_PORT", 8023),
    "reddit": ("Reddit", "WA_REDDIT_PORT", 9999),
    "wikipedia": ("Wikipedia", "WA_WIKIPEDIA_PORT", 8888),
    "monitor": ("Gatus Dashboard", "WA_MONITOR_PORT", 8870),
}

# Service descriptions for output
SERVICE_DESCRIPTIONS = {
    "shopping_admin": "Magento admin panel",
    "shopping": "Magento storefront",
    "gitlab": "GitLab instance",
    "reddit": "Reddit-like forum",
    "wikipedia": "Wikipedia via Kiwix",
    "monitor": "Gatus health dashboard - shows status of all environments",
}


def _get_service_url(service: str) -> str:
    """Get the localhost URL for a service."""
    if service in SERVICES:
        _, _, default_port = SERVICES[service]
        return f"http://localhost:{default_port}"
    return ""


@task(
    help={
        "service": "Service(s) to start (can be specified multiple times). If not specified, starts all services.",
        "foreground": "Run in foreground (default: detached)",
        "no_monitor": "Do not automatically include the monitor service when specific services are requested.",
    },
    iterable=["service"],
)
def up(ctx: Context, service: list[str] | None = None, foreground: bool = False, no_monitor: bool = False) -> None:
    """Start Docker Compose services."""
    services = list(service) if service else []

    # Automatically include monitor when specific services are requested (unless disabled)
    if services and not no_monitor and "monitor" not in services:
        services.append("monitor")

    # Build env vars for gatus display names (mark non-started services as N/A)
    env_vars = {}
    if services:
        monitored = [s for s in SERVICES if s != "monitor"]
        for svc in monitored:
            display_name, _, _ = SERVICES[svc]
            name_var = f"WA_{svc.upper()}_NAME"
            if svc in services:
                env_vars[name_var] = display_name
            else:
                env_vars[name_var] = f"[N/A] {display_name}"

    service_args = " ".join(services) if services else ""
    detach_flag = "" if foreground else "-d"
    env_prefix = " ".join(f'{k}="{v}"' for k, v in env_vars.items())

    cmd = f"{env_prefix} docker compose up {detach_flag} {service_args}".strip()
    ctx.run(cmd, pty=foreground, hide=not foreground)

    if not foreground:
        # Print URLs for started services
        started = services if services else SERVICE_DESCRIPTIONS.keys()
        print("Started services:")
        for svc in started:
            if svc in SERVICE_DESCRIPTIONS:
                url = _get_service_url(svc)
                description = SERVICE_DESCRIPTIONS[svc]
                print(f"  {svc:15} {url:30} - {description}")


@task(
    help={
        "service": "Service(s) to stop (can be specified multiple times). If not specified, stops all services.",
    },
    iterable=["service"],
)
def down(ctx: Context, service: list[str] | None = None) -> None:
    """Stop Docker Compose services."""
    services = service or []
    if services:
        # Stop specific services
        service_args = " ".join(services)
        ctx.run(f"docker compose stop {service_args}")
        ctx.run(f"docker compose rm -f {service_args}")
    else:
        # Stop all services
        ctx.run("docker compose down")


# Create compose namespace
compose_ns = Collection("compose")
compose_ns.add_task(up)
compose_ns.add_task(down)

# Create the namespace
ns = Collection()

# Add namespaces
ns.add_collection(Collection.from_module(dev_tasks), name="dev")
ns.add_collection(Collection.from_module(demo_tasks), name="demo")
ns.add_collection(envs_tasks.ns, name="envs")
ns.add_collection(compose_ns, name="compose")
