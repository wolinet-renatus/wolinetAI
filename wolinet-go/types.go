package wolinet

// ChatMessage represents a single message in a chat conversation.
type ChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
	Name    string `json:"name,omitempty"`
}

// ChatCompletionRequest options for chat completion.
type ChatCompletionRequest struct {
	Model       string        `json:"model"`
	Messages    []ChatMessage `json:"messages"`
	Temperature *float64      `json:"temperature,omitempty"`
	MaxTokens   *int          `json:"max_tokens,omitempty"`
	Stream      bool          `json:"stream,omitempty"`
}

// ChatCompletionChoice individual choice from completion.
type ChatCompletionChoice struct {
	Index        int         `json:"index"`
	Message      ChatMessage `json:"message"`
	FinishReason *string     `json:"finish_reason"`
}

// ChatCompletionUsage token usage breakdown.
type ChatCompletionUsage struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

// ChatCompletionResponse response from unary chat completion.
type ChatCompletionResponse struct {
	ID      string                 `json:"id"`
	Object  string                 `json:"object"`
	Created int64                  `json:"created"`
	Model   string                 `json:"model"`
	Choices []ChatCompletionChoice `json:"choices"`
	Usage   *ChatCompletionUsage   `json:"usage,omitempty"`
	Timings map[string]interface{} `json:"timings,omitempty"`
}

// ChatCompletionStreamChoice choice in a streaming chunk.
type ChatCompletionStreamChoice struct {
	Index int `json:"index"`
	Delta struct {
		Role    string `json:"role,omitempty"`
		Content string `json:"content,omitempty"`
	} `json:"delta"`
	FinishReason *string `json:"finish_reason"`
}

// ChatCompletionStreamResponse streaming chunk response.
type ChatCompletionStreamResponse struct {
	ID      string                       `json:"id"`
	Object  string                       `json:"object"`
	Created int64                        `json:"created"`
	Model   string                       `json:"model"`
	Choices []ChatCompletionStreamChoice `json:"choices"`
}

// EmbeddingRequest request parameters for embedding generation.
type EmbeddingRequest struct {
	Model string   `json:"model"`
	Input []string `json:"input"`
}

// EmbeddingItem vector embedding item.
type EmbeddingItem struct {
	Index     int       `json:"index"`
	Object    string    `json:"object"`
	Embedding []float64 `json:"embedding"`
}

// EmbeddingResponse response from embeddings endpoint.
type EmbeddingResponse struct {
	Object string          `json:"object"`
	Data   []EmbeddingItem `json:"data"`
	Model  string          `json:"model"`
}

// RerankRequest parameters for cross-encoder reranking.
type RerankRequest struct {
	Model     string   `json:"model"`
	Query     string   `json:"query"`
	Documents []string `json:"documents"`
	TopN      *int     `json:"top_n,omitempty"`
}

// RerankResult single scored rerank document.
type RerankResult struct {
	Index          int     `json:"index"`
	RelevanceScore float64 `json:"relevance_score"`
	Document       string  `json:"document,omitempty"`
}

// RerankResponse response from rerank endpoint.
type RerankResponse struct {
	ID      string         `json:"id"`
	Results []RerankResult `json:"results"`
	Model   string         `json:"model"`
}

// TanzaniaPaymentRequest request for mobile money topup.
type TanzaniaPaymentRequest struct {
	Provider         string  `json:"provider"` // mpesa, tigopesa, airtel, halopesa
	PhoneNumber      string  `json:"phone_number"`
	AmountTZS        float64 `json:"amount_tzs"`
	AccountReference string  `json:"account_reference,omitempty"`
}

// TanzaniaPaymentResponse response for mobile money transaction.
type TanzaniaPaymentResponse struct {
	TransactionID string  `json:"transaction_id"`
	Status        string  `json:"status"`
	AmountTZS     float64 `json:"amount_tzs"`
	Message       string  `json:"message"`
	Provider      string  `json:"provider"`
}

// StatusResponse platform telemetry and node status.
type StatusResponse struct {
	Brand struct {
		Name      string `json:"name"`
		Gateway   string `json:"gateway"`
		Inference string `json:"inference"`
		Docs      string `json:"docs"`
		OpenAPI   string `json:"openapi"`
	} `json:"brand"`
	ActiveKey  string `json:"active_key"`
	DefaultKey string `json:"default_key"`
	Gateway    struct {
		Status     string  `json:"status"`
		DB         string  `json:"db"`
		TotalSpend float64 `json:"total_spend"`
	} `json:"gateway"`
	Inference struct {
		Status     string                   `json:"status"`
		ModelCount int                      `json:"model_count"`
		Models     []map[string]interface{} `json:"models"`
		Nodes      []map[string]interface{} `json:"nodes"`
	} `json:"inference"`
	Timestamp string `json:"timestamp"`
}
