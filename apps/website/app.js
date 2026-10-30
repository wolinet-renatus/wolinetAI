/**
 * Wolinet AI — Sovereign Intelligence & Autonomous Development Platform
 * Unified Client-Side Application Logic (ai.wolinet.com)
 */
(() => {
  'use strict';

  // =========================================================================
  // 1. Dynamic Host & Sovereign Link Resolution
  // =========================================================================
  const isLocal = ['localhost', '127.0.0.1', '0.0.0.0'].includes(window.location.hostname);
  const host = window.location.hostname || 'localhost';
  const apiBaseUrl = `${window.location.origin}/v1`;

  const portalMap = {
    wolinex: isLocal ? `http://${host}:8081` : 'https://wolinex.wolinet.com',
    docs: isLocal ? `http://${host}:8083` : 'https://docs.wolinet.com',
    dev: isLocal ? `http://${host}:8082` : 'https://dev.wolinet.com',
    api: '/v1',
    studio: isLocal ? `http://${host}:8081` : 'https://wolinex.wolinet.com',
    downloads: '#downloads'
  };

  // Update dynamic links across the document
  document.querySelectorAll('[data-portal]').forEach((el) => {
    const portal = el.getAttribute('data-portal');
    if (portal && portalMap[portal]) {
      el.setAttribute('href', portalMap[portal]);
    }
  });

  // Convert legacy hardcoded domains if running locally
  if (isLocal) {
    document.querySelectorAll('a[href]').forEach((link) => {
      const href = link.getAttribute('href');
      if (!href) return;
      if (href.includes('wolinex.wolinet.com') || href.includes(':8080')) {
        link.setAttribute('href', `http://${host}:8081`);
      } else if (href.includes('docs.wolinet.com')) {
        link.setAttribute('href', `http://${host}:8083`);
      } else if (href.includes('dev.wolinet.com')) {
        link.setAttribute('href', `http://${host}:8082`);
      }
    });
  }

  // =========================================================================
  // 2. Client Platform Auto-Detection & Downloader State
  // =========================================================================
  function detectClientOS() {
    const ua = (navigator.userAgent || '').toLowerCase();
    const platform = (navigator.platform || '').toLowerCase();

    if (platform.includes('mac') || ua.includes('macintosh') || ua.includes('mac os')) {
      return {
        key: 'macos-arm64',
        name: 'macOS (Apple Silicon & Intel)',
        badge: 'Recommended for your Mac',
        file: 'WolinetIDE-macOS-x64.dmg',
        size: '16.7 MB',
        arch: 'Apple Silicon & Intel 64-bit'
      };
    }
    if (platform.includes('win') || ua.includes('windows')) {
      return {
        key: 'windows-x64',
        name: 'Windows 11 / 10 (x64)',
        badge: 'Recommended for your Windows PC',
        file: 'WolinetIDE-Windows-x64-setup.exe',
        size: '34 MB',
        arch: 'Windows 64-bit'
      };
    }
    if (platform.includes('linux') || ua.includes('linux') || ua.includes('x11')) {
      return {
        key: 'linux-x64',
        name: 'Linux (x86_64 AppImage)',
        badge: 'Recommended for your Linux System',
        file: 'WolinetIDE-Linux-x86_64.AppImage',
        size: '45 MB',
        arch: 'x86_64 AppImage'
      };
    }
    return {
      key: 'macos-x64',
      name: 'macOS Universal',
      badge: 'Recommended Desktop Build',
      file: 'WolinetIDE-macOS-x64.dmg',
      size: '16.7 MB',
      arch: 'Universal Desktop'
    };
  }

  const detectedOS = detectClientOS();
  const detectedPill = document.getElementById('detected-os-pill');
  const heroDownloadBtn = document.getElementById('hero-download-btn');
  const heroDownloadLabel = document.getElementById('hero-download-label');

  if (detectedPill) {
    detectedPill.innerHTML = `<span class="pulse-dot"></span><span>Detected System: ${detectedOS.name}</span>`;
  }

  if (heroDownloadBtn && heroDownloadLabel) {
    heroDownloadLabel.textContent = `Download for ${detectedOS.name.split(' ')[0]}`;
    heroDownloadBtn.setAttribute('href', `/downloads/${detectedOS.file}`);
  }

  // Highlight recommended download card
  const recommendedCard = document.querySelector(`[data-download-card="${detectedOS.key}"]`);
  if (recommendedCard) {
    recommendedCard.classList.add('recommended');
    if (!recommendedCard.querySelector('.platform-badge-rec')) {
      const recBadge = document.createElement('span');
      recBadge.className = 'platform-badge-rec';
      recBadge.textContent = 'Auto-Detected';
      recommendedCard.appendChild(recBadge);
    }
  }

  // SHA-256 Copy Buttons
  document.querySelectorAll('[data-copy-sha]').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      const sha = btn.getAttribute('data-copy-sha');
      if (!sha) return;
      try {
        await navigator.clipboard.writeText(sha);
        const originalText = btn.innerHTML;
        btn.innerHTML = `
          <span style="color: #10b981; font-weight: 600;">✓ Checksum Copied!</span>
          <span style="color: #10b981; font-family: var(--font-mono); font-size: 10px;">${sha.slice(0, 8)}…</span>
        `;
        setTimeout(() => {
          btn.innerHTML = originalText;
        }, 2500);
      } catch (err) {
        console.error('Failed to copy SHA-256:', err);
      }
    });
  });

  // =========================================================================
  // 3. Interactive Sandbox Scenarios (Hero Section)
  // =========================================================================
  const scenarios = {
    synthesis: {
      model: 'Wolinet Pro',
      prompt: 'Synthesize enterprise performance logs and strategic goals into high-impact operational priorities.',
      latency: '42 ms • 120 t/s',
      output: `1. <strong>Autonomous Workflows</strong>: Deploy collaborative 5-role agent swarms with zero overlapping file leases.<br />2. <strong>Enforce Zero-Trust Sovereignty</strong>: Keep all foundation model weights, conversation ledgers, and document embeddings within sovereign boundaries.<br />3. <strong>Hardware Sleep Continuum</strong>: Ensure complex compilation loops persist uninterrupted even during client sleep states.`
    },
    code: {
      model: 'Wolinet Coder',
      prompt: 'Write an asynchronous Python function using the OpenAI SDK to stream completions from Wolinet AI.',
      latency: '36 ms • 145 t/s',
      output: `<code>from openai import AsyncOpenAI<br /><br />client = AsyncOpenAI(<br />&nbsp;&nbsp;base_url="${apiBaseUrl}",<br />&nbsp;&nbsp;api_key="sk-wolinet-live-session"<br />)<br />stream = await client.chat.completions.create(<br />&nbsp;&nbsp;model="Wolinet Coder",<br />&nbsp;&nbsp;messages=[{"role": "user", "content": "Analyze query performance"}],<br />&nbsp;&nbsp;stream=True<br />)<br />async for chunk in stream:<br />&nbsp;&nbsp;print(chunk.choices[0].delta.content or "", end="")</code>`
    },
    selftrained: {
      model: 'Wolinet Coder v2 (Sovereign Continuous Alignment)',
      prompt: 'Verify autonomous trajectory distillation: harvest verified passing agent solutions, compile local alignment parameters, and hot-reload model weights.',
      latency: '24 ms • 165 t/s',
      output: `<strong>[Sovereign Trajectory Alignment: Active]</strong><br />• <strong>Sovereign Pedigree</strong>: 196 verified passing agent trajectories distilled locally without third-party exposure.<br />• <strong>Loss Convergence</strong>: 2.3985 &rarr; 0.1851 (-92.28% error reduction via native acceleration).<br />• <strong>Gateway Status</strong>: Hot-reloaded into sovereign inference fabric with instant zero-downtime serving.`
    },
    rag: {
      model: 'Wolinet Embed + Wolinet Pro',
      prompt: 'Search enterprise documentation for database failover and connection pooling policies.',
      latency: '24 ms • Vector Score: 0.96',
      output: `<strong>[Matched Source: Enterprise Architecture Guide §4.2]</strong><br />• <strong>High-Availability Pool</strong>: Automated circuit breaking with periodic health probing.<br />• <strong>Connection Lifecycle</strong>: 300s max connection lifetime with zero-downtime connection draining.<br />• <strong>Tenant Isolation</strong>: 100% private tenant boundaries with strict zero data retention.`
    }
  };

  const scenarioTabs = document.querySelectorAll('[data-scenario]');
  const promptEl = document.getElementById('demo-prompt-text');
  const outputEl = document.getElementById('demo-output-text');
  const modelTagEl = document.getElementById('active-model-tag');
  const latencyEl = document.getElementById('output-latency');

  if (scenarioTabs.length && promptEl && outputEl) {
    scenarioTabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        scenarioTabs.forEach((t) => t.classList.remove('active'));
        tab.classList.add('active');

        const key = tab.getAttribute('data-scenario');
        const data = scenarios[key];
        if (!data) return;

        outputEl.style.opacity = '0.3';
        setTimeout(() => {
          promptEl.textContent = data.prompt;
          outputEl.innerHTML = data.output;
          if (modelTagEl) modelTagEl.textContent = `Model: ${data.model}`;
          if (latencyEl) latencyEl.textContent = data.latency;
          outputEl.style.opacity = '1';
        }, 120);
      });
    });
  }

  // Preset pill clicks in prompt box
  document.querySelectorAll('.prompt-tag').forEach((tag) => {
    tag.addEventListener('click', () => {
      document.querySelectorAll('.prompt-tag').forEach((t) => t.classList.remove('active'));
      tag.classList.add('active');
      const presetKey = tag.getAttribute('data-preset');
      const targetTab = document.querySelector(`[data-scenario="${presetKey}"]`);
      if (targetTab) targetTab.click();
    });
  });

  // =========================================================================
  // 4. Downloader Terminal Tabs Switcher
  // =========================================================================
  const terminalTabs = document.querySelectorAll('[data-term-tab]');
  const terminalContent = document.getElementById('terminal-install-code');

  const terminalSnippets = {
    gatekeeper: `# Clear macOS Gatekeeper attribute after downloading
xattr -dr com.apple.quarantine /Applications/WolinetIDE.app

# Open WolinetIDE
open /Applications/WolinetIDE.app`,
    npx: `# Sovereign one-command download, verification, and launch
npx pandacode

# Dry run verification only
npx pandacode --dry-run`,
    linux: `# Make AppImage executable
chmod +x WolinetIDE-Linux-x86_64.AppImage

# Launch WolinetIDE
./WolinetIDE-Linux-x86_64.AppImage`,
    sha: `# Verify integrity against official SHA-256 digest
shasum -a 256 WolinetIDE-macOS-x64.dmg

# Expected:
# 0add7a1cb073b54fc1f67cf8f06f8ca982c3d3739286c0ebf0012f71bd2f4d86`
  };

  if (terminalTabs.length && terminalContent) {
    terminalTabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        terminalTabs.forEach((t) => t.classList.remove('active'));
        tab.classList.add('active');
        const tabKey = tab.getAttribute('data-term-tab');
        if (terminalSnippets[tabKey]) {
          terminalContent.textContent = terminalSnippets[tabKey];
        }
      });
    });
  }

  // Copy Terminal Command Button
  const copyTermBtn = document.getElementById('copy-term-btn');
  if (copyTermBtn && terminalContent) {
    copyTermBtn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(terminalContent.textContent);
        const originalHtml = copyTermBtn.innerHTML;
        copyTermBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor" style="color: #10b981;">
            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
          </svg>
          <span style="color: #10b981; font-weight: 600;">Copied!</span>
        `;
        setTimeout(() => {
          copyTermBtn.innerHTML = originalHtml;
        }, 2000);
      } catch (err) {
        console.error('Failed to copy command:', err);
      }
    });
  }

  // =========================================================================
  // 5. Developer Studio — Session & API Key Management
  // =========================================================================
  const keyNode = document.querySelector('#api-key');
  const keyState = document.querySelector('#key-state');
  const keyMessage = document.querySelector('#key-message');
  const copyKeyBtn = document.querySelector('#copy-key');
  const revealKeyBtn = document.querySelector('#reveal-key');
  const rotateKeyBtn = document.querySelector('#rotate-key');

  let session = null;
  let keyVisible = false;
  const defaultDevKey = 'sk-XvKFiwDoOtOe8i4lwbzb8Q';

  function getActiveApiKey() {
    return session?.api_key || defaultDevKey;
  }

  function maskKey(key) {
    if (!key) return '';
    return `${key.slice(0, 8)}${'•'.repeat(20)}`;
  }

  async function loadSession() {
    try {
      const response = await fetch('/api/wolinet/auth/session', {
        credentials: 'same-origin'
      });
      if (response.ok) {
        session = await response.json();
      }
    } catch {
      session = null;
    }

    if (session?.authenticated && session?.api_key) {
      if (keyNode) {
        keyNode.textContent = keyVisible ? session.api_key : maskKey(session.api_key);
      }
      if (keyState) {
        keyState.textContent = 'ACTIVE SESSION';
        keyState.style.borderColor = 'rgba(16, 185, 129, 0.4)';
        keyState.style.color = '#10b981';
      }
    } else {
      if (keyNode) {
        keyNode.textContent = 'Sign in via Studio to activate personal key';
      }
      if (keyState) {
        keyState.textContent = 'PUBLIC DEMO READY';
        keyState.style.borderColor = 'rgba(56, 189, 248, 0.4)';
        keyState.style.color = 'var(--brand-cyan)';
      }
    }

    updateQuickstartSnippets();
  }

  if (copyKeyBtn) {
    copyKeyBtn.addEventListener('click', async () => {
      const keyToCopy = session?.api_key || defaultDevKey;
      try {
        await navigator.clipboard.writeText(keyToCopy);
        if (keyMessage) {
          keyMessage.textContent = '✓ API key copied to clipboard';
          setTimeout(() => {
            if (keyMessage) keyMessage.textContent = '';
          }, 3000);
        }
      } catch (err) {
        console.error('Failed to copy key:', err);
      }
    });
  }

  if (revealKeyBtn) {
    revealKeyBtn.addEventListener('click', () => {
      const activeKey = session?.api_key || defaultDevKey;
      keyVisible = !keyVisible;
      if (keyNode) {
        keyNode.textContent = keyVisible ? activeKey : maskKey(activeKey);
      }
      revealKeyBtn.textContent = keyVisible ? 'Hide Key' : 'Reveal Key';
    });
  }

  if (rotateKeyBtn) {
    rotateKeyBtn.addEventListener('click', async () => {
      if (!session?.authenticated) {
        if (keyMessage) {
          keyMessage.textContent = 'Sign in through Studio to rotate personal keys.';
        }
        return;
      }

      rotateKeyBtn.disabled = true;
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
        if (keyNode) keyNode.textContent = result.api_key;
        if (revealKeyBtn) revealKeyBtn.textContent = 'Hide Key';
        if (keyMessage) {
          keyMessage.textContent = '✓ New key is active. Updated snippets below.';
        }
        updateQuickstartSnippets();
      } catch (error) {
        if (keyMessage) keyMessage.textContent = `Error: ${error.message}`;
      } finally {
        rotateKeyBtn.disabled = false;
      }
    });
  }

  // =========================================================================
  // 6. Developer Studio — Multi-Language Quickstart Snippets
  // =========================================================================
  const codeContent = document.getElementById('quickstart-code-content');
  const codeTabs = document.querySelectorAll('[data-lang]');
  let currentLang = 'python';

  function generateSnippet(lang) {
    const key = session?.api_key || 'YOUR_WOLINET_KEY';

    switch (lang) {
      case 'python':
        return `from openai import OpenAI

# Initialize client pointing to Wolinet API
client = OpenAI(
    base_url="${apiBaseUrl}",
    api_key="${key}"
)

response = client.chat.completions.create(
    model="Wolinet Pro",
    messages=[
        {"role": "system", "content": "You are Wolinet AI, a sovereign developer assistant."},
        {"role": "user", "content": "Explain our sovereign infrastructure in one sentence."}
    ]
)

print(response.choices[0].message.content)`;

      case 'ts':
        return `import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "${apiBaseUrl}",
  apiKey: "${key}",
});

