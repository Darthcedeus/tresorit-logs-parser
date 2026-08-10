# tresorit-logs-parser
Simple web app to display data from Tresorit shared links logs.

## Deploy with Docker Compose

Prerequisites:

- Docker Engine or Docker Desktop
- Docker Compose v2 (`docker compose`)

From a fresh clone:

```sh
git clone <repo-url>
cd tresorit-logs-parser
./scripts/install.sh
./scripts/deploy.sh
```

The app will be available at:

```text
http://localhost:5000
```

To use a different host port:

```sh
APP_PORT=8080 ./scripts/deploy.sh
```

Useful commands:

```sh
docker compose logs -f
./scripts/stop.sh
```
