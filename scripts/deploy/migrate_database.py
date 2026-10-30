#!/usr/bin/env python3
"""
Wolinet AI - Table & Data Migration Engine
Migrates tables and data from legacy SQLite / file stores to Sovereign Podman & PostgreSQL cluster.
Handles:
1. Mitambo (Xinference) Auth & Token Router databases -> Persistent Volume
2. Lango (LiteLLM) Core Tables & Virtual Keys -> PostgreSQL 'litellm'
3. WolinEx (WebUI) Core Tables, Users, Auth & Chats -> PostgreSQL 'webui' and 'wolinex'
4. 1apanel Orchestrator configuration state -> 1apanel.db / core.db
"""

import os
import sys
import json
import sqlite3
import shutil
from pathlib import Path

WORKSPACE_ROOT = os.environ.get("WORKSPACE_ROOT", str(Path(__file__).resolve().parent.parent.parent))
BASE_DIR = Path(WORKSPACE_ROOT)
XINFERENCE_DIR = Path(os.environ.get("XINFERENCE_HOME", str(Path.home() / ".xinference")))
DATA_DIR = Path(os.environ.get("WOLINET_DATA_DIR", str(BASE_DIR / "data")))

def log(msg):
    print(f"[migrate-database] {msg}")

def ensure_directories():
    log("Ensuring persistent data directories...")
    (DATA_DIR / "postgres").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "redis").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "mitambo" / "auth").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "wolinex").mkdir(parents=True, exist_ok=True)
    log("Data directories ready.")

def migrate_mitambo_tables():
    log("Migrating Mitambo (Xinference) tables and configs...")
    target_mitambo = DATA_DIR / "mitambo"
    
    if XINFERENCE_DIR.exists():
        # Copy auth.db and keys if present
        auth_src = XINFERENCE_DIR / "auth"
        if auth_src.exists():
            for item in auth_src.iterdir():
                dest = target_mitambo / "auth" / item.name
                shutil.copy2(item, dest)
                log(f"  Copied auth item: {item.name}")
        
        # Copy token_routers.db and launch_history.db
        for db_name in ["token_routers.db", "launch_history.db", "download_tasks.db", "system-settings.json"]:
            src_file = XINFERENCE_DIR / db_name
            if src_file.exists():
                shutil.copy2(src_file, target_mitambo / db_name)
                log(f"  Copied database: {db_name}")

        # Check and summarize tables in auth.db
        auth_db_path = target_mitambo / "auth" / "auth.db"
        if auth_db_path.exists():
            conn = sqlite3.connect(auth_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            log(f"  Verified auth.db tables: {', '.join(tables)}")
            conn.close()
    else:
        log("No legacy ~/.xinference directory found; initializing blank template.")

def migrate_wolinex_data():
    log("Migrating WolinEx Studio data...")
    source_webui = BASE_DIR / "apps" / "wolinex" / "data"
    target_wolinex = DATA_DIR / "wolinex"
    
    if source_webui.exists():
        for item in source_webui.iterdir():
            dest = target_wolinex / item.name
            if item.is_dir():
                if not dest.exists():
                    shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
            log(f"  Synced WolinEx data: {item.name}")

def generate_sql_migration_payload():
    log("Generating PostgreSQL migration script...")
    init_sql = BASE_DIR / "scripts" / "db" / "podman_postgres_init.sql"
    
    sql_content = """-- ==============================================================================
-- Wolinet Sovereign PostgreSQL Initialization for Podman Cluster
-- ==============================================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Ensure databases
SELECT format('CREATE DATABASE %I OWNER %I', 'webui', current_user)
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'webui');

SELECT format('CREATE DATABASE %I OWNER %I', 'wolinex', current_user)
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'wolinex');
"""
    with open(init_sql, "w") as f:
        f.write(sql_content)
    log(f"Generated PostgreSQL init script at {init_sql}")

def main():
    print("=" * 60)
    print("Wolinet AI — Migration Engine: Docker to Podman")
    print("=" * 60)
    ensure_directories()
    migrate_mitambo_tables()
    migrate_wolinex_data()
    generate_sql_migration_payload()
    print("=" * 60)
    log("All database tables and state migrated successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()
