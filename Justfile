# This Justfile is just for running the project locally on macOS.
# It runs all the programs, including the FastAPI and the celery workers.

set shell := ["zsh", "-uc"]

project_name := "demucs-denoiser"
project_dir := justfile_directory()
app_dir := project_dir / "app"

_default:
    @just --list --list-heading $'Commands:\n' --unsorted --list-prefix='- '

# Run the supervisor without using docker
supervisor:
    #!/usr/bin/env zsh
    set -euxo pipefail

    # Need to be in the app directory for the celery command in supervisord.conf to work
    supervisord -c "supervisord.conf"

# Build and run the docker container
docker:
    #!/usr/bin/env zsh
    set -euxo pipefail

    if ! pgrep -x "Docker Desktop" > /dev/null; then
        echo "Docker Desktop is not running, starting it..."
        open /Applications/Docker.app
        sleep 15
    fi

    echo "Building and running {{project_name}}..."
    docker build -t {{project_name}} --file {{project_dir}}/Dockerfile .
    docker ps -q --filter "name={{project_name}}" | grep -q . && docker stop {{project_name}} || true
    docker run --rm -p 8000:8080 --env-file {{project_dir}}/.env --env PORT=8080 --env REDIS_HOST=host.docker.internal \
        --name {{project_name}} {{project_name}}
