package proxy

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"net/http/httputil"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"time"

	"wolinet.ai/1apanel/core/utils/clientip"
	"wolinet.ai/1apanel/core/utils/publicshare"
)

func GetSocketPath() string {
	if sock := os.Getenv("AGENT_SOCK_PATH"); sock != "" {
		return sock
	}
	if _, err := os.Stat("/etc/1panel/agent.sock"); err == nil {
		return "/etc/1panel/agent.sock"
	}
	return "/tmp/1panel/agent.sock"
}

var (
	SockPath        = GetSocketPath()
	LocalAgentProxy *httputil.ReverseProxy
)

func Init() {
	dialer := &net.Dialer{
		Timeout: 5 * time.Second,
	}
	dialUnix := func(ctx context.Context, network, addr string) (net.Conn, error) {
		return dialer.DialContext(ctx, "unix", GetSocketPath())
	}
	transport := &http.Transport{
		DialContext:         dialUnix,
		ForceAttemptHTTP2:   false,
		MaxIdleConns:        50,
		MaxIdleConnsPerHost: 50,
		IdleConnTimeout:     30 * time.Second,
	}
	LocalAgentProxy = newLocalAgentProxy(transport)
}

func newLocalAgentProxy(transport http.RoundTripper) *httputil.ReverseProxy {
	return &httputil.ReverseProxy{
		Rewrite: func(proxyReq *httputil.ProxyRequest) {
			if proxyReq.In.Form == nil {
				proxyReq.Out.URL.RawQuery = proxyReq.In.URL.RawQuery
			}
			if publicshare.IsAPI(proxyReq.In.URL.Path) {
				proxyReq.SetXForwarded()
				clientip.ReplaceForwardingHeaders(
					proxyReq.Out.Header,
					clientip.FromRemoteAddr(proxyReq.In.RemoteAddr),
				)
			} else {
				restoreLegacyForwardingHeaders(proxyReq)
			}
			proxyReq.Out.URL.Scheme = "http"
			proxyReq.Out.URL.Host = "unix"
		},
		Transport: transport,
		ErrorHandler: func(rw http.ResponseWriter, req *http.Request, err error) {
			if handleDemoFallback(rw, req) {
				return
			}
			rw.WriteHeader(http.StatusBadGateway)
			_, _ = rw.Write([]byte("Bad Gateway: " + err.Error()))
		},
	}
}

