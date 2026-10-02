# Dokploy deployment

Use `docker-compose.yml` as the only service definition. On NVIDIA hosts, add `docker-compose.gpu.yml` as a second Compose file. `docker-compose.prod.yml` remains as an include-only compatibility entry point. The app services have no host-published ports, so Dokploy's proxy owns public ports and PostgreSQL, Redis, and Xinference stay on the project bridge network. Route `ai` to `website:80`, `wolinex` to `wolinex:8080`, `lango` and `dev` to `lango:4000`, and `mitambo` to `mitambo:9997`. The checked-in Nginx blocks assume that Nginx is attached to this same Compose bridge; the Compose stack leaves ports 80 and 443 for Dokploy.

Dokploy Stack/Swarm deployments cannot build services from Compose `build:` directives. The GitHub Actions workflow builds the application images from this repository on each `main` push and publishes them to `ghcr.io/wolinet-renatus/`; Dokploy pulls the `:latest` images. If the GHCR packages are private, add `ghcr.io` in Dokploy's Registry settings with a GitHub username and a token that has `read:packages`; `--with-registry-auth` only forwards credentials already configured on the deployment host. The workflow also publishes commit-tagged images for its direct production deployment. PostgreSQL and Redis use upstream runtime images; database initialization, gateway config, model sync, and other mounted configuration remain in this repository checkout.

When a local model is stopped, missing, or in cooldown, LiteLLM returns HTTP 503 with a short temporary-unavailability message for model API requests. WebUI uses the same message in chat error events and saved chat errors. Detailed provider failures remain in server logs for operators.

The `lango`, `wolinex`, and `website` services include start-first Swarm update policies with rollback monitoring. Select Dokploy's Stack/Swarm deployment mode for those policies to apply. PostgreSQL, Redis, and Xinference remain single instances with stop-first replacement; zero-downtime replacement of Xinference requires spare compute and a separate warmed inference target.

Set the variables in `.env.prod.example` as Dokploy secrets or environment values. The database URLs must use the service name `postgres`; escape reserved characters in the password before placing it in either URL. The `litellm` database is created by the Postgres image. The idempotent `db-init` service creates `webui` on both fresh and existing clusters before LiteLLM or WebUI starts. LiteLLM owns its schema migrations.

For the first Xinference deployment, leave `XINFERENCE_API_KEY` unset or set it to `bootstrap-pending`. Open Xinference through a trusted admin path, create the first administrator, then create an API key with model read access. Store that key as the Dokploy `XINFERENCE_API_KEY` secret and redeploy so LiteLLM can authenticate. Xinference's first-admin setup is first-writer-wins, so complete setup before exposing the endpoint to untrusted clients.

Xinference 3.x stores auth users, API keys, and refresh tokens in SQLite under `XINFERENCE_HOME`; the configured auth DB path is `/root/.xinference/auth/auth.db`. The `xinference_data` volume persists that database and the model cache. Xinference does not support a PostgreSQL auth connection URL. PostgreSQL remains shared by LiteLLM and WebUI, with distinct `litellm` and `webui` databases.

The `model-sync` service and `mitambo` must share a Docker network. The Compose file assigns the explicit `mitambo` network alias; sync registers currently running Xinference chat models under their live UIDs and maintains the public `Wolinet Coder` alias. Set `XINFERENCE_DEFAULT_MODEL_UID` if a particular active model should back that alias. Stopped models are removed on the next sync cycle. Open WebUI gets its model list from LiteLLM, and the database initializer removes the old hard-coded `wolinet-coder` entry.

If inference runs in another Dokploy application, attach the services to a shared network or set `XINFERENCE_FALLBACK_URLS` to a reachable Xinference base URL. The URL must serve `/v1/models` with the configured bearer key. A plain `404 page not found` at `https://mitambo.wolinet.com/status` or `/v1/models` means Dokploy has not routed that domain to the Xinference service: configure the domain target to `mitambo:9997` (or the Nginx proxy service on the same network) before using it as a fallback.

