package dto

type PodmanToggleReq struct {
	Name   string `json:"name" binding:"required"`
	Action string `json:"action" binding:"required"` // "start", "stop", "restart"
}

type PodmanPatchReq struct {
	Name  string `json:"name" binding:"required"`
	Image string `json:"image" binding:"required"`
}

type PodmanModelSyncReq struct {
	ModelID   string `json:"modelId" binding:"required"`
	ModelName string `json:"modelName" binding:"required"`
	Mode      string `json:"mode"`      // "chat", "embedding", "image_generation"
	Enabled   bool   `json:"enabled"`
	ApiBase   string `json:"apiBase"`
	ApiKey    string `json:"apiKey"`
}