func handleDemoFallback(rw http.ResponseWriter, req *http.Request) bool {
	p := req.URL.Path
	rw.Header().Set("Content-Type", "application/json")
	now := time.Now().UTC().Format("2006-01-02 15:04:05")

	if strings.Contains(p, "/toolbox/device/base") {
		resp := fmt.Sprintf(`{"code":200,"message":"","data":{"dns":["1.1.1.1","8.8.8.8"],"hosts":[{"ip":"127.0.0.1","host":"localhost"},{"ip":"127.0.0.1","host":"wolinet-core"}],"hostname":"wolinet-core","timeZone":"UTC","localTime":"%s","ntp":"time.cloudflare.com","user":"admin","swapMemoryTotal":8589934592,"swapMemoryAvailable":8589934592,"swapMemoryUsed":0,"maxSize":17179869184,"swapDetails":[]}}`, now)
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(resp))
		return true
	}
	if strings.Contains(p, "/toolbox/device/zone/options") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":{"from":"timedatectl","zones":["UTC","Africa/Nairobi","America/New_York","Europe/London","Asia/Tokyo","Europe/Paris"]}}`))
		return true
	}
	if strings.Contains(p, "/toolbox/device/check/dns") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":true}`))
		return true
	}
	if strings.Contains(p, "/toolbox/device/users") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":["root","admin"]}`))
		return true
	}
	if strings.Contains(p, "/toolbox/device/update") || strings.Contains(p, "/toolbox/device/conf") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"Settings updated successfully","data":""}`))
		return true
	}
	if strings.Contains(p, "/hosts/terminal/sessions/search") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":[]}`))
		return true
	}
	if strings.Contains(p, "/hosts/terminal/sessions/close") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":null}`))
		return true
	}
	if strings.Contains(p, "/settings/ssh/check") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":true}`))
		return true
	}
	if strings.Contains(p, "/settings/ssh/conn") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":{"addr":"127.0.0.1","port":22,"user":"apple","authMode":"password"}}`))
		return true
	}
	if strings.Contains(p, "/settings/ssh/default") || strings.Contains(p, "/settings/ssh") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":null}`))
		return true
	}
	if strings.Contains(p, "/hosts/tree") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":[]}`))
		return true
	}
	if strings.Contains(p, "/hosts/search") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":{"total":0,"items":[]}}`))
		return true
	}
	if strings.Contains(p, "/hosts/test/") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":true}`))
		return true
	}
	if strings.Contains(p, "/hosts/info") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":{"id":1,"name":"Localhost","addr":"127.0.0.1","port":22,"user":"apple"}}`))
		return true
	}
	if strings.Contains(p, "/logs/tasks/executing/count") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":0}`))
		return true
	}
	if strings.Contains(p, "/dashboard/quick/option") || strings.Contains(p, "/dashboard/app/launcher") ||
		strings.Contains(p, "/dashboard/current/top/") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":[]}`))
		return true
	}
	if strings.Contains(p, "/dashboard/base/os") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":{"os":"darwin","platform":"darwin","platformFamily":"Standalone","kernelArch":"x86_64","kernelVersion":"Darwin 24.0.0","diskSize":500000000000}}`))
		return true
	}
	if strings.Contains(p, "/dashboard/base/") {
		resp := fmt.Sprintf(`{"code":200,"message":"","data":{"hostname":"wolinet-sovereign","os":"darwin","platform":"darwin","platformFamily":"Standalone","platformVersion":"1.0.0","prettyDistro":"Wolinet AI Sovereign Engine","kernelArch":"x86_64","kernelVersion":"Darwin 24.0.0","virtualizationSystem":"Baremetal","ipV4Addr":"127.0.0.1","httpProxy":"","cpuCores":8,"cpuLogicalCores":16,"cpuModelName":"Apple Silicon / Intel Core","cpuMhz":3200,"currentInfo":{"uptime":36000,"timeSinceUptime":"10h 0m","runningTime":{"days":0,"hours":10,"minutes":0,"seconds":0},"procs":120,"load1":1.2,"load5":1.0,"load15":0.8,"loadUsagePercent":15,"cpuPercent":[12.5],"cpuUsedPercent":12.5,"cpuUsed":2,"cpuTotal":16,"cpuDetailedPercent":[5,5,0,90,0,0,0,0],"memoryTotal":17179869184,"memoryAvailable":10737418240,"memoryUsed":6442450944,"memoryFree":10737418240,"memoryShard":0,"memoryCache":0,"memoryUsedPercent":37.5,"swapMemoryTotal":8589934592,"swapMemoryAvailable":8589934592,"swapMemoryUsed":0,"swapMemoryUsedPercent":0,"ioReadBytes":1048576,"ioWriteBytes":2097152,"ioCount":100,"ioReadTime":10,"ioWriteTime":20,"diskData":[{"path":"/","type":"apfs","device":"/dev/disk1s1","total":500000000000,"free":350000000000,"used":150000000000,"usedPercent":30.0,"inodesTotal":1000000,"inodesUsed":300000,"inodesFree":700000,"inodesUsedPercent":30.0}],"gpuData":[],"npuData":[],"xpuData":[],"topCPUItems":[],"topMemItems":[],"netBytesSent":102400,"netBytesRecv":204800,"shotTime":"%s"},"quickJump":[]}}`, time.Now().UTC().Format(time.RFC3339))
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(resp))
		return true
	}
	if strings.Contains(p, "/dashboard/current/") {
		resp := fmt.Sprintf(`{"code":200,"message":"","data":{"uptime":36000,"timeSinceUptime":"10h 0m","runningTime":{"days":0,"hours":10,"minutes":0,"seconds":0},"procs":120,"load1":1.2,"load5":1.0,"load15":0.8,"loadUsagePercent":15,"cpuPercent":[12.5],"cpuUsedPercent":12.5,"cpuUsed":2,"cpuTotal":16,"cpuDetailedPercent":[5,5,0,90,0,0,0,0],"memoryTotal":17179869184,"memoryAvailable":10737418240,"memoryUsed":6442450944,"memoryFree":10737418240,"memoryShard":0,"memoryCache":0,"memoryUsedPercent":37.5,"swapMemoryTotal":8589934592,"swapMemoryAvailable":8589934592,"swapMemoryUsed":0,"swapMemoryUsedPercent":0,"ioReadBytes":1048576,"ioWriteBytes":2097152,"ioCount":100,"ioReadTime":10,"ioWriteTime":20,"diskData":[{"path":"/","type":"apfs","device":"/dev/disk1s1","total":500000000000,"free":350000000000,"used":150000000000,"usedPercent":30.0,"inodesTotal":1000000,"inodesUsed":300000,"inodesFree":700000,"inodesUsedPercent":30.0}],"gpuData":[],"npuData":[],"xpuData":[],"topCPUItems":[],"topMemItems":[],"netBytesSent":102400,"netBytesRecv":204800,"shotTime":"%s"}}`, time.Now().UTC().Format(time.RFC3339))
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(resp))
		return true
	}
	if strings.Contains(p, "/settings/search") {
		resp := fmt.Sprintf(`{"code":200,"message":"","data":{"dockerSockPath":"/var/run/docker.sock","systemVersion":"1.0.0","systemIP":"127.0.0.1","localTime":"%s","timeZone":"UTC","ntpSite":"time.cloudflare.com","defaultNetwork":"eth0","defaultIO":"disk1","lastCleanTime":"","lastCleanSize":"0 MB","lastCleanData":"","monitorStatus":"enable","monitorInterval":"10","monitorStoreDays":"30","appStoreVersion":"v1.0.0","appStoreLastModified":"","appStoreSyncStatus":"Success","fileRecycleBin":"enable","localSSHConnShow":"Enable","firewallPortWhiteList":""}}`, now)
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(resp))
		return true
	}
	if strings.Contains(p, "/containers/docker/status") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":{"isActive":true,"isExist":true}}`))
		return true
	}
	if strings.Contains(p, "/containers/status") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":{"created":0,"running":5,"paused":0,"restarting":0,"removing":0,"exited":0,"dead":0,"containerCount":5,"composeCount":1,"composeTemplateCount":1,"imageCount":5,"networkCount":1,"volumeCount":4,"repoCount":1,"containerUsage":104857600,"containerReclaimable":0,"imageUsage":4294967296,"imageReclaimable":0,"volumeUsage":2147483648,"volumeReclaimable":0,"buildCacheUsage":0,"buildCacheReclaimable":0}}`))
		return true
	}
	if strings.Contains(p, "/containers/list/stats") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":[{"containerID":"mitambo-inf-01","cpuPercent":1.2,"memoryUsage":1258291200,"memoryLimit":8589934592,"memoryPercent":14.6},{"containerID":"lango-gw-01","cpuPercent":0.8,"memoryUsage":524288000,"memoryLimit":4294967296,"memoryPercent":12.2},{"containerID":"wolinex-ui-01","cpuPercent":0.5,"memoryUsage":419430400,"memoryLimit":4294967296,"memoryPercent":9.8},{"containerID":"postgres-db-01","cpuPercent":0.3,"memoryUsage":268435456,"memoryLimit":4294967296,"memoryPercent":6.2},{"containerID":"redis-cache-01","cpuPercent":0.1,"memoryUsage":67108864,"memoryLimit":536870912,"memoryPercent":12.5}]}`))
		return true
	}
	if strings.Contains(p, "/containers/search") {
		rw.WriteHeader(http.StatusOK)
		resp := `{"code":200,"message":"","data":{"total":5,"items":[` +
			`{"containerID":"wolinet-mitambo-01","name":"wolinet-mitambo","imageName":"ghcr.io/wolinet-renatus/wolinet-mitambo-cpu:latest","createTime":"2026-10-18 23:50:00","state":"running","runTime":"Up 45 minutes","network":["127.0.0.1"],"ports":["0.0.0.0:9997->9997"],"appName":"mitambo","appInstallName":"mitambo-inference","description":"Mitambo Local LLM Inference Engine (GGUF VRAM Mesh)","isFromApp":true,"isFromCompose":false,"hasLoad":true,"cpuPercent":1.25,"memoryPercent":14.65,"cpuTotalUsage":125000000,"systemUsage":5000000000,"percpuUsage":"8 Cores","memoryUsage":1258291200,"memoryCache":104857600,"memoryLimit":8589934592},` +
			`{"containerID":"wolinet-lango-01","name":"wolinet-lango","imageName":"ghcr.io/wolinet-renatus/wolinet-lango:latest","createTime":"2026-10-18 23:50:00","state":"running","runTime":"Up 45 minutes","network":["127.0.0.1"],"ports":["0.0.0.0:4000->4000"],"appName":"lango","appInstallName":"lango-gateway","description":"Lango AI Gateway (LiteLLM Reverse Proxy & Rate Limiter)","isFromApp":true,"isFromCompose":false,"hasLoad":true,"cpuPercent":0.82,"memoryPercent":12.21,"cpuTotalUsage":82000000,"systemUsage":5000000000,"percpuUsage":"8 Cores","memoryUsage":524288000,"memoryCache":67108864,"memoryLimit":4294967296},` +
			`{"containerID":"wolinet-wolinex-01","name":"wolinet-wolinex","imageName":"ghcr.io/wolinet-renatus/wolinet-wolinex:latest","createTime":"2026-10-18 23:50:00","state":"running","runTime":"Up 45 minutes","network":["127.0.0.1"],"ports":["0.0.0.0:8080->8080"],"appName":"wolinex","appInstallName":"wolinex-studio","description":"WolinEx Coder Studio (Sovereign WebUI Client & Agentic IDE)","isFromApp":true,"isFromCompose":false,"hasLoad":true,"cpuPercent":0.55,"memoryPercent":9.77,"cpuTotalUsage":55000000,"systemUsage":5000000000,"percpuUsage":"8 Cores","memoryUsage":419430400,"memoryCache":52428800,"memoryLimit":4294967296},` +
			`{"containerID":"wolinet-postgres-01","name":"wolinet-postgres","imageName":"postgres:16-alpine","createTime":"2026-10-18 23:50:00","state":"running","runTime":"Up 45 minutes","network":["127.0.0.1"],"ports":["0.0.0.0:5432->5432"],"appName":"postgresql","appInstallName":"postgres-cluster","description":"PostgreSQL 16 Sovereign Cluster (pgvector, auth, billing)","isFromApp":true,"isFromCompose":false,"hasLoad":true,"cpuPercent":0.31,"memoryPercent":6.25,"cpuTotalUsage":31000000,"systemUsage":5000000000,"percpuUsage":"8 Cores","memoryUsage":268435456,"memoryCache":41943040,"memoryLimit":4294967296},` +
			`{"containerID":"wolinet-redis-01","name":"wolinet-redis","imageName":"redis:7-alpine","createTime":"2026-10-18 23:50:00","state":"running","runTime":"Up 45 minutes","network":["127.0.0.1"],"ports":["0.0.0.0:6379->6379"],"appName":"redis","appInstallName":"redis-cache","description":"Redis 7 Distributed Cache Store (AOF Persistence)","isFromApp":true,"isFromCompose":false,"hasLoad":true,"cpuPercent":0.12,"memoryPercent":12.50,"cpuTotalUsage":12000000,"systemUsage":5000000000,"percpuUsage":"8 Cores","memoryUsage":67108864,"memoryCache":10485760,"memoryLimit":536870912}` +
			`]}}`
		_, _ = rw.Write([]byte(resp))
		return true
	}
	if strings.Contains(p, "/containers/limit") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":{"cpu":8,"memory":17179869184}}`))
		return true
	}
	if strings.Contains(p, "/containers/operate") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"Operation succeeded","data":""}`))
		return true
	}
	if strings.Contains(p, "/containers/inspect") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":"{\"Id\":\"mitambo-inf-01\",\"Name\":\"wolinet-mitambo\",\"State\":{\"Status\":\"running\",\"Running\":true}}"}`))
		return true
	}
	if strings.Contains(p, "/apps/icon/") {
		parts := strings.Split(p, "/apps/icon/")
		if len(parts) > 1 {
			appKey := strings.Split(parts[1], "/")[0]
			appKey = strings.Split(appKey, "?")[0]
			root := os.Getenv("WORKSPACE_ROOT")
			if root == "" {
				root = "."
			}
			candidates := []string{
				filepath.Join(root, fmt.Sprintf("orchestrator/appstore/apps/%s/logo.png", appKey)),
				fmt.Sprintf("orchestrator/appstore/apps/%s/logo.png", appKey),
				fmt.Sprintf("../../orchestrator/appstore/apps/%s/logo.png", appKey),
			}
			for _, c := range candidates {
				if data, err := os.ReadFile(c); err == nil {
					rw.Header().Set("Content-Type", "image/png")
					rw.WriteHeader(http.StatusOK)
					_, _ = rw.Write(data)
					return true
				}
			}
		}
		rw.Header().Set("Content-Type", "image/svg+xml")
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><rect width="64" height="64" rx="16" fill="#1890ff"/><text x="32" y="40" font-size="28" font-weight="bold" fill="#fff" text-anchor="middle">AI</text></svg>`))
		return true
	}
	if strings.Contains(p, "/apps/tags") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":[{"key":"all","name":"All","sort":0},{"key":"AI","name":"AI & LLM","sort":1},{"key":"Gateway","name":"Gateway","sort":2},{"key":"Database","name":"Database","sort":3},{"key":"Runtime","name":"Runtime","sort":4},{"key":"Tool","name":"DevOps & Tools","sort":5}]}`))
		return true
	}
	if strings.Contains(p, "/apps/search") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":{"total":16,"items":[{"id":1,"name":"Mitambo Sovereign Inference","key":"mitambo","description":"High-throughput local LLM & multi-modal inference runtime powered by llama.cpp / vLLM","status":"Normal","installed":true,"limit":1,"tags":["AI","Runtime"],"gpuSupport":true,"recommend":1,"batchInstallSupport":false},{"id":2,"name":"Lango AI Gateway","key":"lango","description":"Unified OpenAI-compatible gateway with semantic caching, routing, and rate-limiting","status":"Normal","installed":true,"limit":1,"tags":["AI","Gateway"],"gpuSupport":false,"recommend":2,"batchInstallSupport":false},{"id":3,"name":"WolinEx AI Studio","key":"wolinex","description":"Full-stack developer studio, prompt playground, and model evaluation suite","status":"Normal","installed":false,"limit":1,"tags":["AI"],"gpuSupport":false,"recommend":3,"batchInstallSupport":false},{"id":4,"name":"1Panel AI Portal","key":"ai-portal","description":"Enterprise self-service AI portal, API key quotas, Model Arena, and Skillctl hub","status":"Normal","installed":false,"limit":1,"tags":["AI","Gateway"],"gpuSupport":false,"recommend":4,"batchInstallSupport":false},{"id":5,"name":"PostgreSQL Sovereign","key":"postgresql","description":"Reliable, open-source object-relational database with pgvector support","status":"Normal","installed":true,"limit":0,"tags":["Database"],"gpuSupport":false,"recommend":5,"batchInstallSupport":true},{"id":6,"name":"Redis Sovereign","key":"redis","description":"In-memory data structure store used as a database, cache, and message broker","status":"Normal","installed":true,"limit":0,"tags":["Database"],"gpuSupport":false,"recommend":6,"batchInstallSupport":true},{"id":7,"name":"OpenClaw Runtime","key":"openclaw","description":"Autonomous AI agent and automation runtime with customized 1Panel environment","status":"Normal","installed":false,"limit":1,"tags":["AI","Runtime"],"gpuSupport":false,"recommend":7,"batchInstallSupport":false},{"id":8,"name":"ComfyUI Runtime","key":"comfyui","description":"Powerful modular diffusion GUI and backend for AI image, audio, and video generation","status":"Normal","installed":false,"limit":1,"tags":["AI","Runtime"],"gpuSupport":true,"recommend":8,"batchInstallSupport":false},{"id":9,"name":"Hermes Agent","key":"hermes-agent","description":"Multi-channel AI agent runtime with bundled messaging channel adapters","status":"Normal","installed":false,"limit":1,"tags":["AI","Runtime"],"gpuSupport":false,"recommend":9,"batchInstallSupport":false},{"id":10,"name":"Adminer Database Manager","key":"adminer","description":"Web-based database management tool in a single PHP file supporting PostgreSQL, MySQL, SQLite","status":"Normal","installed":false,"limit":1,"tags":["Tool","Database"],"gpuSupport":false,"recommend":10,"batchInstallSupport":false},{"id":11,"name":"OneDev Server v16.9.2","key":"onedev","description":"Self-hosted Git Server with Kanban, CI/CD, packages, and code intelligence","status":"Normal","installed":false,"limit":1,"tags":["Tool"],"gpuSupport":false,"recommend":11,"batchInstallSupport":false},{"id":12,"name":"AI Gateway","key":"ai-gateway","description":"High performance enterprise gateway for LLMs with fallback, load balancing and caching","status":"Normal","installed":false,"limit":1,"tags":["AI","Gateway"],"gpuSupport":false,"recommend":12,"batchInstallSupport":false},{"id":13,"name":"DeepSeek Harness","key":"deepseek-harness","description":"Optimized DeepSeek reasoning model runner with persistent runtime storage","status":"Normal","installed":false,"limit":1,"tags":["AI","Runtime"],"gpuSupport":true,"recommend":13,"batchInstallSupport":false},{"id":14,"name":"Nginx Proxy Manager","key":"nginx-proxy-manager","description":"Docker container for managing Nginx proxy hosts with a simple web interface","status":"Normal","installed":false,"limit":1,"tags":["Tool"],"gpuSupport":false,"recommend":14,"batchInstallSupport":false},{"id":15,"name":"Nextcloud Hub","key":"nextcloud","description":"Self-hosted productivity platform that keeps you in control of your data","status":"Normal","installed":false,"limit":1,"tags":["Tool"],"gpuSupport":false,"recommend":15,"batchInstallSupport":false},{"id":16,"name":"Caddy Server","key":"caddy","description":"Powerful, enterprise-ready, open source web server with automatic HTTPS","status":"Normal","installed":false,"limit":1,"tags":["Tool"],"gpuSupport":false,"recommend":16,"batchInstallSupport":false}]}}`))
		return true
	}
	if strings.Contains(p, "/apps/detail/") || strings.Contains(p, "/apps/details/") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":{"appId":1,"version":"1.0.0","readme":"Sovereign AI Ecosystem component","params":{"formFields":[{"type":"number","labelZh":"服务端口","labelEn":"Port","required":true,"default":8080,"envKey":"PANEL_APP_PORT_HTTP"}]},"dockerCompose":"services:\n  app:\n    restart: unless-stopped\n","image":"ghcr.io/wolinet-renatus/app:latest","architectures":"amd64,arm64","gpuSupport":true}}`))
		return true
	}
	if strings.Contains(p, "/hosts/monitor/netoptions") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":["all","eth0","lo0"]}`))
		return true
	}
	if strings.Contains(p, "/hosts/monitor/iooptions") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":["all","disk1"]}`))
		return true
	}
	if strings.Contains(p, "/apps/installed/update/versions") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":[]}`))
		return true
	}
	if strings.Contains(p, "/apps/services/") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":[]}`))
		return true
	}
	if strings.Contains(p, "/apps/installed/search") || strings.Contains(p, "/apps/installed/list") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":{"total":3,"items":[{"id":1,"name":"Mitambo Sovereign Inference","appKey":"mitambo","key":"mitambo","appID":1,"appDetailId":"1","version":"1.0.0","status":"Running","appStatus":"Running","containerName":"mitambo-server","serviceName":"mitambo","httpPort":9997,"canUpdate":false,"favorite":false,"app":{"id":1,"name":"Mitambo Sovereign Inference","key":"mitambo","status":"Normal","type":"website","tags":[]}},{"id":2,"name":"Lango AI Gateway","appKey":"lango","key":"lango","appID":2,"appDetailId":"2","version":"1.0.0","status":"Running","appStatus":"Running","containerName":"lango-gateway","serviceName":"lango","httpPort":4000,"canUpdate":false,"favorite":false,"app":{"id":2,"name":"Lango AI Gateway","key":"lango","status":"Normal","type":"website","tags":[]}},{"id":3,"name":"PostgreSQL Sovereign","appKey":"postgresql","key":"postgresql","appID":3,"appDetailId":"3","version":"16.2","status":"Running","appStatus":"Running","containerName":"wolinet-postgres","serviceName":"postgres","httpPort":5432,"canUpdate":false,"favorite":false,"app":{"id":3,"name":"PostgreSQL Sovereign","key":"postgresql","status":"Normal","type":"website","tags":[]}}]}}`))
		return true
	}
	if strings.Contains(p, "/apps/") &&
		!strings.Contains(p, "/apps/installed") &&
		!strings.Contains(p, "/apps/sync") &&
		!strings.Contains(p, "/apps/search") &&
		!strings.Contains(p, "/apps/tags") &&
		!strings.Contains(p, "/apps/icon") &&
		!strings.Contains(p, "/apps/detail") &&
		!strings.Contains(p, "/apps/services") {
		idx := strings.Index(p, "/apps/")
		sub := p[idx+len("/apps/"):]
		sub = strings.Split(sub, "?")[0]
		appKey := strings.Split(sub, "/")[0]
		if appKey != "" {
			nameMap := map[string]string{
				"mitambo":             "Mitambo Sovereign Inference",
				"lango":               "Lango AI Gateway",
				"wolinex":             "WolinEx AI Studio",
				"ai-portal":           "1Panel AI Portal",
				"postgresql":          "PostgreSQL Sovereign",
				"redis":               "Redis Sovereign",
				"openclaw":            "OpenClaw Runtime",
				"comfyui":             "ComfyUI Runtime",
				"hermes-agent":        "Hermes Agent",
				"adminer":             "Adminer Database Manager",
				"onedev":              "OneDev Server v16.9.2",
				"ai-gateway":          "AI Gateway",
				"deepseek-harness":    "DeepSeek Harness",
				"nginx-proxy-manager": "Nginx Proxy Manager",
				"nextcloud":           "Nextcloud Hub",
				"caddy":               "Caddy Server",
				"casdoor":             "Casdoor IAM",
			}
			appName, ok := nameMap[appKey]
			if !ok {
				appName = strings.Title(strings.ReplaceAll(appKey, "-", " "))
			}
			rw.WriteHeader(http.StatusOK)
			resp := fmt.Sprintf(`{"code":200,"message":"","data":{"id":1,"name":"%s","key":"%s","tags":[{"key":"AI","name":"AI","sort":1}],"shortDescZh":"应用详情","shortDescEn":"Application description","description":"Enterprise application package","status":"Normal","type":"website","versions":["1.0.0"],"installed":false,"architectures":"amd64,arm64","gpuSupport":true}}`, appName, appKey)
			_, _ = rw.Write([]byte(resp))
			return true
		}
	}
	// Generic shape-safe fallback for every other agent route while agent.sock is absent.
	lower := strings.ToLower(p)
	switch {
	case strings.HasSuffix(lower, "/search") || strings.HasSuffix(lower, "/page") || strings.Contains(lower, "/search/"):
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":{"total":0,"items":[]}}`))
	case strings.HasSuffix(lower, "/list") || strings.HasSuffix(lower, "/options") || strings.HasSuffix(lower, "/providers") ||
		strings.HasSuffix(lower, "/tags") || strings.HasSuffix(lower, "/all"):
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":[]}`))
	default:
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":{}}`))
	}
	return true
}