To configure cloud fallbacks, add OpenAI, xAI/Grok, or other provider models and credentials in LiteLLM, then set `WOLINET_FALLBACK_MODELS` to the exact comma-separated model IDs shown by LiteLLM. Requests for `Wolinet Coder` will try those enabled models if the local route fails.

Xinference requires `model_engine` when an LLM is launched. LiteLLM's model mapping selects the already-launched model UID and cannot choose or launch its Xinference engine. To launch the CPU GGUF profile after admin setup, run the following on the deployment host with an operator API key in `XINFERENCE_ADMIN_API_KEY`:

```sh
docker compose exec -T mitambo xinference launch \
  --endpoint http://127.0.0.1:9997 \
  --api-key "$XINFERENCE_ADMIN_API_KEY" \
  --model-engine llama.cpp \
  --model-name qwen2.5-instruct \
  --size-in-billions 7 \
  --model-format ggufv2 \
  --quantization Q4_K_M \
  --n_threads 8 \
  --n_ctx 4096
```

The selected model size, quantization, context, and thread count must fit the host's RAM/VRAM and Xinference's registered model options. On CPU instances, unconstrained models can attempt to pre-allocate full context across multiple CPU slots, triggering host/container OOM crashes (e.g. `unixsocket closed: 0 bytes read on a total of 11 expected bytes`). Always bound the context with `--n_ctx 2048 --n_parallel 1 --n-gpu none` (or specify them under Advanced Configuration in the web UI). See [Xinference CPU Model Deployment & Troubleshooting Guide](file:///Users/apple/Documents/wolinetai/docs/deployment/xinference-model-launch.md) and [`scripts/deploy/launch_cpu_model.py`](file:///Users/apple/Documents/wolinetai/scripts/deploy/launch_cpu_model.py) for the complete procedure and automated deployment script. For a GPU deployment, query the model's supported launch parameters with `xinference engine`, then set its `n_gpu_layers` to the desired offload depth; Compose device reservations expose all NVIDIA devices but cannot allocate VRAM to an individual model. `XINFERENCE_MODEL_SRC=modelscope` selects the model download source, though initial downloads still take time and require outbound access.

The Nginx 600-second timeouts cover the origin hop. Proxied Cloudflare zones have a 125-second default Proxy Read Timeout, so responses must continue producing data within that interval or the zone must have an Enterprise timeout increase. Cloudflare streams proxied responses by default; if a zone rule enables response inspection or buffering, add a path-scoped Response Body Buffering rule set to None for the streaming paths.

Run `scripts/deploy/verify-stack.sh` after a Dokploy rollout. It validates the merged Compose structure, waits for `mitambo` to become healthy, opens a connection to both PostgreSQL databases, and calls the authenticated Xinference `/status` endpoint through LiteLLM's network namespace.

## PostgreSQL backups

Run `scripts/db/backup-postgres.sh` on the Contabo host from any working directory. It streams `pg_dumpall` from the Compose `postgres` service through gzip into `${BACKUP_DIR:-<repository>/backups}/wolinet_db_<UTC timestamp>.sql.gz`, validates the gzip archive, and removes matching archives older than seven days with `find -mtime +7`. The script disables TTY allocation (`docker compose exec -T`) so terminal control bytes cannot corrupt the dump. It requires Docker Compose, `gzip`, and `flock` on the host.

The default `backups/` directory is relative to this repository root and is ignored by Git. For durable storage outside the Dokploy checkout, create a persistent host directory such as `/srv/wolinet/backups` and schedule the script with `BACKUP_DIR=/srv/wolinet/backups`. This is a host-side bind-mount/storage path: the dump is written by the host script, so do not mount or write it into the PostgreSQL data directory. Schedule it with the Contabo host's cron or systemd timer, for example:

```cron
0 2 * * * BACKUP_DIR=/srv/wolinet/backups /path/to/wolinetai/scripts/db/backup-postgres.sh >> /var/log/wolinet-postgres-backup.log 2>&1
```

Ensure the scheduler's user can access the Docker socket, the repository's Compose files, and the backup directory. The archive contains every database and role in the shared PostgreSQL cluster; restrict directory access and copy backups off-host for disaster recovery.
