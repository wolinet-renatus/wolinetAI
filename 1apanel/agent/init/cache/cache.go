package cache

import (
	"wolinet.ai/1apanel/agent/global"
	cachedb "wolinet.ai/1apanel/agent/init/cache/db"
)

func Init() {
	global.CACHE = cachedb.NewCacheDB()
}
