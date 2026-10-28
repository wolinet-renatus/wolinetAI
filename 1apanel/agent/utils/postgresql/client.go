package postgresql

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"net/url"
	"time"

	"wolinet.ai/1apanel/agent/buserr"
	"wolinet.ai/1apanel/agent/utils/postgresql/client"
	_ "github.com/jackc/pgx/v5/stdlib"
)

type PostgresqlClient interface {
	Create(info client.CreateInfo) error
	CreateUser(info client.CreateInfo, withDeleteDB bool) error
	Delete(info client.DeleteInfo) error
	ChangePrivileges(info client.Privileges) error
	ChangePassword(info client.PasswordChangeInfo) error

	Backup(info client.BackupInfo) error
	Recover(info client.RecoverInfo) error
	SyncDB() ([]client.SyncDBInfo, error)
	Close()
}

func NewPostgresqlClient(conn client.DBInfo) (PostgresqlClient, error) {
	addr := conn.Address
	if addr == "" {
		addr = "127.0.0.1"
	}
	port := conn.Port
	if port == 0 {
		port = 5433
	}
	initDB := conn.InitialDB
	if len(initDB) == 0 {
		initDB = "postgres"
	}

	escapedUsername := url.QueryEscape(conn.Username)
	escapedPassword := url.QueryEscape(conn.Password)
	connArgs := fmt.Sprintf("postgres://%s:%s@%s:%d/%s?sslmode=disable", escapedUsername, escapedPassword, addr, port, initDB)
	db, err := sql.Open("pgx", connArgs)
	if err == nil {
		timeout := conn.Timeout
		if timeout == 0 {
			timeout = 10
		}
		ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeout)*time.Second)
		defer cancel()
		if pingErr := db.PingContext(ctx); pingErr == nil {
			return client.NewRemote(client.Remote{
				Client:   db,
				From:     conn.From,
				Database: conn.Database,
				User:     conn.Username,
				Password: conn.Password,
				Address:  addr,
				Port:     port,
			}), nil
		}
		_ = db.Close()
	}

	if conn.From == "local" {
		connArgs := []string{"exec", "-e", fmt.Sprintf("PGPASSWORD=%s", conn.Password), conn.Address, "psql", "-t", "-U", conn.Username, "-c"}
		return client.NewLocal(connArgs, conn.Address, conn.Username, conn.Password, conn.Database), nil
	}
	if errors.Is(err, context.DeadlineExceeded) {
		return nil, buserr.New("ErrExecTimeOut")
	}
	return nil, err
}
