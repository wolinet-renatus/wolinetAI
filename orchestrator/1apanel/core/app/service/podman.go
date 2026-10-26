package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"strings"
	"time"

	"wolinet.ai/1apanel/core/global"
)

type PodmanEngine struct{}

var PodmanService = &PodmanEngine{}

type PodmanContainerInfo struct {
	ID      string            `json:"Id"`
	Names   []string          `json:"Names"`
	Image   string            `json:"Image"`
	State   string            `json:"State"`
	Status  string            `json:"Status"`
	Created int64             `json:"Created"`
	Ports   []PodmanPortMap   `json:"Ports"`
	Pod     string            `json:"Pod,omitempty"`
	Labels  map[string]string `json:"Labels,omitempty"`
}

type PodmanPortMap struct {
	HostIP        string `json:"host_ip"`
	ContainerPort int    `json:"container_port"`
	HostPort      int    `json:"host_port"`
	Range         int    `json:"range"`
	Protocol      string `json:"protocol"`
}

// ToggleAppService controls the On/Off panel switches for individual containers
func (p *PodmanEngine) ToggleAppService(ctx context.Context, containerName string, action string) error {
	// action can be: "start" (ON), "stop" (OFF), or "restart"
	global.LOG.Infof("[PodmanEngine] ToggleAppService container=%s action=%s", containerName, action)
	cmd := exec.CommandContext(ctx, "podman", action, containerName)
	return cmd.Run()
}

// HotPatchContainer handles the application update flow without dropping sister container instances
func (p *PodmanEngine) HotPatchContainer(ctx context.Context, imageTag string, containerName string) error {
	global.LOG.Infof("[PodmanEngine] HotPatchContainer imageTag=%s container=%s", imageTag, containerName)
	// 1. Pull down revised container image layers from secure local registry
	pullCmd := exec.CommandContext(ctx, "podman", "pull", imageTag)
	if err := pullCmd.Run(); err != nil {
		return err
	}

	// 2. Cycle only the targeted application container inside the active pod
	restartCmd := exec.CommandContext(ctx, "podman", "restart", containerName)
	return restartCmd.Run()
}

// ListContainers lists all containers managed by Podman
func (p *PodmanEngine) ListContainers(ctx context.Context) ([]PodmanContainerInfo, error) {
	cmd := exec.CommandContext(ctx, "podman", "ps", "-a", "--format", "json")
	out, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	var containers []PodmanContainerInfo
	if len(strings.TrimSpace(string(out))) == 0 {
		return containers, nil
	}
	if err := json.Unmarshal(out, &containers); err != nil {
		return nil, err
	}
	return containers, nil
}

// ListPods lists all active pods
func (p *PodmanEngine) ListPods(ctx context.Context) ([]map[string]interface{}, error) {
	cmd := exec.CommandContext(ctx, "podman", "pod", "ps", "--format", "json")
	out, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	var pods []map[string]interface{}
	if len(strings.TrimSpace(string(out))) == 0 {
		return pods, nil
	}
	if err := json.Unmarshal(out, &pods); err != nil {
		return nil, err
	}
	return pods, nil
}

// SyncModelProfile dynamically updates Lango LiteLLM proxy router model tables without restarting the parent pod
func (p *PodmanEngine) SyncModelProfile(ctx context.Context, modelID string, modelName string, mode string, enabled bool, apiBase string, apiKey string) error {
	gatewayURL := os.Getenv("LITELLM_BASE_URL")
	if gatewayURL == "" {
		gatewayURL = "http://127.0.0.1:4000"
	}
	masterKey := os.Getenv("LITELLM_MASTER_KEY")
	if masterKey == "" {
		masterKey = "sk-XvKFiwDoOtOe8i4lwbzb8Q"
	}
	if apiBase == "" {
		apiBase = "http://127.0.0.1:9997/v1"
	}
	if apiKey == "" {
		apiKey = "sk-XvKFiwDoOtOe8i4lwbzb8Q"
	}
	if mode == "" {
		mode = "chat"
	}

	client := &http.Client{Timeout: 10 * time.Second}

	if enabled {
		payload := map[string]interface{}{
			"model_name": modelName,
			"litellm_params": map[string]interface{}{
				"model":                             "xinference/" + modelID,
				"api_base":                          apiBase,
				"api_key":                           apiKey,
				"merge_reasoning_content_in_choices": true,
			},
			"model_info": map[string]interface{}{
				"id":   modelID,
				"mode": mode,
			},
		}
		data, err := json.Marshal(payload)
		if err != nil {
			return err
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodPost, gatewayURL+"/model/new", bytes.NewReader(data))
		if err != nil {
			return err
		}
		req.Header.Set("Authorization", "Bearer "+masterKey)
		req.Header.Set("Content-Type", "application/json")

		resp, err := client.Do(req)
		if err != nil {
			return err
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
			return fmt.Errorf("gateway /model/new returned status %d", resp.StatusCode)
		}
		global.LOG.Infof("[PodmanEngine] Successfully registered model %s (%s) in Lango Gateway", modelName, modelID)
	} else {
		payload := map[string]interface{}{
			"id": modelID,
		}
		data, err := json.Marshal(payload)
		if err != nil {
			return err
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodPost, gatewayURL+"/model/delete", bytes.NewReader(data))
		if err != nil {
			return err
		}
		req.Header.Set("Authorization", "Bearer "+masterKey)
		req.Header.Set("Content-Type", "application/json")

		resp, err := client.Do(req)
		if err != nil {
			return err
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNotFound {
			return fmt.Errorf("gateway /model/delete returned status %d", resp.StatusCode)
		}
		global.LOG.Infof("[PodmanEngine] Successfully deregistered model %s from Lango Gateway", modelID)
	}

	return nil
}
