# DevOps, Binary Release & Contabo Deployment Scripts

Utility and deployment scripts for packaging, shipping, and operating the 4-stage Wolinet AI platform without exposing source code or compiling on production servers.

## Strict Zero-Compilation Server Policy
Production servers (such as Contabo Ubuntu 24.04) must **not** clone source code, install compilers (`go`, `rustc`, `cargo`, `make`), or compile `.deb` packages unless every binary distribution option is impossible.

Always build `.deb` packages on a developer workstation or CI (`make package-server`) and deploy verified binaries via either:
1. **Cloudflare R2 Binary Release (Recommended)**:
   - Publish pre-built `.deb` packages, `.sha256` sidecars, and installer assets from your workstation (zero source code):
     ```bash
     ./scripts/publish-r2-release.sh --bucket wolinetai --prefix releases/latest
     ```
   - Install or upgrade on a production server using [`install-from-r2.sh`](install-from-r2.sh) (downloads verified binaries from R2 into `/tmp`, removes `/opt/wolinetai` if present, installs Stages 1–4, configures Cloudflare Origin CA SSL + DNS + Nginx + UFW + 6-hourly R2 backups, and cleans `/tmp`).
2. **Direct Workstation SSH Stream**:
   - Stream pre-built `.deb` packages and installer scripts directly from your workstation over SSH (`scripts/deploy-contabo-ssh.sh`), automatically cleaning remote staging and any source checkout after install.

Only use `bootstrap-contabo.sh` (in-place source build) if pre-built `amd64` packages cannot be produced offline or fetched from R2/SSH.

## Key Scripts
- **`publish-r2-release.sh`**: Uploads the 4 `.deb` packages, `.sha256` checksums, Lango `/ui` assets, and installer scripts to Cloudflare R2 (`releases/latest/`).
- **`install-from-r2.sh`**: Zero-source production server installer that pulls verified `.deb` binaries from R2, installs Stages 1–4, runs DB migrations/seeding, sets up Nginx/Cloudflare edge + R2 backups, and cleans up temporary files.
- **`deploy-contabo-ssh.sh`**: Streams pre-built local `.deb`s and edge/backup setup straight to a remote Ubuntu 24.04 server over SSH.
- **`install-server-stack.sh`**: Installs Stage 1 (`orchestrator` + `pgvector/pgvector:pg16` + Redis) -> Stage 2 (`mitambo`) -> Stage 3 (`lango`) -> Stage 4 (`wolinex-web`), runs `wolinet-orchestrator migrate-seed`, and applies hardware-proportional systemd limits.
- **`setup-contabo-edge.sh`**: Pins internal services to `127.0.0.1`, issues 15-year Cloudflare Origin CA certificates, configures Host Nginx keepalive/rate-limiting/HSTS vhosts (`*.wolinet.com`), hardens UFW + `systemd-resolved`, and enforces Cloudflare `Full (Strict)` SSL + DNS.
- **`setup-r2-backup.sh`**: Configures Wolinex Web S3 uploads to R2 and installs `/usr/local/bin/wolinet-backup-r2`, `/usr/local/bin/wolinet-restore-r2`, and the 6-hourly `wolinet-backup.timer`.
- **`install-wolinex-client.sh`**: Installs workstation client downloads (`wolinex-cli` / desktop client) separately from server stacks.
- **`start_platform.sh` / `register_models.sh` / `healthcheck.sh`**: Local dev helpers (or via `Makefile`: `make start`, `make register`, `make health`).

## Disaster Recovery (Backup & Restore)
On a provisioned server:
```bash
sudo /usr/local/bin/wolinet-backup-r2       # Take immediate snapshot to R2
sudo /usr/local/bin/wolinet-restore-r2 --list # List available R2 snapshots
sudo /usr/local/bin/wolinet-restore-r2        # Restore latest Postgres chat/keys, SQLite, & configs
```
