# gndctrl — Docker

**Planned.** Two Docker-native distribution modes.

## Sidecar Mode

A lightweight sidecar container that mounts the project workspace read-only and runs the Auditor + pre-flight API on a local port.

```yaml
# docker-compose.yml
services:
  app:
    build: .
    environment:
      - GNDCTRL_URL=http://gndctrl:7070

  gndctrl:
    image: gndctrl/gndctrl:latest
    ports:
      - "7070:7070"
    volumes:
      - .:/workspace:ro
```

Agent containers call `http://gndctrl:7070/preflight` before each task. The sidecar validates zone access, checks weight class, returns clearance brief.

## Entrypoint Injection Mode

For environments where each project runs inside a container cloned from a base image. The gndctrl agent contract is injected at container boot via `entrypoint.sh`, and the pre-flight sequence runs against the project's `.gndctrl` file on startup.

Useful for AI dev platforms, CI runners, or any setup where agents spin up in fresh containers per task.

## Planned Images

| Image | Purpose |
|---|---|
| `gndctrl/gndctrl:latest` | Full sidecar — Auditor + pre-flight API + Writer |
| `gndctrl/cli:latest` | CLI-only — audit + preflight commands |
| `gndctrl/auditor:latest` | Auditor only — for CI/CD pipelines |
