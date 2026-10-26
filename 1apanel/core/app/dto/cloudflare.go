package dto

type CloudflareDNSRecordReq struct {
	ZoneID   string `json:"zoneId"`
	Domain   string `json:"domain" binding:"required"`
	Type     string `json:"type"`     // "A", "AAAA", "CNAME"
	TargetIP string `json:"targetIp"` // Host public IPv4/IPv6 or CNAME target
	Proxied  bool   `json:"proxied"`  // Cloudflare CDN/WAF proxy flag
	ApiToken string `json:"apiToken"`
}

type CloudflareEdgeProxyReq struct {
	Domain         string `json:"domain" binding:"required"`
	UpstreamTarget string `json:"upstreamTarget" binding:"required"` // e.g. "http://127.0.0.1:8080"
	AutoDNS        bool   `json:"autoDns"`
	TargetIP       string `json:"targetIp"`
	ZoneID         string `json:"zoneId"`
	ApiToken       string `json:"apiToken"`
	Proxied        bool   `json:"proxied"`
}

type CloudflareEdgeResponse struct {
	Success bool        `json:"success"`
	Message string      `json:"message"`
	Data    interface{} `json:"data,omitempty"`
}
