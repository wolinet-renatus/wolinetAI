# Wolinet AI Desktop (Native Intel macOS App)

This folder contains the native macOS desktop application for **Wolinet AI / Litespeed**, compiled specifically for **Intel Mac (x86_64)**.

## Pre-built App
* `WolinetAI.app` (Mach-O 64-bit executable x86_64)

## How to Run
Launch directly from terminal:
```bash
./apps/desktop/run.sh
```
Or open in Finder / drag `WolinetAI.app` into `/Applications`.

## How to Re-compile
If you update any frontend code in `apps/web-client`:
```bash
./apps/desktop/build.sh
```
This runs `swiftc` with macOS SDK frameworks (`AppKit`, `WebKit`) to produce a freshly signed bundle.
