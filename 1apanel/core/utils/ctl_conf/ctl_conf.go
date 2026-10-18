package ctl_conf

import (
	"fmt"
	"os"
	"strings"
)

const defaultFile = "/usr/local/bin/1pctl"

func getFallback(key string) string {
	switch key {
	case "BASE_DIR":
		if dir := os.Getenv("PANEL_BASE_DIR"); dir != "" {
			return dir
		}
		return "./data"
	case "ORIGINAL_PORT":
		return "9999"
	case "ORIGINAL_VERSION":
		return "v2.0.0"
	case "ORIGINAL_USERNAME":
		return "admin"
	case "ORIGINAL_PASSWORD":
		return "wolinet"
	case "ORIGINAL_ENTRANCE":
		return ""
	case "LANGUAGE":
		return "en"
	default:
		return ""
	}
}

func Load(key string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	cfgFile := defaultFile
	if custom := os.Getenv("PANEL_CTL_FILE"); custom != "" {
		cfgFile = custom
	}
	info, err := LoadFromFile(cfgFile, key)
	if err == nil && len(info) > 0 && info != `""` {
		return info
	}
	if fallback := getFallback(key); fallback != "" {
		return fallback
	}
	return ""
}

func LoadWithoutPanic(key string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	cfgFile := defaultFile
	if custom := os.Getenv("PANEL_CTL_FILE"); custom != "" {
		cfgFile = custom
	}
	info, err := LoadFromFile(cfgFile, key)
	if err != nil {
		return getFallback(key)
	}
	return info
}

func LoadFromFile(filePath, key string) (string, error) {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return "", err
	}
	prefix := key + "="
	for _, line := range strings.Split(string(data), "\n") {
		if strings.HasPrefix(line, prefix) {
			return strings.TrimSpace(strings.TrimPrefix(line, prefix)), nil
		}
	}
	return "", fmt.Errorf("error `%s` find in %s", key, filePath)
}

func UpdateInFile(filePath, key, value string) error {
	return rewriteFile(filePath, func(line string) (string, bool) {
		if strings.HasPrefix(line, key+"=") {
			return key + "=" + value, true
		}
		return line, true
	})
}

func RemoveValueFromFile(filePath, key, value string) error {
	target := key + "=" + value
	return rewriteFile(filePath, func(line string) (string, bool) {
		return line, line != target
	})
}

func rewriteFile(filePath string, rewrite func(string) (string, bool)) error {
	info, err := os.Stat(filePath)
	if err != nil {
		return err
	}
	data, err := os.ReadFile(filePath)
	if err != nil {
		return err
	}
	content := rewriteLines(string(data), rewrite)
	return os.WriteFile(filePath, []byte(content), info.Mode().Perm())
}

func rewriteLines(data string, rewrite func(string) (string, bool)) string {
	hasTrailingNewline := strings.HasSuffix(data, "\n")
	lines := strings.Split(strings.TrimSuffix(data, "\n"), "\n")
	rewritten := make([]string, 0, len(lines))
	for _, line := range lines {
		newLine, keep := rewrite(line)
		if keep {
			rewritten = append(rewritten, newLine)
		}
	}
	content := strings.Join(rewritten, "\n")
	if hasTrailingNewline {
		content += "\n"
	}
	return content
}
