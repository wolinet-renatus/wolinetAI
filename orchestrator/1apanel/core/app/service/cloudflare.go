package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"wolinet.ai/1apanel/core/app/dto"
	"wolinet.ai/1apanel/core/global"
)

type CloudflareEdgeService struct{}

var CloudflareService = &CloudflareEdgeService{}

const cloudflareAPIBase = "https://api.cloudflare.com/client/v4"

type cfDNSListResponse struct {
	Success bool `json:"success"`
	Errors  []struct {
		Code    int    `json:"code"`
		Message string `json:"message"`
	} `json:"errors"`
	Result []struct {
		ID      string `json:"id"`
		Name    string `json:"name"`
		Type    string `json:"type"`
		Content string `json:"content"`
		Proxied bool   `json:"proxied"`
	} `json:"result"`
}

type cfDNSActionResponse struct {
	Success bool `json:"success"`
	Errors  []struct {
		Code    int    `json:"code"`
		Message string `json:"message"`
	} `json:"errors"`
	Result struct {
		ID      string `json:"id"`
		Name    string `json:"name"`
		Type    string `json:"type"`
		Content string `json:"content"`
		Proxied bool   `json:"proxied"`
	} `json:"result"`
}

type cfZonesResponse struct {
	Success bool `json:"success"`
	Errors  []struct {
		Code    int    `json:"code"`
		Message string `json:"message"`
	} `json:"errors"`
	Result []struct {
		ID   string `json:"id"`
		Name string `json:"name"`
	} `json:"result"`
}

// GetToken resolves Cloudflare API token dynamically from request or environment
func (s *CloudflareEdgeService) GetToken(overrideToken string) string {
	if overrideToken != "" {
		return overrideToken
	}
	return os.Getenv("CLOUDFLARE_API_TOKEN")
}

// FindZoneID resolves the Cloudflare Zone ID for a root domain
func (s *CloudflareEdgeService) FindZoneID(ctx context.Context, apiToken string, domain string) (string, error) {
	token := s.GetToken(apiToken)
	if token == "" {
		return "", fmt.Errorf("Cloudflare API token not configured")
	}

	parts := strings.Split(domain, ".")
	var zoneName string
	if len(parts) >= 2 {
		zoneName = strings.Join(parts[len(parts)-2:], ".")
	} else {
		zoneName = domain
	}

	url := fmt.Sprintf("%s/zones?name=%s", cloudflareAPIBase, zoneName)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}

	var res cfZonesResponse
	if err := json.Unmarshal(body, &res); err != nil {
		return "", err
	}
	if !res.Success || len(res.Result) == 0 {
		return "", fmt.Errorf("zone not found for domain %s (zone %s)", domain, zoneName)
	}

	return res.Result[0].ID, nil
}

// UpsertDNSRecord dynamically creates or updates an A/CNAME record on Cloudflare Edge DNS
func (s *CloudflareEdgeService) UpsertDNSRecord(ctx context.Context, apiToken string, zoneID string, domain string, recType string, content string, proxied bool) (string, error) {
	token := s.GetToken(apiToken)
	if token == "" {
		return "", fmt.Errorf("Cloudflare API token not configured")
	}
	if zoneID == "" {
		resolvedID, err := s.FindZoneID(ctx, token, domain)
		if err != nil {
			return "", err
		}
		zoneID = resolvedID
	}
	if recType == "" {
		recType = "A"
	}

	client := &http.Client{Timeout: 15 * time.Second}

	// 1. Check if record already exists
	checkURL := fmt.Sprintf("%s/zones/%s/dns_records?name=%s&type=%s", cloudflareAPIBase, zoneID, domain, recType)
	reqCheck, err := http.NewRequestWithContext(ctx, http.MethodGet, checkURL, nil)
	if err != nil {
		return "", err
	}
	reqCheck.Header.Set("Authorization", "Bearer "+token)
	reqCheck.Header.Set("Content-Type", "application/json")

	respCheck, err := client.Do(reqCheck)
	if err != nil {
		return "", err
	}
	defer respCheck.Body.Close()

	bodyCheck, err := io.ReadAll(respCheck.Body)
	if err != nil {
		return "", err
	}

	var listRes cfDNSListResponse
	if err := json.Unmarshal(bodyCheck, &listRes); err != nil {
		return "", err
	}

	payload := map[string]interface{}{
		"type":    recType,
		"name":    domain,
		"content": content,
		"ttl":     1, // Auto TTL when proxied
		"proxied": proxied,
	}
	data, err := json.Marshal(payload)
	if err != nil {
		return "", err
	}

	var actionReq *http.Request
	if listRes.Success && len(listRes.Result) > 0 {
		// Update existing record
		recordID := listRes.Result[0].ID
		updateURL := fmt.Sprintf("%s/zones/%s/dns_records/%s", cloudflareAPIBase, zoneID, recordID)
		actionReq, err = http.NewRequestWithContext(ctx, http.MethodPut, updateURL, bytes.NewReader(data))
		if err != nil {
			return "", err
		}
	} else {
		// Create new record
		createURL := fmt.Sprintf("%s/zones/%s/dns_records", cloudflareAPIBase, zoneID)
		actionReq, err = http.NewRequestWithContext(ctx, http.MethodPost, createURL, bytes.NewReader(data))
		if err != nil {
			return "", err
		}
	}

	actionReq.Header.Set("Authorization", "Bearer "+token)
	actionReq.Header.Set("Content-Type", "application/json")

	respAction, err := client.Do(actionReq)
	if err != nil {
		return "", err
	}
	defer respAction.Body.Close()

	bodyAction, err := io.ReadAll(respAction.Body)
	if err != nil {
		return "", err
	}

	var actionRes cfDNSActionResponse
	if err := json.Unmarshal(bodyAction, &actionRes); err != nil {
		return "", err
	}
	if !actionRes.Success {
		var errMsgs []string
		for _, e := range actionRes.Errors {
			errMsgs = append(errMsgs, fmt.Sprintf("[%d] %s", e.Code, e.Message))
		}
		return "", fmt.Errorf("Cloudflare DNS API error: %s", strings.Join(errMsgs, "; "))
	}

	global.LOG.Infof("[CloudflareEdgeService] Successfully upserted %s record for %s -> %s (proxied: %v)", recType, domain, content, proxied)
	return actionRes.Result.ID, nil
}

