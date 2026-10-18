package proxy

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"net/http/httputil"
	"slices"
	"strings"
	"time"

	"wolinet.ai/1apanel/core/utils/clientip"
	"wolinet.ai/1apanel/core/utils/publicshare"
)

const SockPath = "/etc/1panel/agent.sock"

var (
	LocalAgentProxy *httputil.ReverseProxy
)

func Init() {
	dialer := &net.Dialer{
		Timeout: 5 * time.Second,
	}
	dialUnix := func(ctx context.Context, network, addr string) (net.Conn, error) {
		return dialer.DialContext(ctx, "unix", SockPath)
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
		resp := fmt.Sprintf(`{"code":200,"message":"","data":{"dockerSockPath":"/var/run/docker.sock","systemVersion":"1.0.0","systemIP":"127.0.0.1","localTime":"%s","timeZone":"UTC","ntpSite":"time.cloudflare.com","defaultNetwork":"eth0","defaultIO":"disk1","lastCleanTime":"","lastCleanSize":"0 MB","lastCleanData":"","monitorStatus":"enable","monitorInterval":"10","monitorStoreDays":"30","appStoreVersion":"v1.0.0","appStoreLastModified":"","appStoreSyncStatus":"Success","fileRecycleBin":"enable","localSSHConnShow":"enable","firewallPortWhiteList":""}}`, now)
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(resp))
		return true
	}
	if strings.Contains(p, "/apps/tags") || strings.Contains(p, "/apps/installed/list") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":[]}`))
		return true
	}
	if strings.Contains(p, "/apps/search") || strings.Contains(p, "/apps/installed/search") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":{"total":0,"items":[]}}`))
		return true
	}
	if strings.Contains(p, "/toolbox/") || strings.Contains(p, "/hosts/") || strings.Contains(p, "/dashboard/") || strings.Contains(p, "/apps/") || strings.Contains(p, "/logs/") || strings.Contains(p, "/containers/") {
		rw.WriteHeader(http.StatusOK)
		_, _ = rw.Write([]byte(`{"code":200,"message":"","data":null}`))
		return true
	}
	return false
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
