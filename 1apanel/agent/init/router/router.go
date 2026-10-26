package router

import (
	v2 "wolinet.ai/1apanel/agent/app/api/v2"
	"wolinet.ai/1apanel/agent/global"
	"wolinet.ai/1apanel/agent/i18n"
	"wolinet.ai/1apanel/agent/middleware"
	rou "wolinet.ai/1apanel/agent/router"
	"github.com/gin-gonic/gin"
)

var (
	Router *gin.Engine
)

func Routers() *gin.Engine {
	Router = gin.Default()
	Router.Use(i18n.UseI18n())

	PrivateGroup := Router.Group("/api/v2")
	if !global.IsMaster {
		PrivateGroup.Use(middleware.Certificate())
	}
	PrivateGroup.Use(middleware.OperationResolveMeta())
	for _, router := range rou.RouterGroupApp {
		router.InitRouter(PrivateGroup)
	}
	PrivateGroup.GET("/health/check", v2.ApiGroupApp.BaseApi.CheckHealth)

	return Router
}
