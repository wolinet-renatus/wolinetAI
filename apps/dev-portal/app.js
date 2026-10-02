const keyNode = document.querySelector("#api-key");
const keyState = document.querySelector("#key-state");
const keyMessage = document.querySelector("#key-message");
const accountLabel = document.querySelector("#account-label");
const chatLog = document.querySelector("#chat-log");
const chatForm = document.querySelector("#chat-form");
const chatInput = document.querySelector("#chat-input");
let session = null;
let keyVisible = false;

async function loadSession() {
  try {
    const response = await fetch("/api/wolinet/auth/session", {
      credentials: "same-origin",
    });
    session = await response.json();
  } catch {
    session = null;
  }

  if (!session?.authenticated) {
    keyNode.textContent = "Sign in through Wolinex to load your key";
    accountLabel.textContent = "Sign in required";
    keyState.textContent = "NOT SIGNED IN";
    return;
  }

  keyNode.textContent = session.api_key
    ? `${session.api_key.slice(0, 7)}${"•".repeat(22)}`
    : "No key available";
  accountLabel.textContent =
    session.user?.name || session.user?.email || "Signed in";
  keyState.textContent = "ACTIVE SESSION";
  keyState.classList.add("active");
}

document.querySelector("#copy-key").addEventListener("click", async () => {
  if (!session?.api_key) return;
  await navigator.clipboard.writeText(session.api_key);
  keyMessage.textContent = "Key copied to clipboard";
});

document.querySelector("#reveal-key").addEventListener("click", () => {
  if (!session?.api_key) return;
  keyVisible = !keyVisible;
  keyNode.textContent = keyVisible
    ? session.api_key
    : `${session.api_key.slice(0, 7)}${"•".repeat(22)}`;
  document.querySelector("#reveal-key").textContent = keyVisible
    ? "Hide key"
    : "Reveal key";
});

document.querySelector("#rotate-key").addEventListener("click", async () => {
  if (!session?.authenticated) {
    keyMessage.textContent = "Sign in through Wolinex to manage your key";
    return;
  }

  const button = document.querySelector("#rotate-key");
  button.disabled = true;
  keyMessage.textContent = "Rotating key…";
  try {
    const response = await fetch("/api/wolinet/auth/regenerate-key", {
      method: "POST",
      credentials: "same-origin",
    });
    const result = await response.json();
    if (!response.ok || !result.api_key)
      throw new Error(result.error || "Key rotation failed");
    session.api_key = result.api_key;
    keyVisible = true;
    keyNode.textContent = result.api_key;
    keyMessage.textContent =
      "New key is active. Replace the old key in your applications.";
  } catch (error) {
    keyMessage.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

document
  .querySelector(".copy-snippet")
  .addEventListener("click", async (event) => {
    const snippet = document
      .querySelector(".quickstart pre")
      .innerText.replace(
        "YOUR_WOLINET_KEY",
        session?.api_key || "YOUR_WOLINET_KEY",
      );
    await navigator.clipboard.writeText(snippet);
    event.currentTarget.textContent = "Copied";
    setTimeout(() => {
      event.currentTarget.textContent = "Copy";
    }, 1600);
  });

function addMessage(content, role) {
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role === "user" ? "user-bubble" : "assistant-bubble"}`;
  bubble.textContent = content;
  chatLog.append(bubble);
  chatLog.scrollTop = chatLog.scrollHeight;
  return bubble;
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const content = chatInput.value.trim();
  if (!content) return;
  if (!session?.api_key) {
    addMessage(
      "Sign in through Wolinex to use the developer assistant.",
      "assistant",
    );
    return;
  }

  addMessage(content, "user");
  chatInput.value = "";
  const answer = addMessage("", "assistant");
  const button = chatForm.querySelector("button");
  button.disabled = true;
  try {
    const response = await fetch("/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.api_key}`,
      },
      body: JSON.stringify({
        model: "Wolinet Coder",
        stream: true,
        messages: [{ role: "user", content }],
      }),
    });
    if (!response.ok) throw new Error(`Gateway returned ${response.status}`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let pending = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      pending += decoder.decode(value, { stream: true });
      const rows = pending.split("\n");
      pending = rows.pop() || "";
      for (const row of rows) {
        if (!row.startsWith("data: ") || row === "data: [DONE]") continue;
        try {
          answer.textContent +=
            JSON.parse(row.slice(6)).choices?.[0]?.delta?.content || "";
        } catch {
          continue;
        }
      }
      chatLog.scrollTop = chatLog.scrollHeight;
    }
  } catch (error) {
    answer.textContent = `Unable to reach the model: ${error.message}`;
  } finally {
    button.disabled = false;
    chatInput.focus();
  }
});

loadSession();
