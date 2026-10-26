package router

import (
	"github.com/gin-gonic/gin"
	v2 "wolinet.ai/1apanel/core/app/api/v2"
	"wolinet.ai/1apanel/core/middleware"
)

type CloudflareRouter struct{}

func (c *CloudflareRouter) InitRouter(Router *gin.RouterGroup) {
	cfRouter := Router.Group("core/cloudflare").Use(middleware.SessionAuth())
	baseApi := v2.ApiGroupApp.BaseApi
	{
		cfRouter.POST("/dns", baseApi.UpsertCloudflareDNS)
		cfRouter.POST("/proxy", baseApi.DeployEdgeProxy)
	}
}