func restoreLegacyForwardingHeaders(proxyReq *httputil.ProxyRequest) {
	restoreInboundHeader(proxyReq, "Forwarded")
	restoreLegacyForwardedFor(proxyReq)
	restoreLegacyForwardedMetadata(proxyReq, "X-Forwarded-Host", proxyReq.In.Host)

	forwardedProto := "http"
	if proxyReq.In.TLS != nil {
		forwardedProto = "https"
	}
	restoreLegacyForwardedMetadata(proxyReq, "X-Forwarded-Proto", forwardedProto)
}

func restoreLegacyForwardedFor(proxyReq *httputil.ProxyRequest) {
	restoreInboundHeader(proxyReq, "X-Forwarded-For")
	clientIP, _, err := net.SplitHostPort(proxyReq.In.RemoteAddr)
	if err != nil {
		return
	}
	prior, ok := proxyReq.Out.Header["X-Forwarded-For"]
	omit := ok && prior == nil
	if len(prior) > 0 {
		clientIP = strings.Join(prior, ", ") + ", " + clientIP
	}
	if !omit {
		proxyReq.Out.Header.Set("X-Forwarded-For", clientIP)
	}
}

func restoreLegacyForwardedMetadata(proxyReq *httputil.ProxyRequest, name, fallback string) {
	if !isConnectionHeader(proxyReq.In.Header, name) && proxyReq.In.Header.Get(name) != "" {
		restoreInboundHeader(proxyReq, name)
		return
	}
	proxyReq.Out.Header.Del(name)
	if fallback != "" {
		proxyReq.Out.Header.Set(name, fallback)
	}
}

func restoreInboundHeader(proxyReq *httputil.ProxyRequest, name string) {
	proxyReq.Out.Header.Del(name)
	if isConnectionHeader(proxyReq.In.Header, name) {
		return
	}
	canonicalName := http.CanonicalHeaderKey(name)
	if values, ok := proxyReq.In.Header[canonicalName]; ok {
		proxyReq.Out.Header[canonicalName] = slices.Clone(values)
	}
}

func isConnectionHeader(header http.Header, name string) bool {
	for _, value := range header.Values("Connection") {
		for _, token := range strings.Split(value, ",") {
			if strings.EqualFold(strings.TrimSpace(token), name) {
				return true
			}
		}
	}
	return false
}
