package terminal

import (
	"os"
	"os/exec"
	"syscall"
	"time"

	"github.com/creack/pty"
	"github.com/pkg/errors"
	"wolinet.ai/1apanel/core/global"
)

const (
	DefaultCloseSignal  = syscall.SIGINT
	DefaultCloseTimeout = 10 * time.Second
)

type LocalCommand struct {
	closeSignal  syscall.Signal
	closeTimeout time.Duration

	cmd *exec.Cmd
	pty *os.File
}

func NewCommand(script string) (*LocalCommand, error) {
	shell := os.Getenv("SHELL")
	if shell == "" {
		if path, err := exec.LookPath("zsh"); err == nil {
			shell = path
		} else if path, err := exec.LookPath("bash"); err == nil {
			shell = path
		} else {
			shell = "/bin/sh"
		}
	}
	cmd := exec.Command(shell)
	cmd.Env = os.Environ()
	if term := os.Getenv("TERM"); term != "" {
		cmd.Env = append(cmd.Env, "TERM="+term)
	} else {
		cmd.Env = append(cmd.Env, "TERM=xterm-256color")
	}
	if home, err := os.UserHomeDir(); err == nil && home != "" {
		cmd.Dir = home
	}
	if len(script) != 0 {
		cmd.Env = append(cmd.Env, "INIT_SCRIPT="+script)
	}

	ptyFile, err := pty.Start(cmd)
	if err != nil {
		return nil, errors.Wrapf(err, "failed to start command")
	}
	if len(script) != 0 {
		time.Sleep(100 * time.Millisecond)
		_, _ = ptyFile.Write([]byte(script + "\n"))
	}

	lcmd := &LocalCommand{
		closeSignal:  DefaultCloseSignal,
		closeTimeout: DefaultCloseTimeout,
		cmd:          cmd,
		pty:          ptyFile,
	}

	return lcmd, nil
}

func (lcmd *LocalCommand) Read(p []byte) (n int, err error) {
	if lcmd.pty == nil {
		return 0, os.ErrClosed
	}
	return lcmd.pty.Read(p)
}

func (lcmd *LocalCommand) Write(p []byte) (n int, err error) {
	if lcmd.pty == nil {
		return 0, os.ErrClosed
	}
	return lcmd.pty.Write(p)
}

func (lcmd *LocalCommand) Close() error {
	if lcmd.cmd != nil && lcmd.cmd.Process != nil {
		_ = lcmd.cmd.Process.Kill()
	}
	if lcmd.pty != nil {
		_ = lcmd.pty.Close()
	}
	return nil
}

func (lcmd *LocalCommand) ResizeTerminal(width int, height int) error {
	if lcmd.pty == nil {
		return nil
	}
	return pty.Setsize(lcmd.pty, &pty.Winsize{
		Rows: uint16(height),
		Cols: uint16(width),
	})
}

func (lcmd *LocalCommand) Wait(quitChan chan bool) {
	if err := lcmd.cmd.Wait(); err != nil {
		global.LOG.Errorf("ssh session wait failed, err: %v", err)
		setQuit(quitChan)
	}
	setQuit(quitChan)
}
