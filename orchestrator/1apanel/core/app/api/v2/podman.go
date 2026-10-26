package v2

import (
	"errors"

	"github.com/gin-gonic/gin"
	"wolinet.ai/1apanel/core/app/api/v2/helper"
	"wolinet.ai/1apanel/core/app/dto"
	"wolinet.ai/1apanel/core/app/service"
)

// @Tags Podman
// @Summary Toggle container lifecycle state (start/stop/restart)
// @Router /core/podman/toggle [post]
func (b *BaseApi) ToggleContainer(c *gin.Context) {
	var req dto.PodmanToggleReq
	if err := helper.CheckBindAndValidate(&req, c); err != nil {
		helper.BadRequest(c, err)
		return
	}
	if req.Action != "start" && req.Action != "stop" && req.Action != "restart" {
		helper.BadRequest(c, errors.New("action must be start, stop, or restart"))
		return
	}

	if err := service.PodmanService.ToggleAppService(c.Request.Context(), req.Name, req.Action); err != nil {
		helper.InternalServer(c, err)
		return
	}
	helper.SuccessWithData(c, gin.H{"status": "ok", "name": req.Name, "action": req.Action})
}

// @Tags Podman
// @Summary Hot patch a container image without restarting the pod
// @Router /core/podman/patch [post]
func (b *BaseApi) HotPatchContainer(c *gin.Context) {
	var req dto.PodmanPatchReq
	if err := helper.CheckBindAndValidate(&req, c); err != nil {
		helper.BadRequest(c, err)
		return
	}

	if err := service.PodmanService.HotPatchContainer(c.Request.Context(), req.Image, req.Name); err != nil {
		helper.InternalServer(c, err)
		return
	}
	helper.SuccessWithData(c, gin.H{"status": "ok", "name": req.Name, "image": req.Image})
}

// @Tags Podman
// @Summary List all rootless Podman containers
// @Router /core/podman/containers [get]
func (b *BaseApi) ListPodmanContainers(c *gin.Context) {
	containers, err := service.PodmanService.ListContainers(c.Request.Context())
	if err != nil {
		helper.InternalServer(c, err)
		return
	}
	helper.SuccessWithData(c, containers)
}

// @Tags Podman
// @Summary List all rootless Podman pods
// @Router /core/podman/pods [get]
func (b *BaseApi) ListPodmanPods(c *gin.Context) {
	pods, err := service.PodmanService.ListPods(c.Request.Context())
	if err != nil {
		helper.InternalServer(c, err)
		return
	}
	helper.SuccessWithData(c, pods)
}

// @Tags Podman
// @Summary Dynamically synchronize AI model routing profile in Lango Gateway
// @Router /core/podman/models/sync [post]
func (b *BaseApi) SyncModelRoute(c *gin.Context) {
	var req dto.PodmanModelSyncReq
	if err := helper.CheckBindAndValidate(&req, c); err != nil {
		helper.BadRequest(c, err)
		return
	}

	if err := service.PodmanService.SyncModelProfile(c.Request.Context(), req.ModelID, req.ModelName, req.Mode, req.Enabled, req.ApiBase, req.ApiKey); err != nil {
		helper.InternalServer(c, err)
		return
	}
	helper.SuccessWithData(c, gin.H{"status": "ok", "modelId": req.ModelID, "enabled": req.Enabled})
}
