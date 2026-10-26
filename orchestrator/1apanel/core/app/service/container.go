package service

import (
	"context"
	"os/exec"
)

// ToggleAppService controls the On/Off panel switches for individual containers
func (p *PodmanEngine) ToggleContainerService(ctx context.Context, containerName string, action string) error {
	cmd := exec.CommandContext(ctx, "podman", action, containerName)
	return cmd.Run()
}
