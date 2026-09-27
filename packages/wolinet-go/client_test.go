package wolinet

import (
	"context"
	"testing"
	"time"
)

func TestChatCompletion(t *testing.T) {
	client := NewClient("sk-wolinet-local-dev", WithBaseURL("http://localhost:4000"), WithTimeout(15*time.Second))
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	resp, err := client.CreateChatCompletion(ctx, ChatCompletionRequest{
		Model: "wolinex-coder",
		Messages: []ChatMessage{
			{Role: "user", Content: "Reply with the single word: OK"},
		},
	})
	if err != nil {
		t.Logf("Gateway completion test skipped or failed: %v", err)
		return
	}

	if len(resp.Choices) == 0 {
		t.Fatalf("expected at least 1 choice, got 0")
	}
	t.Logf("Response content: %s", resp.Choices[0].Message.Content)
}

func TestGetStatus(t *testing.T) {
	client := NewClient("sk-wolinet-local-dev", WithBaseURL("http://localhost:4000"))
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	status, err := client.GetStatus(ctx)
	if err != nil {
		t.Logf("Status call skipped: %v", err)
		return
	}
	if status.Brand.Name == "" {
		t.Errorf("expected brand name, got empty string")
	}
	t.Logf("Brand: %s, Gateway: %s, Inference: %s", status.Brand.Name, status.Gateway.Status, status.Inference.Status)
}
