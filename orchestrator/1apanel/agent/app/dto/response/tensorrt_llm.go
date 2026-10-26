package response

import (
	"wolinet.ai/1apanel/agent/app/dto/request"
	"wolinet.ai/1apanel/agent/app/model"
)

type TensorRTLLMsRes struct {
	Items []TensorRTLLMDTO `json:"items"`
	Total int64            `json:"total"`
}

type TensorRTLLMDTO struct {
	model.TensorRTLLM
	Version  string `json:"version"`
	Model    string `json:"model"`
	Dir      string `json:"dir"`
	ModelDir string `json:"modelDir"`
	Image    string `json:"image"`
	Command  string `json:"command"`

	ExposedPorts []request.ExposedPort `json:"exposedPorts"`
	Environments []request.Environment `json:"environments"`
	Volumes      []request.Volume      `json:"volumes"`
}
