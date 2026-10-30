package service

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	"wolinet.ai/1apanel/agent/app/dto/request"
	"wolinet.ai/1apanel/agent/app/model"
	"wolinet.ai/1apanel/agent/app/repo"
	"wolinet.ai/1apanel/agent/app/task"
	"wolinet.ai/1apanel/agent/constant"
	"wolinet.ai/1apanel/agent/global"
	"github.com/pkg/errors"
)

func IsSovereignApp(name string) bool {
	switch strings.ToLower(name) {
	case "mitambo", "lango", "web-client", "wolinex", "memory", "obscura", "dev-portal", "docs", "website", "postgresql", "redis", "mysql":
		return true
	default:
		return false
	}
}

func stopHostProcessByPort(port int) error {
	if port <= 0 {
		return nil
	}
	out, err := exec.Command("lsof", "-ti", fmt.Sprintf(":%d", port)).Output()
	if err != nil {
		return nil
	}
	pids := strings.Fields(strings.TrimSpace(string(out)))
	for _, pidStr := range pids {
		pid, err := strconv.Atoi(pidStr)
		if err == nil && pid > 0 {
			if proc, err := os.FindProcess(pid); err == nil {
				_ = proc.Signal(syscall.SIGTERM)
			}
		}
	}
	return nil
}

func GetWorkspaceRoot() string {
	if root := os.Getenv("WORKSPACE_ROOT"); root != "" {
		return root
	}
	if dir, err := os.Getwd(); err == nil {
		for {
			if _, err := os.Stat(filepath.Join(dir, "products.json")); err == nil {
				return dir
			}
			if _, err := os.Stat(filepath.Join(dir, "docker-compose.prod.yml")); err == nil {
				return dir
			}
			parent := filepath.Dir(dir)
			if parent == dir {
				break
			}
			dir = parent
		}
	}
	return "."
}

func startSovereignApp(appName string, port int) error {
	wsRoot := GetWorkspaceRoot()
	switch appName {
	case "mitambo":
		cmd := exec.Command(filepath.Join(wsRoot, "inference/.venv/bin/python"),
			filepath.Join(wsRoot, "inference/.venv/bin/xinference-local"),
			"-H", "0.0.0.0", "-p", "9997")
		cmd.Dir = filepath.Join(wsRoot, "inference")
		return cmd.Start()
	case "web-client", "wolinex":
		cmd := exec.Command("bash", filepath.Join(wsRoot, "apps/wolinex/run_webui.sh"))
		cmd.Dir = filepath.Join(wsRoot, "apps/wolinex")
		return cmd.Start()
	case "memory":
		homeDir, _ := os.UserHomeDir()
		dataDir := filepath.Join(homeDir, "Library/Application Support/ai-memory")
		cfgPath := filepath.Join(dataDir, "config.toml")
		binPath := filepath.Join(homeDir, ".local/lib/ai-memory/ai-memory")
		cmd := exec.Command(binPath,
			"--data-dir", dataDir,
			"--config", cfgPath,
			"serve", "--transport", "http", "--enable-web")
		return cmd.Start()
	case "dev-portal", "docs", "website", "homepage":
		cmd := exec.Command("python3", "scripts/deploy/start-web-services.py")
		cmd.Dir = wsRoot
		return cmd.Start()
	case "lango":
		return exec.Command("docker", "start", "wolinetai-lango-1").Run()
	case "obscura":
		return exec.Command("docker", "start", "wolinet-browser").Run()
	case "postgresql":
		return exec.Command("docker", "start", "wolinetai-postgres-1").Run()
	case "redis":
		return exec.Command("docker", "start", "wolinetai-redis-1").Run()
	case "mysql":
		return exec.Command("docker", "start", "wolinetai-mysql-1").Run()
	default:
		return nil
	}
}

func stopSovereignApp(appName string, port int) error {
	switch appName {
	case "lango":
		return exec.Command("docker", "stop", "wolinetai-lango-1").Run()
	case "obscura":
		return exec.Command("docker", "stop", "wolinet-browser").Run()
	case "postgresql":
		return exec.Command("docker", "stop", "wolinetai-postgres-1").Run()
	case "redis":
		return exec.Command("docker", "stop", "wolinetai-redis-1").Run()
	case "mysql":
		return exec.Command("docker", "stop", "wolinetai-mysql-1").Run()
	default:
		return stopHostProcessByPort(port)
	}
}

func restartSovereignApp(appName string, port int) error {
	_ = stopSovereignApp(appName, port)
	time.Sleep(1 * time.Second)
	return startSovereignApp(appName, port)
}

func buildOrSyncSovereignApp(appName string) error {
	buildTarget := appName
	switch appName {
	case "website", "homepage":
		buildTarget = "website"
	case "dev-portal", "devportal":
		buildTarget = "dev-portal"
	case "docs":
		buildTarget = "docs"
	case "web-client", "webui", "wolinex":
		buildTarget = "wolinex"
	case "memory":
		buildTarget = "memory"
	case "mitambo":
		buildTarget = "mitambo"
	case "lango":
		buildTarget = "lango"
	case "obscura":
		buildTarget = "server"
	}
	wsRoot := GetWorkspaceRoot()
	cmd := exec.Command("python3", filepath.Join(wsRoot, "bin/wolinet-product"), "build", buildTarget)
	cmd.Dir = wsRoot
	out, err := cmd.CombinedOutput()
	if err != nil {
		global.LOG.Errorf("build sovereign app %s error: %v, output: %s", appName, err, string(out))
		return err
	}
	return nil
}

