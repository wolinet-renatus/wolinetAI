package terminal

import (
	"encoding/base64"
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	"wolinet.ai/1apanel/core/global"
)

var Upgrader = websocket.Upgrader{
	ReadBufferSize:  4096,
	WriteBufferSize: 16384,
	CheckOrigin: func(r *http.Request) bool {
		return true
	},
}

func ServeNativeLocalTerminal(c *gin.Context) {
	defer c.Abort()
	// Probe request without websocket upgrade (e.g. checkStreamAuth)
	if !websocket.IsWebSocketUpgrade(c.Request) {
		c.JSON(http.StatusOK, gin.H{
			"code":    200,
			"message": "",
			"data":    nil,
		})
		return
	}

	wsConn, err := Upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		global.LOG.Errorf("Terminal WebSocket upgrade failed: %v", err)
		return
	}
	defer wsConn.Close()

	cols, err := strconv.Atoi(c.DefaultQuery("cols", "120"))
	if err != nil || cols <= 0 {
		cols = 120
	}
	rows, err := strconv.Atoi(c.DefaultQuery("rows", "32"))
	if err != nil || rows <= 0 {
		rows = 32
	}

	cmdStr := c.DefaultQuery("command", "")
	slave, err := NewCommand(cmdStr)
	if err != nil {
		global.LOG.Errorf("Failed to start terminal process: %v", err)
		errMsg, _ := json.Marshal(WsMsg{
			Type: WsMsgCmd,
			Data: base64.StdEncoding.EncodeToString([]byte("Failed to spawn shell: " + err.Error() + "\r\n")),
		})
		_ = wsConn.WriteMessage(websocket.TextMessage, errMsg)
		return
	}
	defer slave.Close()

	session, err := NewLocalWsSession(cols, rows, wsConn, slave, true)
	if err != nil {
		global.LOG.Errorf("Failed to create terminal session: %v", err)
		return
	}

	quitChan := make(chan bool, 3)
	session.Start(quitChan)
	go slave.Wait(quitChan)

	<-quitChan
	dt := time.Now().Add(time.Second)
	_ = wsConn.WriteControl(websocket.CloseMessage, nil, dt)
}