async function main() {
  const completion = await client.chat.completions.create({
    model: "Wolinet Pro",
    messages: [
      { role: "system", content: "You are Wolinet AI, a sovereign developer assistant." },
      { role: "user", content: "Explain our sovereign infrastructure in one sentence." }
    ],
  });

  console.log(completion.choices[0].message.content);
}

main();`;

      case 'curl':
      default:
        return `curl ${apiBaseUrl}/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${key}" \\
  -d '{
    "model": "Wolinet Pro",
    "messages": [
      {"role": "system", "content": "You are Wolinet AI, a sovereign developer assistant."},
      {"role": "user", "content": "Explain our sovereign infrastructure in one sentence."}
    ]
  }'`;
    }
  }

  function updateQuickstartSnippets() {
    if (codeContent) {
      codeContent.textContent = generateSnippet(currentLang);
    }
  }

  if (codeTabs.length && codeContent) {
    codeTabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        codeTabs.forEach((t) => t.classList.remove('active'));
        tab.classList.add('active');
        currentLang = tab.getAttribute('data-lang') || 'python';
        updateQuickstartSnippets();
      });
    });
  }

  // Copy Code Button
  const copyCodeBtn = document.getElementById('copy-code-btn');
  if (copyCodeBtn && codeContent) {
    copyCodeBtn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(codeContent.textContent);
        const originalHtml = copyCodeBtn.innerHTML;
        copyCodeBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor" style="color: #10b981;">
            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
          </svg>
          <span style="color: #10b981; font-weight: 600;">Copied!</span>
        `;
        setTimeout(() => {
          copyCodeBtn.innerHTML = originalHtml;
        }, 2000);
      } catch (err) {
        console.error('Failed to copy code snippet:', err);
      }
    });
  }

  // =========================================================================
  // 7. Developer Studio — Live Interactive Assistant
  // =========================================================================
  const chatLog = document.getElementById('chat-log');
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  const chatSubmitBtn = document.getElementById('chat-submit-btn');

  const conversationHistory = [
    {
      role: 'system',
      content: 'You are the Wolinet Technical Assistant, an expert developer companion. Provide direct, concise, production-ready code examples and architectural guidance for Wolinet AI models.'
    }
  ];

  function appendChatBubble(content, role) {
    if (!chatLog) return null;
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${role === 'user' ? 'user-bubble' : 'assistant-bubble'}`;
    bubble.textContent = content;
    chatLog.appendChild(bubble);
    chatLog.scrollTop = chatLog.scrollHeight;
    return bubble;
  }

  if (chatForm && chatInput) {
    chatForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const userText = chatInput.value.trim();
      if (!userText) return;

      appendChatBubble(userText, 'user');
      conversationHistory.push({ role: 'user', content: userText });
      chatInput.value = '';

      const assistantBubble = appendChatBubble('', 'assistant');
      assistantBubble.classList.add('streaming');

      if (chatSubmitBtn) chatSubmitBtn.disabled = true;
      if (chatInput) chatInput.disabled = true;

      const apiKey = getActiveApiKey();

      try {
        const response = await fetch('/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${apiKey}`
          },
          body: JSON.stringify({
            model: 'Wolinet Coder',
            stream: true,
            messages: conversationHistory
          })
        });

        if (!response.ok) {
          const errText = await response.text();
          throw new Error(`API returned HTTP ${response.status}: ${errText}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let partialChunk = '';
        let fullAssistantReply = '';

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          partialChunk += decoder.decode(value, { stream: true });
          const lines = partialChunk.split('\n');
          partialChunk = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data:') || trimmed === 'data: [DONE]') continue;

            const jsonStr = trimmed.replace(/^data:\s*/, '');
            try {
              const parsed = JSON.parse(jsonStr);
              const delta = parsed.choices?.[0]?.delta?.content || '';
              if (delta) {
                fullAssistantReply += delta;
                assistantBubble.textContent = fullAssistantReply;
                chatLog.scrollTop = chatLog.scrollHeight;
              }
            } catch {
              // Ignore partial JSON chunks until complete
            }
          }
        }

        assistantBubble.classList.remove('streaming');
        if (fullAssistantReply) {
          conversationHistory.push({ role: 'assistant', content: fullAssistantReply });
        } else {
          assistantBubble.textContent = 'Request completed with empty response.';
        }
      } catch (err) {
        console.error('Chat completions error:', err);
        assistantBubble.classList.remove('streaming');
        assistantBubble.textContent = `Unable to complete request: ${err.message}. Please verify your API key or connectivity.`;
      } finally {
        if (chatSubmitBtn) chatSubmitBtn.disabled = false;
        if (chatInput) {
          chatInput.disabled = false;
          chatInput.focus();
        }
      }
    });
  }

  // =========================================================================
  // 8. Dynamic Year
  // =========================================================================
  const yearEl = document.getElementById('year');
  if (yearEl) {
    yearEl.textContent = new Date().getFullYear();
  }

  // =========================================================================
  // 9. Initial Kickoff
  // =========================================================================
  loadSession();
})();
