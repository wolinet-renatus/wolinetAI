package router

import (
	"github.com/gin-gonic/gin"
	v2 "wolinet.ai/1apanel/core/app/api/v2"
	"wolinet.ai/1apanel/core/middleware"
)

type PodmanRouter struct{}

func (p *PodmanRouter) InitRouter(Router *gin.RouterGroup) {
	podmanRouter := Router.Group("core/podman").Use(middleware.SessionAuth())
	baseApi := v2.ApiGroupApp.BaseApi
	{
		podmanRouter.POST("/toggle", baseApi.ToggleContainer)
		podmanRouter.POST("/patch", baseApi.HotPatchContainer)
		podmanRouter.GET("/containers", baseApi.ListPodmanContainers)
		podmanRouter.GET("/pods", baseApi.ListPodmanPods)
		podmanRouter.POST("/models/sync", baseApi.SyncModelRoute)
	}
}