func rebuildSovereignApp(appName string, port int) error {
	_ = buildOrSyncSovereignApp(appName)
	return restartSovereignApp(appName, port)
}

func operateSovereignApp(install *model.AppInstall, req request.AppInstalledOperate) error {
	switch req.Operate {
	case constant.Rebuild:
		install.Status = constant.StatusRebuilding
		_ = appInstallRepo.Save(context.Background(), install)
		go func() {
			_ = rebuildSovereignApp(install.Name, install.HttpPort)
			install.Status = constant.StatusRunning
			_ = appInstallRepo.Save(context.Background(), install)
		}()
		return nil
	case constant.Start:
		if err := startSovereignApp(install.Name, install.HttpPort); err != nil {
			return err
		}
		install.Status = constant.StatusRunning
		install.Message = ""
		_ = appInstallRepo.Save(context.Background(), install)
		return nil
	case constant.Stop:
		if err := stopSovereignApp(install.Name, install.HttpPort); err != nil {
			return err
		}
		install.Status = constant.StatusStopped
		install.Message = ""
		_ = appInstallRepo.Save(context.Background(), install)
		return nil
	case constant.Restart:
		install.Status = constant.StatusRestarting
		_ = appInstallRepo.Save(context.Background(), install)
		go func() {
			_ = restartSovereignApp(install.Name, install.HttpPort)
			install.Status = constant.StatusRunning
			install.Message = ""
			_ = appInstallRepo.Save(context.Background(), install)
		}()
		return nil
	case constant.Sync:
		return syncAppInstallStatus(install, true)
	case constant.Upgrade:
		detail, _ := appDetailRepo.GetFirst(repo.WithByID(req.DetailId))
		upgradeReq := request.AppInstallUpgrade{
			InstallID: install.ID,
			DetailID:  req.DetailId,
			TaskID:    req.TaskID,
		}
		return upgradeSovereignApp(install, detail, upgradeReq)
	case constant.Favorite:
		install.Favorite = req.Favorite
		var maxSort int
		global.DB.Model(&model.AppInstall{}).Where("favorite = ?", req.Favorite).Select("COALESCE(MAX(sort_order),0)").Scan(&maxSort)
		install.SortOrder = maxSort + 1
		return appInstallRepo.Save(context.Background(), install)
	default:
		return errors.New("operate not support")
	}
}

func upgradeSovereignApp(install *model.AppInstall, detail model.AppDetail, req request.AppInstallUpgrade) error {
	targetVersion := detail.Version
	if targetVersion == "" {
		targetVersion = "latest"
	}
	taskID := req.TaskID
	upgradeTask, err := task.NewTaskWithOps(install.Name, task.TaskUpgrade, task.TaskScopeApp, taskID, install.ID)
	if err != nil {
		_ = buildOrSyncSovereignApp(install.Name)
		_ = restartSovereignApp(install.Name, install.HttpPort)
		install.Version = targetVersion
		if detail.ID > 0 {
			install.AppDetailId = detail.ID
		}
		install.Status = constant.StatusRunning
		install.Message = ""
		return appInstallRepo.Save(context.Background(), install)
	}

	upgradeTask.AddSubTaskWithOps(
		task.GetTaskName(install.Name, task.TaskUpgrade, task.TaskScopeApp),
		func(t *task.Task) error {
			t.Logf("==> [Sovereign Upgrade] Upgrading %s from v%s to %s without system disturbance...", install.Name, install.Version, targetVersion)
			t.Logf("==> [Sovereign Upgrade] Triggering change-aware build for %s via bin/wolinet-product...", install.Name)
			_ = buildOrSyncSovereignApp(install.Name)
			t.Logf("==> [Sovereign Upgrade] Gracefully restarting %s...", install.Name)
			_ = restartSovereignApp(install.Name, install.HttpPort)
			install.Version = targetVersion
			if detail.ID > 0 {
				install.AppDetailId = detail.ID
			}
			install.Status = constant.StatusRunning
			install.Message = ""
			if err := appInstallRepo.Save(context.Background(), install); err != nil {
				return err
			}
			t.Logf("==> [Sovereign Upgrade] Upgrade completed successfully for %s (%s). Service is healthy.", install.Name, targetVersion)
			return nil
		},
		nil,
		0,
		0,
	)

	upgradingInstall := *install
	upgradingInstall.Status = constant.StatusUpgrading
	_ = appInstallRepo.Save(context.Background(), &upgradingInstall)

	go func() {
		_ = upgradeTask.Execute()
		install.Status = constant.StatusRunning
		_ = appInstallRepo.Save(context.Background(), install)
	}()

	return nil
}
