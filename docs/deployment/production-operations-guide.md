# Production Operations & Troubleshooting Runbook

This document serves as the persistent memory and operational runbook for diagnosing and resolving common deployment, container, networking, and database issues in the Wolinet AI stack (Dokploy / Docker Swarm / Contabo VPS).

---

## 1. Disk Space Management & Image Retention

### Symptom
- Root filesystem `/` hits 100% utilization (`df -h /`).
- Docker operations fail with `No space left on device` or `failed to register layer`.
- Swarm tasks fail to spawn due to missing bind mounts or truncated code directories.

### Root Cause
1. **GitHub Actions Matrix Builds**: Building all images unconditionally on every commit pushes ~32 GB of new layers (e.g. `wolinet-mitambo-cpu` at 12.2 GB and `wolinet-wolinex` at 6.78 GB).
2. **Superseded Image Layer Accumulation**: `docker pull` updates `:latest` but leaves older SHA-tagged images on disk. Standard `docker image prune -f` only cleans dangling images, ignoring superseded tagged images.
3. **Container Log Bloat**: Unrotated container stdout/stderr files in `/var/lib/docker/containers/*/*-json.log`.

### Permanent Prevention
1. **CI Path Filtering**: [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml) checks `git diff HEAD~1 HEAD` and skips building large images (`mitambo`, `wolinex`) when their source directories are untouched.
2. **Automated Redeploy Prune**: [`scripts/deploy/prune-and-redeploy.sh`](../deploy/prune-and-redeploy.sh) executes `docker image prune -a -f` after the stack is running.

### Emergency Host Recovery
```bash
# 1. Prune stopped containers (releases locks on old images)
docker container prune -f

# 2. Prune BuildKit build cache
docker builder prune -a -f

# 3. Prune all unused images not attached to running containers
docker image prune -a -f

# 4. Truncate bloated container JSON logs & journal
truncate -s 0 /var/lib/docker/containers/*/*-json.log 2>/dev/null || true
journalctl --vacuum-time=1d
apt-get clean

# 5. Check reclaimed space
df -h /
```

---

## 2. Contabo IPv6 TCP Reset During Large Image Pulls

### Symptom
- `docker pull` fails mid-download with:
  `failed to copy: read tcp [2a02:c207:....]:443: read: connection reset by peer`

### Root Cause
Contabo VPS IPv6 routing to GitHub's Fastly CDN (`2606:50c0:...`) frequently experiences MTU drops or TCP resets when streaming large layer files (>1 GB).

### Solution
Force the Linux host / Docker to prefer IPv4:

```bash
# Option A: Prefer IPv4 for all host name resolution
grep -q "precedence ::ffff:0:0/96  100" /etc/gai.conf 2>/dev/null || echo "precedence ::ffff:0:0/96  100" >> /etc/gai.conf

# Option B: Temporarily disable IPv6 interfaces during image pull
sysctl -w net.ipv6.conf.all.disable_ipv6=1
sysctl -w net.ipv6.conf.default.disable_ipv6=1

# Pull image cleanly over stable IPv4
docker pull ghcr.io/wolinet-renatus/wolinet-mitambo-cpu:latest

# (Optional) Re-enable IPv6 after download finishes
sysctl -w net.ipv6.conf.all.disable_ipv6=0
sysctl -w net.ipv6.conf.default.disable_ipv6=0
```

---

## 3. Docker Swarm Paused Rollback Loop

### Symptom
- Service update shows:
  `rollback: update rolled back due to failure`
  `service rollback paused: update paused due to failure or early termination of task`
- Subsequent `docker service update --force` commands fail to apply new settings.

### Root Cause
Docker Swarm update configuration has `failure_action: rollback`. When a task exits during the monitor window, Swarm rolls back to the previous spec. If the previous spec also fails, Swarm pauses the rollback to prevent infinite thrashing.

### Solution
Break out of the paused rollback by explicitly disabling rollback and applying the new configuration:

```bash
docker service update \
  --rollback=false \
  --update-failure-action pause \
  --force \
  <service_name>
```

---

## 4. Open WebUI Alembic Foreign Revision Mismatch

### Symptom
- Open WebUI (`wolinex`) crashes on boot with:
  `alembic.util.exc.CommandError: Can't locate revision identified by 'd4c1a8e37b62'`

### Root Cause
An earlier container or test image ran Alembic migrations that wrote a foreign revision ID (`d4c1a8e37b62`) into PostgreSQL's `alembic_version` table. The baseline Open WebUI container image only knows up to revision `f2a4b6c8d0e1` (`add_chat_jsonb_gin_index.py`).

### Solution
Sanitize the `alembic_version` table in the active database (`wolinex`):

```bash
PG_CONTAINER=$(docker ps -q -f name=wolinetai-wolinex-s9qn5o_postgres | head -n 1)
docker exec -i "$PG_CONTAINER" psql -U postgres -d wolinex -c "UPDATE alembic_version SET version_num = 'f2a4b6c8d0e1';"
```

---

## 5. Open WebUI Dynamic Config `KeyError: 'ENABLE_OLLAMA_API'`

### Symptom
- Open WebUI crashes during startup at `open_webui/main.py:933`:
  ```
  app.state.config.ENABLE_OLLAMA_API = False
  File ".../open_webui/internal/config.py", line 391, in __setattr__
      entries[name].value = value
  KeyError: 'ENABLE_OLLAMA_API'
  ```

### Root Cause
`AppConfig` inherits from a custom persistent config class that expects attributes to be predefined `ConfigVar` instances in `_entries`. When `main.py` directly assigns a primitive boolean to an uninitialized key, looking up `entries[name]` throws a `KeyError`.

### Solution
In [`apps/web-client/backend/open_webui/internal/config.py`](file:///Users/apple/Documents/wolinetai/apps/web-client/backend/open_webui/internal/config.py):
1. In `__setattr__`: If `name not in entries`, cleanly delegate to `super().__setattr__(name, value)`.
2. In `__getattr__`: If `name not in entries`, fallback to `super().__getattribute__(name)`.

This makes `AppConfig` behave like a standard Python object for any dynamic or environment-driven attributes without requiring pre-registration.

---

## 6. Documentation Sign-In / Register Action

### Symptom
- Visiting `https://wolinex.wolinet.com/docs` and clicking "Sign In" or "Register" does nothing or fails due to inline JavaScript modal handler errors.

### Solution
Header authentication buttons in [`apps/web-client/backend/open_webui/routers/wolinet_docs.py`](file:///Users/apple/Documents/wolinetai/apps/web-client/backend/open_webui/routers/wolinet_docs.py) use direct HTML navigation links:
```html
<a href="/auth" class="btn-signin">Sign In</a>
<a href="/auth" class="btn-register">Register</a>
```
This routes users directly to Open WebUI's native login/registration screen (`/auth`) with zero client-side JavaScript dependencies.

---

## 7. Operational Health Check Cheat Sheet

```bash
# List all services and replica counts
docker service ls

# Inspect specific service tasks and failure reasons
docker service ps wolinetai-wolinex-s9qn5o_wolinex --no-trunc | head -n 5

# View recent service logs
docker service logs --tail 30 wolinetai-wolinex-s9qn5o_wolinex
docker service logs --tail 30 wolinetai-wolinex-s9qn5o_lango

# Check active container resources
docker stats --no-stream
```
