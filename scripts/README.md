# DevOps & Automation Scripts

Utility scripts for managing the lifecycle, registration, and health of the Wolinet AI platform.

## Scripts
- **`start_platform.sh`**: Launches both the Xinference Engine (`http://127.0.0.1:9997`) and the LiteLLM AI Gateway (`http://127.0.0.1:4000`), waiting until both are ready.
- **`register_models.sh`**: Scans `models/registrations/*.json` and registers each custom model spec with the running Xinference engine.
- **`healthcheck.sh`**: Validates engine responsiveness, gateway status, and executes an actual test inference against `wolinex-coder`.

## Usage
All scripts can be invoked directly or via the root `Makefile`:
```bash
make start       # Runs ./scripts/start_platform.sh
make register    # Runs ./scripts/register_models.sh
make health      # Runs ./scripts/healthcheck.sh
```
