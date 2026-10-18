package db

import (
	"path"

	"wolinet.ai/1apanel/core/global"
	"wolinet.ai/1apanel/core/utils/common"
)

func Init() {
	global.DB = common.LoadDBConnByPath(path.Join(global.CONF.Base.InstallDir, "1panel/db/core.db"), "core")
	global.TaskDB = common.LoadDBConnByPath(path.Join(global.CONF.Base.InstallDir, "1panel/db/task.db"), "task")
	global.AgentDB = common.LoadDBConnByPath(path.Join(global.CONF.Base.InstallDir, "1panel/db/agent.db"), "agent")
	global.AlertDB = common.LoadDBConnByPath(path.Join(global.CONF.Base.InstallDir, "1panel/db/alert.db"), "alert")
}
