/**
 * Wolinet AI Documentation Portal — Client Logic (docs.wolinet.com)
 */
(() => {
  'use strict';

  const drawer = document.querySelector('#copilot-drawer');
  const openFloatBtn = document.querySelector('#floating-assistant-btn');
  const openHeaderBtn = document.querySelector('#open-assistant-header-btn');
  const closeBtn = document.querySelector('#close-drawer-btn');
  const chatLog = document.querySelector('#copilot-chat-log');
  const chatForm = document.querySelector('#copilot-form');
  const chatInput = document.querySelector('#copilot-input');
  const submitBtn = document.querySelector('#copilot-submit-btn');

  let session = null;

  // Drawer Toggle
  function openDrawer() {
    if (drawer) drawer.classList.add('open');
    if (chatInput) chatInput.focus();
  }

  function closeDrawer() {
    if (drawer) drawer.classList.remove('open');
  }

  openFloatBtn?.addEventListener('click', openDrawer);
  openHeaderBtn?.addEventListener('click', openDrawer);
  closeBtn?.addEventListener('click', closeDrawer);

  // Close drawer on Escape
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && drawer?.classList.contains('open')) {
      closeDrawer();
    }
  });

  // Session Check
  async function loadSession() {
    try {
      const response = await fetch('/api/wolinet/auth/session', {
        credentials: 'same-origin'
      });
      session = await response.json();
    } catch {
      session = null;
    }
  }

  function addMessage(content, role) {
    const bubble = document.createElement('div');
    bubble.className = `copilot-bubble ${role}`;
    bubble.innerHTML = content;
    chatLog.append(bubble);
    chatLog.scrollTop = chatLog.scrollHeight;
    return bubble;
  }

  // Quick Chips
  document.querySelectorAll('.copilot-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const prompt = chip.getAttribute('data-prompt');
      if (prompt && chatInput) {
        chatInput.value = prompt;
        chatForm.dispatchEvent(new Event('submit'));
      }
    });
  });

  // Exhaustive API Documentation System Prompt
  const DOCS_SYSTEM_PROMPT = `You are the Wolinet AI Documentation Copilot.
You specialize in explaining the Wolinet OpenAI-compatible REST API specification, parameter contracts, headers, and schemas.
Domain Knowledge:
1. Endpoints:
   - POST /v1/chat/completions:
     • Supported params: 'model', 'messages' (role: system/user/assistant/tool), 'temperature' (0.0-2.0), 'top_p', 'stream' (bool), 'tools' (array of functions), 'tool_choice', 'response_format' (e.g. {"type": "json_object"}), 'max_tokens', 'stop'.
     • Output: Chat completion object with choices array, message delta when streaming, finish_reason.
   - POST /v1/embeddings:
     • Params: 'input' (string or list of strings), 'model' (default: 'Wolinet Embed' / 'wolinex-embed'), 'encoding_format' ('float').
     • Output: List of embedding vectors (1536 dimensions).
   - GET /v1/models:
     • Returns active sovereign model roster ('Wolinet Pro', 'Wolinet Coder v2', 'Wolinet Embed').
2. Headers:
   - 'Authorization: Bearer <WOLINET_API_KEY>'
   - 'Content-Type: application/json'
3. Error Codes & Retries:
   - 400 Bad Request: Malformed JSON or invalid parameter types.
   - 401 Unauthorized: Missing or invalid API key. Rotate key at https://dev.wolinet.com/#keys.
   - 429 Too Many Requests: Rate limit or virtual key budget reached. Implement exponential backoff with jitter.
   - 500 / 502: Upstream inference temporarily unavailable. Retry after short delay.
4. Streaming Format:
   - Server-Sent Events (SSE) emitting 'data: {"id":..., "choices":[{"delta":{"content":"..."}}]}' followed by 'data: [DONE]'.
Be accurate, quote exact parameter names, and provide clean JSON and HTTP examples.`;

  chatForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = chatInput.value.trim();
    if (!query) return;

    addMessage(query, 'user');
    chatInput.value = '';
    const answer = addMessage('<span style="color: var(--brand-cyan);">Consulting API specification…</span>', 'assistant');
    if (submitBtn) submitBtn.disabled = true;

    try {
      const authHeader = session?.api_key ? `Bearer ${session.api_key}` : 'Bearer sk-wolinet-docs-guest';
      const response = await fetch('/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': authHeader
        },
        body: JSON.stringify({
          model: 'Wolinet Coder v2',
          stream: true,
          messages: [
            { role: 'system', content: DOCS_SYSTEM_PROMPT },
            { role: 'user', content: query }
          ]
        })
      });

      if (!response.ok) {
        throw new Error(`Endpoint returned status ${response.status}`);
      }

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
    } catch (err) {
      answer.innerHTML = `<strong>API Specification Note:</strong><br />Requests to Wolinet endpoints require <code>Authorization: Bearer &lt;key&gt;</code> and <code>Content-Type: application/json</code>. To manage API keys, visit <a href="https://dev.wolinet.com/#keys" target="_blank" rel="noopener noreferrer" style="color: var(--brand-cyan);">Developer Studio</a>. (Status: ${err.message})`;
    } finally {
      if (submitBtn) submitBtn.disabled = false;
      chatInput.focus();
    }
  });

  loadSession();
})();

