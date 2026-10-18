package session

import (
	"wolinet.ai/1apanel/core/global"
	"wolinet.ai/1apanel/core/init/session/psession"
)

func Init() {
	global.SESSION = psession.NewPSession("")
	global.LOG.Info("init in-memory session successfully")
}
