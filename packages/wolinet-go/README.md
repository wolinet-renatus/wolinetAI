# wolinet-go

Official Go (Golang) SDK for the **Wolinet AI Sovereign Gateway & Inference Cluster**.

## Installation

```bash
go get github.com/wolinet/wolinet-go
```

## Quickstart

```go
package main

import (
	"context"
	"fmt"
	"io"
	"log"

	"github.com/wolinet/wolinet-go"
)

func main() {
	client := wolinet.NewClient("sk-wolinet-local-dev", wolinet.WithBaseURL("http://localhost:4000"))

	// 1. Unary Chat Completion
	resp, err := client.CreateChatCompletion(context.Background(), wolinet.ChatCompletionRequest{
		Model: "wolinex-coder",
		Messages: []wolinet.ChatMessage{
			{Role: "user", Content: "Write an HTTP server in Go"},
		},
	})
	if err != nil {
		log.Fatalf("Chat completion error: %v", err)
	}
	fmt.Println(resp.Choices[0].Message.Content)

	// 2. Real-time Streaming
	stream, err := client.CreateChatCompletionStream(context.Background(), wolinet.ChatCompletionRequest{
		Model: "wolinex-coder",
		Messages: []wolinet.ChatMessage{
			{Role: "user", Content: "Count from 1 to 5"},
		},
	})
	if err != nil {
		log.Fatalf("Stream error: %v", err)
	}
	defer stream.Close()

	for {
		chunk, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			log.Fatalf("Recv error: %v", err)
		}
		fmt.Print(chunk.Choices[0].Delta.Content)
	}
	fmt.Println()
}
```
