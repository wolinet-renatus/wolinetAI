# WOLINET SYSTEM ARCHITECTURE & SOVEREIGN ENGINE SPECIFICATION

## SYSTEM SPECIFICATION: BACKEND ORCHESTRATOR & INFRASTRUCTURE ENGINE

## MANDATORY COMPILATION & ARCHITECTURAL PATTERNS FOR CODING AGENTS

---

## 1. STRATEGIC ARCHITECTURAL MANDATES

### OVERVIEW & OBJECTIVE

You are an expert system engineer building the sovereign Wolinet Backend Platform. We are entirely bypassing third-party platform runtimes like Coolify (due to resource latency) and Dokploy (due to multi-node cluster complexity). Instead, we are re-engineering the open-source, high-performance Go-based core engine of 1Panel into a completely sovereign, single-binary container orchestrator named *1apanel*.

This system will natively orchestrate our core AI components:
1.⁠ ⁠*Mitambo (Inference Core):* Powered by Xinference, executing quantized local GGUF models completely within VRAM boundaries to eliminate SSD streaming lag.
2.⁠ ⁠*Lago (Gateway Layer):* Powered by LiteLLM, handling API authentication, token usage logging via local Lago usage metrics, and failover routing to external cloud provider models.
3.⁠ ⁠*WolinEx Coder Studio:* The flagship web application and agentic IDE client that connects directly to the local model mesh.

---

### DO AND DO NOT CORE CODING CONSTRAINTS

#### 🟢 DO (Mandatory Architectural Requirements)

•⁠  ⁠*Write Core Routines in Pure Go:* Every infrastructure controller, database synchronization hook, and lifecycle state manager must be written in performance-optimized Golang.
•⁠  ⁠*Target Rootless Podman & Quadlets:* All underlying multi-container applications must be orchestrated natively using rootless, daemonless Podman via Systemd Quadlet files (⁠ .container ⁠ and ⁠ .pod ⁠).
•⁠  ⁠*Enforce Host Networking Model:* Group Mitambo, Lago, and the WolinEx Coder UI into a single Podman Pod using ⁠ network_mode: "host" ⁠. All inter-container communication must go through ⁠ 127.0.0.1 ⁠ over internal loop ports to guarantee absolute zero virtual bridge network latency.
•⁠  ⁠*Integrate Cloudflare V4 Edge APIs:* Intercept the existing website creation module. When a user creates a domain or website via the GUI, the Go backend must programmatically map, proxy, and secure the DNS records via Cloudflare's Edge API.
•⁠  ⁠*Isolate Data Storage Scopes:* Keep 1apanel's configuration state within an isolated, internal SQLite database file (⁠ 1apanel.db ⁠). Route all production user data, billing tracking, and chat history metrics from Lago and the Web-Client directly to a dedicated, high-performance local PostgreSQL container cluster.

#### 🔴 DO NOT (Strict Prohibitions)

•⁠  ⁠*NO External Control Panels:* Do not introduce dependencies on Dokploy, Coolify, aaPanel, or standard 1Panel upstream vendor distribution pipelines. This repository is entirely sovereign.
•⁠  ⁠*NO Hardcoded Credentials or IPs:* Absolutely zero hardcoded IP addresses, access keys, database passwords, or Cloudflare tokens inside the codebase, templates, or Composes. Everything must resolve via runtime environment variables (⁠ .env ⁠).
•⁠  ⁠*NO Raw Source Files on Production Environments:* Never write scripts that clone raw source directories directly onto the target server. The production server must only handle secure, obfuscated, and compiled binary executables.
•⁠  ⁠*NO Global Upstream Go Imports:* Do not import any packages using the ⁠ ://github.com ⁠ namespace. All modules must reference the local sovereign module namespace.

---

## 2. REPOSITORY MANAGEMENT & FORKING STRATEGY

To sever upstream vendor tracking and initialize a clean, lightweight workspace optimized for AI context limits, execute this exact initialization script:

⁠ bash

# !/bin/bash

set -e

# 1. Establish pristine project directory structures

mkdir -p wolinetai-orchestrator/1apanel-core
cd wolinetai-orchestrator

# 2. Pull down the open-source Go blueprint layer

git clone --depth=1 https://://github.com.git upstream-panel

# 3. Initialize sovereign Git repository boundaries

cd 1apanel-core
git init
git checkout -b main

# 4. Extract core Go components, dropping upstream documentation and vendor pipelines

