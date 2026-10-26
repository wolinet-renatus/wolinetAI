package service

import (
	"context"

	"wolinet.ai/1apanel/agent/constant"
	"wolinet.ai/1apanel/agent/global"
	"gorm.io/gorm"
)

func getTxAndContext() (tx *gorm.DB, ctx context.Context) {
	tx = global.DB.Begin()
	ctx = context.WithValue(context.Background(), constant.DB, tx)
	return
}
