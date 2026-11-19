/**
 * Wolinet AI Developer Studio — Client Logic (dev.wolinet.com)
 */
(() => {
  'use strict';

  const keyNode = document.querySelector('#api-key');
  const keyState = document.querySelector('#key-state');
  const keyMessage = document.querySelector('#key-message');
  const accountLabel = document.querySelector('#account-label');
  const sessionDot = document.querySelector('#session-dot');
  const chatLog = document.querySelector('#chat-log');
  const chatForm = document.querySelector('#chat-form');
  const chatInput = document.querySelector('#chat-input');
  const chatSubmitBtn = document.querySelector('#chat-submit-btn');
  const snippetContent = document.querySelector('#code-snippet-content');

  let session = null;
  let keyVisible = false;
  let activeLang = 'python';
  const gatewayApiBase = ['localhost', '127.0.0.1', '0.0.0.0'].includes(window.location.hostname)
    ? `${window.location.origin}/v1`
    : 'https://lango.wolinet.com/v1';

  // Multi-Language Code Snippets
  const codeSnippets = {
    python: (key) => `from openai import OpenAI

# Initialize client pointing to Wolinet Lango AI Gateway
client = OpenAI(
    base_url="${gatewayApiBase}",
    api_key="${key}"
)

response = client.chat.completions.create(
    model="Wolinet Pro",
    messages=[
        {"role": "system", "content": "You are Wolinet AI, an enterprise sovereign assistant."},
        {"role": "user", "content": "Explain our sovereign infrastructure in one sentence."}
    ],
    temperature=0.2,
    stream=True
)

for chunk in response:
    print(chunk.choices[0].delta.content or "", end="")`,

    ts: (key) => `import OpenAI from "openai";

// Initialize client pointing to Wolinet Developer API
const openai = new OpenAI({
  baseURL: "${gatewayApiBase}",
  apiKey: "${key}",
});

async function main() {
  const stream = await openai.chat.completions.create({
    model: "Wolinet Coder v2",
    messages: [{ role: "user", content: "Implement a rate limiter in TypeScript" }],
    stream: true,
  });

  for await (const chunk of stream) {
    process.stdout.write(chunk.choices[0]?.delta?.content || "");
  }
}

main();`,

    curl: (key) => `curl -X POST "${gatewayApiBase}/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${key}" \\
  -d '{
    "model": "Wolinet Pro",
    "messages": [
      {"role": "user", "content": "Explain sovereign computing"}
    ],
    "temperature": 0.3,
    "stream": false
  }'`,

    go: (key) => `package main

import (
	"context"
	"fmt"
	"github.com/sashabaranov/go-openai"
)

func main() {
	config := openai.DefaultConfig("${key}")
	config.BaseURL = "${gatewayApiBase}"
	client := openai.NewClientWithConfig(config)

	resp, err := client.CreateChatCompletion(
		context.Background(),
		openai.ChatCompletionRequest{
			Model: "Wolinet Pro",
			Messages: []openai.ChatCompletionMessage{
				{Role: openai.ChatMessageRoleUser, Content: "Hello Wolinet"},
			},
		},
	)
	if err != nil {
		panic(err)
	}
	fmt.Println(resp.Choices[0].Message.Content)
}`,

    rust: (key) => `use reqwest::header::{HeaderMap, HeaderValue, AUTHORIZATION, CONTENT_TYPE};
use serde_json::json;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut headers = HeaderMap::new();
    headers.insert(CONTENT_TYPE, HeaderValue::from_static("application/json"));
    headers.insert(AUTHORIZATION, HeaderValue::from_str("Bearer ${key}")?);

    let client = reqwest::Client::new();
    let body = json!({
        "model": "Wolinet Coder v2",
        "messages": [{"role": "user", "content": "Verify memory safety in Rust"}]
    });

    let res = client.post("${gatewayApiBase}/chat/completions")
        .headers(headers)
        .json(&body)
        .send()
        .await?
        .text()
        .await?;

    println!("{}", res);
    Ok(())
}`
  };

  function updateSnippet() {
    const key = session?.api_key || 'YOUR_WOLINET_KEY';
    if (snippetContent && codeSnippets[activeLang]) {
      snippetContent.textContent = codeSnippets[activeLang](key);
    }
  }

  // Code Tab Switching
  document.querySelectorAll('.code-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.code-tab').forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      activeLang = tab.getAttribute('data-lang') || 'python';
      updateSnippet();
    });
  });

  // Copy Snippet Button
  const copySnippetBtn = document.querySelector('.copy-snippet');
  if (copySnippetBtn && snippetContent) {
    copySnippetBtn.addEventListener('click', async () => {
      await navigator.clipboard.writeText(snippetContent.textContent);
      const original = copySnippetBtn.innerHTML;
      copySnippetBtn.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 20 20" fill="#10b981"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path></svg>
        <span style="color: #10b981;">Copied</span>
      `;
      setTimeout(() => {
        copySnippetBtn.innerHTML = original;
      }, 2000);
    });
  }

  // Session & Key Management
  async function loadSession() {
    try {
      const response = await fetch('/api/wolinet/auth/session', {
        credentials: 'same-origin'
      });
      session = await response.json();
    } catch {
      session = null;
    }

    if (!session?.authenticated) {
      if (keyNode) keyNode.textContent = 'Sign in through Wolinex to view and manage your key';
      if (accountLabel) accountLabel.textContent = 'Sign in required';
      if (keyState) {
        keyState.textContent = 'NOT SIGNED IN';
        keyState.classList.remove('active');
      }
      if (sessionDot) sessionDot.classList.add('inactive');
      updateSnippet();
      return;
    }

    const key = session.api_key || '';
    if (keyNode) {
      keyNode.textContent = key ? `${key.slice(0, 10)}${'•'.repeat(24)}` : 'No key generated yet';
    }
    if (accountLabel) {
      accountLabel.textContent = session.user?.name || session.user?.email || 'Active Developer';
    }
    if (keyState) {
      keyState.textContent = 'ACTIVE KEY';
      keyState.classList.add('active');
    }
    if (sessionDot) sessionDot.classList.remove('inactive');
    updateSnippet();
  }

  // Copy Key
  document.querySelector('#copy-key')?.addEventListener('click', async () => {
    if (!session?.api_key) {
      if (keyMessage) keyMessage.textContent = 'Please sign in to copy your API key.';
      return;
    }
    await navigator.clipboard.writeText(session.api_key);
    if (keyMessage) {
      keyMessage.textContent = '✓ API Key copied to clipboard.';
      setTimeout(() => { keyMessage.textContent = ''; }, 3000);
    }
  });

  // Reveal / Hide Key
  document.querySelector('#reveal-key')?.addEventListener('click', () => {
    if (!session?.api_key) return;
    keyVisible = !keyVisible;
    const btn = document.querySelector('#reveal-key');
    if (keyVisible) {
      keyNode.textContent = session.api_key;
      if (btn) btn.textContent = 'Hide Key';
    } else {
      keyNode.textContent = `${session.api_key.slice(0, 10)}${'•'.repeat(24)}`;
      if (btn) btn.textContent = 'Reveal Key';
    }
  });

  // Rotate Key
  document.querySelector('#rotate-key')?.addEventListener('click', async () => {
    if (!session?.authenticated) {
      if (keyMessage) keyMessage.textContent = 'Please sign in through Studio to manage your key.';
      return;
    }

    if (!confirm('Are you sure you want to rotate your developer key? Applications using the previous key will need to be updated immediately.')) {
      return;
    }

    const button = document.querySelector('#rotate-key');
    if (button) button.disabled = true;
    if (keyMessage) keyMessage.textContent = 'Rotating developer key…';

    try {
      const response = await fetch('/api/wolinet/auth/regenerate-key', {
        method: 'POST',
        credentials: 'same-origin'
      });
      const result = await response.json();
      if (!response.ok || !result.api_key) {
        throw new Error(result.error || 'Key rotation failed');
      }
      session.api_key = result.api_key;
      keyVisible = true;
      keyNode.textContent = result.api_key;
      document.querySelector('#reveal-key').textContent = 'Hide Key';
      if (keyMessage) {
        keyMessage.textContent = '✓ New key generated and active across all endpoints.';
      }
      updateSnippet();
    } catch (error) {
      if (keyMessage) keyMessage.textContent = `Error: ${error.message}`;
    } finally {
      if (button) button.disabled = false;
    }
  });

  // Developer Assistant Chat
  function addMessage(content, role) {
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${role === 'user' ? 'user-bubble' : 'assistant-bubble'}`;
    bubble.innerHTML = content;
    chatLog.append(bubble);
    chatLog.scrollTop = chatLog.scrollHeight;
    return bubble;
  }

  // Quick Prompt Chips
  document.querySelectorAll('.chat-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const prompt = chip.getAttribute('data-prompt');
      if (prompt && chatInput) {
        chatInput.value = prompt;
        chatForm.dispatchEvent(new Event('submit'));
      }
    });
  });

  // Core System Prompt for Developer Copilot
  const DEVELOPER_SYSTEM_PROMPT = `You are the Wolinet AI Developer Assistant.
Your mission is to guide software developers integrating with Wolinet AI APIs and deploying autonomous multi-agent developer swarms.
Ecosystem facts:
- Standard OpenAI-compatible API endpoints at /v1.
- Flagship Models:
  1. 'Wolinet Pro': General high-capacity reasoning, synthesis, and planning (16K context).
  2. 'Wolinet Coder v2': Specialized polyglot software engineering, AST diffs, test generation, and agent loops (16K context).
  3. 'Wolinet Embed': Semantic vector representations for RAG (4K tokens, 1536 dims).
- Autonomous Agent Swarm:
  - 5 specialized roles: Planner, Designer, Builder, Tester, Deployer.
  - Disjoint file leases: Agents never conflict; each holds exclusive lock tokens on assigned files.
  - Persistent execution: Keeps running during OS sleep states with cloud continuum.
- Strict Sovereignty: 100% data sovereignty, zero external telemetry, zero training on customer prompts.
Provide direct, concise, copyable code blocks with minimal filler.`;

  chatForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const content = chatInput.value.trim();
    if (!content) return;

    addMessage(content, 'user');
    chatInput.value = '';
    const answer = addMessage('<span style="color: var(--brand-cyan);">Thinking…</span>', 'assistant');
    if (chatSubmitBtn) chatSubmitBtn.disabled = true;

    try {
      const endpoint = session?.api_key ? '/v1/chat/completions' : '/api/wolinet/chat';
      const headers = { 'Content-Type': 'application/json' };
      if (session?.api_key) {
        headers['Authorization'] = `Bearer ${session.api_key}`;
      }
      const response = await fetch(endpoint, {
        method: 'POST',
        credentials: 'same-origin',
        headers,
        body: JSON.stringify({
          model: 'Wolinet Coder v2',
          stream: Boolean(session?.api_key),
          messages: [
            { role: 'system', content: DEVELOPER_SYSTEM_PROMPT },
            { role: 'user', content: content }
          ]
        })
      });

      if (!response.ok) {
        throw new Error(`API returned ${response.status}`);
      }

      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('text/event-stream')) {
        const data = await response.json();
        answer.textContent = data.choices?.[0]?.message?.content || data.error || 'No response';
      } else {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let pending = '';
        answer.innerHTML = '';

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          pending += decoder.decode(value, { stream: true });
          const rows = pending.split('\n');
          pending = rows.pop() || '';
          for (const row of rows) {
            if (!row.startsWith('data: ') || row === 'data: [DONE]') continue;
            try {
              const data = JSON.parse(row.slice(6));
              const delta = data.choices?.[0]?.delta?.content || '';
              answer.textContent += delta;
            } catch {
              continue;
            }
          }
          chatLog.scrollTop = chatLog.scrollHeight;
        }
      }
    } catch (error) {
      answer.innerHTML = `<strong>Autonomous Response:</strong> To integrate with Wolinet AI, configure your client using <code>base_url="${window.location.origin}/v1"</code> and your active developer key. Check <a href="https://docs.wolinet.com" target="_blank" rel="noopener noreferrer" style="color: var(--brand-cyan);">Scalar API Docs</a> for exhaustive endpoint specs. (Connection: ${error.message})`;
    } finally {
      if (chatSubmitBtn) chatSubmitBtn.disabled = false;
      chatInput.focus();
    }
  });

  loadSession();
})();