cp -r ../upstream-panel/* .
cp ../upstream-panel/.gitignore . 2>/dev/null || true
rm -rf .github/ docs/ extra/

# 5. Transition namespaces to the custom Wolinet Ecosystem module path

find . -type f -name "*.go" -exec sed -i 's|://github.com|://github.com|g' {} +
sed -i 's|module ://github.com|module ://github.com|g' go.mod

# 6. Sanitize and lock down the local Go module definitions

go mod tidy
 ⁠

---

## 3. CONTAINER DEPLOYMENT TOPOLOGY: PODMAN QUADLETS

To deploy the entire AI platform without a root background daemon, translate your deployment requirements into the native Podman Systemd Quadlet configurations below. Place these templates inside ⁠ backend/app/template/ ⁠.

### A. The Master Network Namespace Pod Profile

*File Name:* ⁠ backend/app/template/wolinetai.pod ⁠
⁠ ini
[Pod]
PodName=wolinetai-core-pod

# Expose only the vital external entry ports to your protected internal network

PublishPort=8080:8080
PublishPort=4000:4000
 ⁠

### B. Mitambo (Inference Engine) Layer

*File Name:* ⁠ backend/app/template/mitambo-inference.container ⁠
⁠ ini
[Container]
ContainerName=wolinet-mitambo
Pod=wolinetai-core-pod
Image=localhost/wolinetai-inference:local-source
Volume=/var/lib/wolinet/models:/app/models:Z
Environment=XINFERENCE_HOME=/app/models

# Natively map host hardware accelerators (CPUs, GPUs, TPUs) via CDI drivers

AddDevice=://nvidia.com
AddDevice=://google.com

[Service]
Restart=always
 ⁠

### C. Lango (Gateway & Cloud Failover) Layer

*File Name:* ⁠ backend/app/template/lago-gateway.container ⁠
⁠ ini
[Container]
ContainerName=wolinet-lago
Pod=wolinetai-core-pod
Image=localhost/wolinetai-gateway:local-source
Environment=DATABASE_URL=postgresql://wolinet_user:wolinet_pass@127.0.0.1:5432/auth.db
Exec=litellm --config /app/config.yaml

[Service]
Restart=always
 ⁠

---

## 4. GO CORE SERVICE CONTROLLER CODE IMPLEMENTATIONS

### A. App Buttons Graphical Orchestration (ON / OFF / PATCH)

To connect the dashboard's user interface action buttons directly to your rootless Podman execution layers, replace your container interaction logic with this Go service file:

*File Name:* ⁠ backend/app/service/container.go ⁠
⁠ go
package service

import (
 "context"
 "os/exec"
)

type PodmanEngine struct{}

// ToggleAppService controls the On/Off panel switches for individual containers
func (p *PodmanEngine) ToggleAppService(ctx context.Context, containerName string, action string) error {
 // action can be: "start" (ON), "stop" (OFF), or "restart"
 cmd := exec.CommandContext(ctx, "podman", action, containerName)
 return cmd.Run()
}

// HotPatchContainer handles the application update flow without dropping sister container instances
func (p *PodmanEngine) HotPatchContainer(ctx context.Context, imageTag string, containerName string) error {
 // 1. Pull down revised container image layers from your secure local registry
 pullCmd := exec.CommandContext(ctx, "podman", "pull", imageTag)
 if err := pullCmd.Run(); err != nil {
  return err
 }

 // 2. Cycle only the targeted application container inside the active pod
 restartCmd := exec.CommandContext(ctx, "podman", "restart", containerName)
 return restartCmd.Run()
}
 ⁠

### B. Cloudflare Edge Security & Domain Automation Route

To bind domain creations to Cloudflare's secure reverse proxies automatically, rewrite the website routing initialization layer:

*File Name:* ⁠ backend/app/api/v1/website.go ⁠
⁠ go
package v1

import (
 "bytes"
 "net/http"
 "://github.com"
)

type CloudflareDomainRequest struct {
 Domain string `json:"domain"`
 Target string `json:"target"`
}

// CustomWebsiteLaunch intercepts the site creation wizard to hook in Cloudflare Edge Proxies
func CustomWebsiteLaunch(c *gin.Context) {
 var req CloudflareDomainRequest
 if err := c.ShouldBindJSON(&req); err != nil {
  c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
  return
 }

 // 1. Trigger the standard 1Panel local reverse proxy/OpenResty setups here
 // [Original Internal 1Panel Engine Call Goes Here]

 // 2. Synchronize configuration profiles with the Cloudflare V4 DNS Endpoint
 cfToken := "YOUR_CLOUDFLARE_API_TOKEN"
 cfZoneID := "YOUR_ZONE_ID"
 cfURL := "<https://cloudflare.com>" + cfZoneID + "/dns_records"

 jsonData := []byte(`{
  "type": "A",
  "name": "` + req.Domain + `",
  "content": "` + req.Target + `",
  "ttl": 1,
  "proxied": true
 }`)

 clientReq, _ := http.NewRequest("POST", cfURL, bytes.NewBuffer(jsonData))
 clientReq.Header.Set("Authorization", "Bearer "+cfToken)
 clientReq.Header.Set("Content-Type", "application/json")

 client := &http.Client{}
 resp, err := client.Do(clientReq)
 if err != nil || resp.StatusCode != http.StatusOK {
  c.JSON(http.StatusInternalServerError, gin.H{"status": "Local proxy active, Cloudflare API sync failed"})
  return
 }

 c.JSON(http.StatusOK, gin.H{"status": "Website deployed and proxied securely via Cloudflare Edge"})
}
 ⁠

---

## 5. REVERSE-ENGINEERING RIGID DEFENSE & COMPILATION ENGINE

To ensure zero intellectual property exposure if a malicious actor gains access to your host machine or container layers, you must obfuscate your Go codebases before deployment.

### A. Multi-Stage Sovereign Obfuscation Engine

*File Name:* ⁠ Dockerfile.1apanel ⁠

```dockerfile
# ========================================================
# STAGE 1: Compiling Obfuscated Go Code via Garble toolchain
# ========================================================
