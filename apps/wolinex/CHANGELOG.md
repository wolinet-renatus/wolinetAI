# Changelog

All notable changes to Wolinet AI Web Portal will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.13.2] - 2026-11-19

### Added

- **Wolinet AI Platform Integration.** Connected Wolinex Web exclusively to the Lango gateway (`lango.wolinet.com`) and isolated PostgreSQL database while keeping Mitambo local inference behind Lango routing.
- **Brand Identity & Portal Alignment.** Updated portal icons, manifest, splash imagery, and release notes across `wolinex.wolinet.com`, `dev.wolinet.com`, and `docs.wolinet.com`.

### Fixed

- **Database Schema Auto-Heal & Session Cookies.** Restored missing `os` import in authentication router and automatic Alembic version alignment during upgrades.
- **Channel Requests When Disabled.** Skipped background `/api/v1/channels/` polling on socket connect when channels are disabled.