// GenerateOpenRestyProxyConfig builds a high-performance OpenResty reverse proxy configuration
func (s *CloudflareEdgeService) GenerateOpenRestyProxyConfig(domain string, upstreamTarget string) string {
	return fmt.Sprintf(`# Wolinet Sovereign Edge Proxy Configuration
# Domain: %s
# Upstream: %s

server {
    listen 80;
    listen [::]:80;
    server_name %s;

    # Cloudflare Real-IP Restoration
    set_real_ip_from 173.245.48.0/20;
    set_real_ip_from 103.21.244.0/22;
    set_real_ip_from 103.22.200.0/22;
    set_real_ip_from 103.31.4.0/22;
    set_real_ip_from 141.101.64.0/18;
    set_real_ip_from 108.162.192.0/18;
    set_real_ip_from 190.93.240.0/20;
    set_real_ip_from 188.114.96.0/20;
    set_real_ip_from 197.234.240.0/22;
    set_real_ip_from 198.41.128.0/17;
    set_real_ip_from 162.158.0.0/15;
    set_real_ip_from 104.16.0.0/13;
    set_real_ip_from 104.24.0.0/14;
    set_real_ip_from 172.64.0.0/13;
    set_real_ip_from 131.0.72.0/22;
    real_ip_header CF-Connecting-IP;

    client_max_body_size 500M;

    location / {
        proxy_pass %s;
        proxy_http_version 1.1;

        # WebSocket & Streaming Buffering Support
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE & Token Streaming Zero-Latency Pass-Through
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
`, domain, upstreamTarget, domain, upstreamTarget)
}

// DeployEdgeProxy writes the OpenResty config and optionally registers Cloudflare DNS
func (s *CloudflareEdgeService) DeployEdgeProxy(ctx context.Context, req dto.CloudflareEdgeProxyReq) (string, error) {
	// 1. Generate OpenResty Nginx configuration
	configContent := s.GenerateOpenRestyProxyConfig(req.Domain, req.UpstreamTarget)

	// Determine sites conf directory dynamically (relative or workspace anchor)
	baseDir := os.Getenv("WORKSPACE_ROOT")
	if baseDir == "" {
		baseDir = "."
	}
	confDir := filepath.Join(baseDir, "data", "openresty", "conf", "sites-enabled")
	_ = os.MkdirAll(confDir, 0755)

	confFile := filepath.Join(confDir, fmt.Sprintf("%s.conf", req.Domain))
	if err := os.WriteFile(confFile, []byte(configContent), 0644); err != nil {
		global.LOG.Warnf("[CloudflareEdgeService] Note: could not write local OpenResty conf: %v", err)
	}

	// 2. If AutoDNS is requested and target IP provided, upsert to Cloudflare Edge
	var dnsRecordID string
	if req.AutoDNS && req.TargetIP != "" {
		recID, err := s.UpsertDNSRecord(ctx, req.ApiToken, req.ZoneID, req.Domain, "A", req.TargetIP, req.Proxied)
		if err != nil {
			return "", fmt.Errorf("OpenResty config generated, but Cloudflare DNS update failed: %w", err)
		}
		dnsRecordID = recID
	}

	return dnsRecordID, nil
}
