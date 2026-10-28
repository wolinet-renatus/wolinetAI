package service

import (
	"context"
	"fmt"
	"strings"
	"time"

	"wolinet.ai/1apanel/agent/app/dto"
	"wolinet.ai/1apanel/agent/app/model"
	"wolinet.ai/1apanel/agent/app/repo"
	terminalai "wolinet.ai/1apanel/agent/utils/terminal/ai"
)

const (
	defaultChatSystemPrompt = "You are Wolinet AI Operations Copilot, an expert sovereign DevOps and systems automation assistant running inside the 1Panel control plane. Infrastructure topology: Lango AI Gateway is on http://127.0.0.1:4000 (Bearer sk-XvKFiwDoOtOe8i4lwbzb8Q), OrcaCyber AI Defense Core is on http://127.0.0.1:8088, Mitambo local inference cluster is on http://127.0.0.1:9997, 1Panel is on http://127.0.0.1:9999, and Obscura browser sandbox bridge is on http://127.0.0.1:8080. You help administrators monitor servers, analyze Docker containers, automate Obscura browser workflows, and run diagnostic commands. Always provide actionable, clean, production-grade responses with exact commands and configurations."
	defaultChatMaxTokens    = 4096
	defaultFallbackModel    = "wolinet-coder"
	defaultFallbackBaseURL  = "http://127.0.0.1:4000/v1"
	defaultFallbackAPIKey   = "sk-XvKFiwDoOtOe8i4lwbzb8Q"
)

func (a AgentService) GetChatOptions() (*dto.AgentChatOptionsResp, error) {
	agents, err := agentRepo.List()
	if err != nil {
		return nil, err
	}
	agentItems := make([]dto.AgentItem, 0, len(agents))
	for _, ag := range agents {
		agentItems = append(agentItems, dto.AgentItem{
			ID:        ag.ID,
			Name:      ag.Name,
			Remark:    ag.Remark,
			AgentType: ag.AgentType,
			Model:     ag.Model,
			Status:    ag.Status,
			Provider:  ag.Provider,
		})
	}

	modelRows, err := agentAccountModelRepo.List()
	if err != nil {
		modelRows = []model.AgentAccountModel{}
	}
	models := make([]dto.AgentAccountModel, 0, len(modelRows))
	for _, m := range modelRows {
		name := m.Name
		if name == "" {
			name = m.Model
		}
		models = append(models, dto.AgentAccountModel{
			RecordID: m.ID,
			ID:       m.Model,
			Name:     name,
		})
	}

	if len(models) == 0 {
		models = []dto.AgentAccountModel{
			{ID: "wolinet-max", Name: "Wolinet Max (Reasoning & Architecture)"},
			{ID: "wolinet-pro", Name: "Wolinet Pro (Sovereign Local Hardware Engine)"},
			{ID: "wolinex-coder", Name: "Wolinex Coder (High-Speed Code & DevOps)"},
			{ID: "wolinet-coder", Name: "Wolinet Coder (Sovereign Systems & DevOps)"},
			{ID: "wolinet-turbo", Name: "Wolinet Turbo (Sub-Second Ultra Fast Ops)"},
			{ID: "wolinet-max-pro", Name: "Wolinet Max Pro (Moonshot Kimi K3.1 1M Context)"},
			{ID: "scorpio-pro", Name: "Scorpio Pro (DeepSeek Sovereign Deep Reasoner)"},
			{ID: "scorpio", Name: "Scorpio (DeepSeek Sovereign Fast Reasoner)"},
			{ID: "secure-pro", Name: "Secure Pro (AI Cyber Defense & Security Guard)"},
			{ID: "wolinet-turbo-draft", Name: "Wolinet Turbo Draft (Speculative Defense Engine)"},
		}
	}

	defaultModel := defaultFallbackModel
	if len(agentItems) > 0 && agentItems[0].Model != "" {
		defaultModel = agentItems[0].Model
	} else if len(models) > 0 {
		defaultModel = models[0].ID
	}

	return &dto.AgentChatOptionsResp{
		Agents:       agentItems,
		Models:       models,
		DefaultModel: defaultModel,
	}, nil
}

