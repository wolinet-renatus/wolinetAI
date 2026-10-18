package router

import (
	v2 "wolinet.ai/1apanel/core/app/api/v2"
	"wolinet.ai/1apanel/core/middleware"
	"github.com/gin-gonic/gin"
)

type RuntimeDiagnosticsRouter struct{}

func (s *RuntimeDiagnosticsRouter) InitRouter(Router *gin.RouterGroup) {
	diagnosticsRouter := Router.Group("hosts/diagnostics").
		Use(middleware.SessionAuth()).
		Use(middleware.PasswordExpired())
	baseApi := v2.ApiGroupApp.BaseApi
	{
		diagnosticsRouter.GET("/summary", baseApi.LoadRuntimeDiagnosticsSummary)
		diagnosticsRouter.GET("/goroutines", baseApi.LoadRuntimeGoroutines)
		diagnosticsRouter.POST("/profiles", baseApi.CreateRuntimeProfile)
	}
}
