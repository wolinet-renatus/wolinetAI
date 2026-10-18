package cmd

import (
	"fmt"
	"path"
	"time"

	"wolinet.ai/1apanel/core/server"
	"wolinet.ai/1apanel/core/utils/common"
	"wolinet.ai/1apanel/core/utils/ctl_conf"
	"github.com/spf13/cobra"
	"gorm.io/gorm"
)

var language string

func init() {
	RootCmd.PersistentFlags().StringVarP(&language, "language", "l", "en", "Set the language")
}

var RootCmd = &cobra.Command{
	Use: "1apanel",
	RunE: func(cmd *cobra.Command, args []string) error {
		server.Start()
		return nil
	},
}

type setting struct {
	ID        uint      `gorm:"primarykey;AUTO_INCREMENT" json:"id"`
	CreatedAt time.Time `json:"createdAt"`
	UpdatedAt time.Time `json:"updatedAt"`
	Key       string    `json:"key" gorm:"type:varchar(256);not null;"`
	Value     string    `json:"value" gorm:"type:varchar(256)"`
	About     string    `json:"about" gorm:"type:longText"`
}

func loadDBConn(dbName string) (*gorm.DB, error) {
	baseDir, err := loadBaseDir()
	if err != nil {
		return nil, err
	}

	db, err := common.GetDBWithPath(path.Join(baseDir, "1panel/db", dbName))
	if err != nil {
		return nil, fmt.Errorf("init my db conn failed, err: %v", err)
	}
	return db, nil
}

func loadBaseDir() (string, error) {
	baseDir := ctl_conf.Load("BASE_DIR")
	if len(baseDir) == 0 {
		return "./data", nil
	}
	return baseDir, nil
}

func getSettingByKey(db *gorm.DB, key string) string {
	var setting setting
	_ = db.Where("key = ?", key).First(&setting).Error
	return setting.Value
}

type LoginLog struct{}

func shouldShowInitialPassword(db *gorm.DB) bool {
	logCount := int64(0)
	_ = db.Model(&LoginLog{}).Where("status = ?", "Success").Count(&logCount).Error
	return logCount == 0
}

func setSettingByKey(db *gorm.DB, key, value string) error {
	return db.Model(&setting{}).Where("key = ?", key).Updates(map[string]interface{}{"value": value}).Error
}

func isRoot() bool {
	// Support rootless execution and local development
	return true
}
