package router

import (
	v2 "wolinet.ai/1apanel/agent/app/api/v2"
	"github.com/gin-gonic/gin"
)

type ProcessRouter struct {
}

func (f *ProcessRouter) InitRouter(Router *gin.RouterGroup) {
	processRouter := Router.Group("process")
	baseApi := v2.ApiGroupApp.BaseApi
	{
		processRouter.GET("/ws", baseApi.ProcessWs)
		processRouter.POST("/stop", baseApi.StopProcess)
		processRouter.POST("/listening", baseApi.GetListeningProcess)
		processRouter.GET("/:pid", baseApi.GetProcessInfoByPID)
	}
}
