package v2

import (
	"github.com/gin-gonic/gin"
	"wolinet.ai/1apanel/core/app/api/v2/helper"
	"wolinet.ai/1apanel/core/app/dto"
	"wolinet.ai/1apanel/core/app/service"
)

// @Tags Cloudflare
// @Summary Upsert Cloudflare V4 DNS Edge Record
// @Router /core/cloudflare/dns [post]
func (b *BaseApi) UpsertCloudflareDNS(c *gin.Context) {
	var req dto.CloudflareDNSRecordReq
	if err := helper.CheckBindAndValidate(&req, c); err != nil {
		helper.BadRequest(c, err)
		return
	}

	recordID, err := service.CloudflareService.UpsertDNSRecord(
		c.Request.Context(),
		req.ApiToken,
		req.ZoneID,
		req.Domain,
		req.Type,
		req.TargetIP,
		req.Proxied,
	)
	if err != nil {
		helper.InternalServer(c, err)
		return
	}

	helper.SuccessWithData(c, gin.H{
		"recordId": recordID,
		"domain":   req.Domain,
		"targetIp": req.TargetIP,
		"proxied":  req.Proxied,
	})
}

// @Tags Cloudflare
// @Summary Dynamically map domain to internal service with OpenResty and Cloudflare Edge
// @Router /core/cloudflare/proxy [post]
func (b *BaseApi) DeployEdgeProxy(c *gin.Context) {
	var req dto.CloudflareEdgeProxyReq
	if err := helper.CheckBindAndValidate(&req, c); err != nil {
		helper.BadRequest(c, err)
		return
	}

	recordID, err := service.CloudflareService.DeployEdgeProxy(c.Request.Context(), req)
	if err != nil {
		helper.InternalServer(c, err)
		return
	}

	helper.SuccessWithData(c, gin.H{
		"status":         "ok",
		"domain":         req.Domain,
		"upstreamTarget": req.UpstreamTarget,
		"recordId":       recordID,
		"autoDns":        req.AutoDNS,
	})
}