func (a AgentService) ChatWithAgent(req dto.AgentChatReq) (*dto.AgentChatResp, error) {
	startTime := time.Now()

	provider := "wolinet"
	baseURL := defaultFallbackBaseURL
	apiKey := defaultFallbackAPIKey
	apiType := "openai-completions"
	modelName := strings.TrimSpace(req.Model)
	agentName := "Wolinet AI Copilot"

	if req.AgentID > 0 {
		if ag, err := agentRepo.GetFirst(repo.WithByID(req.AgentID)); err == nil && ag != nil {
			agentName = ag.Name
			if modelName == "" {
				modelName = ag.Model
			}
			if ag.BaseURL != "" {
				baseURL = ag.BaseURL
			}
			if ag.APIKey != "" {
				apiKey = ag.APIKey
			}
			if ag.Provider != "" {
				provider = ag.Provider
			}
			if ag.APIType != "" {
				apiType = ag.APIType
			}
			if ag.AccountID > 0 && (apiKey == "" || baseURL == "") {
				if acc, err := agentAccountRepo.GetFirst(repo.WithByID(ag.AccountID)); err == nil && acc != nil {
					if baseURL == "" && acc.BaseURL != "" {
						baseURL = acc.BaseURL
					}
					if apiKey == "" && acc.APIKey != "" {
						apiKey = acc.APIKey
					}
					if acc.Provider != "" {
						provider = acc.Provider
					}
					if acc.APIType != "" {
						apiType = acc.APIType
					}
				}
			}
		}
	} else if req.AccountID > 0 {
		if acc, err := agentAccountRepo.GetFirst(repo.WithByID(req.AccountID)); err == nil && acc != nil {
			agentName = acc.Name
			if acc.BaseURL != "" {
				baseURL = acc.BaseURL
			}
			if acc.APIKey != "" {
				apiKey = acc.APIKey
			}
			if acc.Provider != "" {
				provider = acc.Provider
			}
			if acc.APIType != "" {
				apiType = acc.APIType
			}
		}
	} else {
		// Fallback: look for accounts
		if accounts, err := agentAccountRepo.List(); err == nil && len(accounts) > 0 {
			acc := accounts[0]
			agentName = acc.Name
			if acc.BaseURL != "" {
				baseURL = acc.BaseURL
			}
			if acc.APIKey != "" {
				apiKey = acc.APIKey
			}
			if acc.Provider != "" {
				provider = acc.Provider
			}
			if acc.APIType != "" {
				apiType = acc.APIType
			}
		}
	}

	if modelName == "" {
		modelName = defaultFallbackModel
	}

	maxTokens := req.MaxTokens
	if maxTokens <= 0 {
		maxTokens = defaultChatMaxTokens
	}

	hasSystem := false
	messages := make([]terminalai.ChatMessage, 0, len(req.Messages)+1)
	for _, m := range req.Messages {
		if strings.EqualFold(m.Role, "system") {
			hasSystem = true
		}
		messages = append(messages, terminalai.ChatMessage{
			Role:    m.Role,
			Content: m.Content,
		})
	}

	if !hasSystem {
		messages = append([]terminalai.ChatMessage{
			{
				Role:    "system",
				Content: defaultChatSystemPrompt,
			},
		}, messages...)
	}

	clientCfg := terminalai.ClientConfig{
		Provider:  provider,
		BaseURL:   baseURL,
		APIKey:    apiKey,
		Model:     modelName,
		APIType:   apiType,
		MaxTokens: maxTokens,
		Timeout:   120 * time.Second,
	}

	client, err := terminalai.NewClient(clientCfg)
	if err != nil {
		return nil, fmt.Errorf("initialize AI client: %w", err)
	}

	chatReq := terminalai.ChatCompletionRequest{
		Messages:    messages,
		MaxTokens:   maxTokens,
		Temperature: req.Temperature,
	}

	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()

	resp, err := client.ChatCompletion(ctx, chatReq)
	if err != nil {
		return nil, fmt.Errorf("AI completion failed: %w", err)
	}

	durationMs := time.Since(startTime).Milliseconds()

	return &dto.AgentChatResp{
		Model:       resp.Model,
		Content:     resp.Content,
		UsageTokens: resp.Usage.TotalTokens,
		DurationMs:  durationMs,
		AgentName:   agentName,
	}, nil
}
