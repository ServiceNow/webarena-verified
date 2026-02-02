# Environments

WebArena-Verified uses Docker containers to provide isolated, reproducible test environments for each website in the benchmark.

## Overview

Each test environment (Shopping, Reddit, GitLab, etc.) runs as a self-contained Docker container with:

- The application and its dependencies
- Pre-populated test data
- Environment control utilities for management via CLI or HTTP

## Sections

- [Docker Images](docker_images.md) - Instructions for building and running slim Docker images
- [Environment Control](environment_control.md) - The `environment_control` package for managing environments
