"use client";
/* eslint-disable no-restricted-syntax, max-lines, complexity, max-depth, react-hooks/set-state-in-effect */
import React, { useState, useEffect, useCallback, useRef } from "react";
import CodeBlock from "@/components/CodeBlock";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// ── Types ────────────────────────────────────────────────────────────────────

interface InferenceModel {
  id: string;
  type: string;
  icon: string;
  engine: string;
  quantization: string;
  size_b: number | string | null;
  context_length: number | null;
  ability: string[];
  description: string;
}

interface ClusterNode {
  role: string;
  address: string;
  gpus: number;
}

interface WolinetStatus {
  brand: {
    name: string;
    gateway: string;
    inference: string;
    docs: string;
    openapi: string;
  };
  gateway: {
    status: string;
    db: string;
    total_spend: number;
  };
  inference: {
    status: string;
    model_count: number;
    models: InferenceModel[];
    nodes: ClusterNode[];
  };
  timestamp: string;
}

interface ApiRefProps {
  proxySettings: {
    PROXY_BASE_URL?: string;
    LITELLM_UI_API_DOC_BASE_URL?: string | null;
  };
  accessToken?: string | null;
}

interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  healthy: "bg-emerald-500",
  connected: "bg-emerald-500",
  degraded: "bg-amber-500",
  unknown: "bg-zinc-500",
  no_models: "bg-amber-500",
  error: "bg-rose-500",
};

const MODEL_TYPE_COLORS: Record<string, string> = {
  LLM: "bg-violet-500/15 text-violet-300 border border-violet-500/30",
  embedding: "bg-blue-500/15 text-blue-300 border border-blue-500/30",
  rerank: "bg-teal-500/15 text-teal-300 border border-teal-500/30",
  image: "bg-pink-500/15 text-pink-300 border border-pink-500/30",
  audio: "bg-amber-500/15 text-amber-300 border border-amber-500/30",
};

function fmtSize(size: number | string | null): string {
  if (size === null || size === undefined) return "";
  if (typeof size === "string") return size.replace("_", ".") + "B";
  return `${size}B`;
}

function fmtCtx(ctx: number | null): string {
  if (!ctx) return "";
  return ctx >= 1000 ? `${(ctx / 1000).toFixed(0)}k ctx` : `${ctx} ctx`;
}

// ── Sub-components ────────────────────────────────────────────────────────────

const StatusDot: React.FC<{ status: string; label?: string }> = ({ status, label }) => (
  <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
    <span
      className={`w-2 h-2 rounded-full ${STATUS_COLORS[status] ?? "bg-zinc-500"} shadow-sm`}
      style={{
        boxShadow:
          status === "healthy" || status === "connected"
            ? "0 0 6px rgba(52,211,153,0.6)"
            : undefined,
      }}
    />
    {label ?? status}
  </span>
);

const StatCard: React.FC<{
  label: string;
  value: string | number;
  sub?: string;
  accent?: boolean;
}> = ({ label, value, sub, accent }) => (
  <div
    className={`p-3.5 rounded-xl border transition-all ${accent
      ? "border-violet-500/30 bg-violet-500/5 shadow-xs shadow-violet-500/10"
      : "border-[rgba(255,255,255,0.07)] bg-[#13131c]"
      }`}
  >
    <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">
      {label}
    </div>
    <div className={`text-2xl font-bold mt-1 tracking-tight ${accent ? "text-violet-300" : "text-white"}`}>
      {value}
    </div>
    {sub && <div className="text-[11px] text-muted-foreground mt-0.5">{sub}</div>}
  </div>
);

const ModelCard: React.FC<{ model: InferenceModel; base_url: string }> = ({ model, base_url }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      onClick={() => setExpanded(v => !v)}
      className="p-3.5 rounded-xl border border-[rgba(255,255,255,0.07)] bg-[#13131c] hover:border-violet-500/30 transition-all cursor-pointer group"
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="text-lg shrink-0">{model.icon || "🤖"}</span>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-semibold text-white group-hover:text-violet-300 transition-colors truncate">
                {model.id}
              </span>
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded-md font-medium shrink-0 ${MODEL_TYPE_COLORS[model.type] ?? "bg-zinc-500/15 text-zinc-300"
                  }`}
              >
                {model.type}
              </span>
            </div>
            {model.description && (
              <p className="text-[11px] text-muted-foreground truncate mt-0.5">
                {model.description}
              </p>
            )}
          </div>
        </div>

        {/* Badges */}
        <div className="flex items-center gap-2 shrink-0">
          {model.size_b && (
            <span className="text-[11px] font-mono text-muted-foreground bg-white/5 rounded px-1.5 py-0.5">
              {fmtSize(model.size_b)}
            </span>
          )}
          {model.context_length && (
            <span className="text-[11px] font-mono text-muted-foreground bg-white/5 rounded px-1.5 py-0.5">
              {fmtCtx(model.context_length)}
            </span>
          )}
        </div>
      </div>

      {/* Meta tags */}
      <div className="flex items-center gap-2 mt-2 pt-2 border-t border-white/5 flex-wrap">
        {model.quantization && (
          <span className="text-[11px] text-amber-400/80 bg-amber-500/10 rounded px-2 py-0.5">
            {model.quantization}
          </span>
        )}
        {model.engine && (
          <span className="text-[11px] text-muted-foreground">{model.engine}</span>
        )}
        <span className="ml-auto text-[10px] text-muted-foreground">
          {expanded ? "▲ collapse" : "▼ snippet"}
        </span>
      </div>

      {/* Code snippet */}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-white/5" onClick={e => e.stopPropagation()}>
          <CodeBlock
            language="python"
            code={
              (() => {
                if (model.type === "LLM") {
                  return `import openai\nclient = openai.OpenAI(\n    api_key="sk-wolinet-...",\n    base_url="${base_url}"\n)\nresponse = client.chat.completions.create(\n    model="${model.id}",\n    messages=[{"role": "user", "content": "Hello!"}]\n)\nprint(response.choices[0].message.content)`;
                }
                if (model.type === "embedding") {
                  return `import openai\nclient = openai.OpenAI(\n    api_key="sk-wolinet-...",\n    base_url="${base_url}"\n)\nresponse = client.embeddings.create(\n    model="${model.id}",\n    input="Your text to embed"\n)\nprint(response.data[0].embedding[:5])`;
                }
                return `# ${model.id} — ${model.type}\n# Endpoint: ${base_url}`;
              })()
            }
          />
        </div>
      )}
    </div>
  );
};

// ── Main Component ────────────────────────────────────────────────────────────

const APIReferenceView: React.FC<ApiRefProps> = ({ proxySettings, accessToken }) => {
  const [activeTab, setActiveTab] = useState<"explorer" | "models" | "sdk" | "agent" | "mock">("explorer");
  const [status, setStatus] = useState<WolinetStatus | null>(null);
  const [gatewayModels, setGatewayModels] = useState<InferenceModel[]>([]);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);

  // Resolve authenticated user API key from prop, session JWT, or server
  const [effectiveKey, setEffectiveKey] = useState<string>("sk-wolinet-local-dev");

  useEffect(() => {
    // 1. If accessToken prop is provided and is a valid sk- key
    if (accessToken && accessToken.trim()) {
      const trimmed = accessToken.trim();
      if (trimmed.startsWith("sk-")) {
        setEffectiveKey(trimmed);
        return;
      }
    }

    // 2. Check localStorage session / JWT
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("token") || localStorage.getItem("accessToken");
      if (stored && stored.trim()) {
        const trimmed = stored.trim();
        if (trimmed.startsWith("sk-")) {
          setEffectiveKey(trimmed);
          return;
        }
        if (trimmed.includes(".")) {
          try {
            const parts = trimmed.split(".");
            if (parts.length === 3) {
              const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
              if (payload?.key && typeof payload.key === "string" && payload.key.startsWith("sk-")) {
                setEffectiveKey(payload.key);
                return;
              }
            }
          } catch { }
        }
      }

      // 3. Fallback: auto-detect from /wolinet/key
      fetch("/wolinet/key", { credentials: "include" })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data?.key && typeof data.key === "string" && data.key.startsWith("sk-")) {
            setEffectiveKey(data.key);
          }
        })
        .catch(() => { });
    }
  }, [accessToken]);

  // Derive gateway origin dynamically for cross-origin requests
  const gatewayOrigin = (() => {
    try {
      if (proxySettings?.PROXY_BASE_URL) return new URL(proxySettings.PROXY_BASE_URL).origin;
    } catch { }
    return typeof window !== "undefined" ? window.location.origin : "";
  })();

  // Resolve gateway base URL
  let base_url = gatewayOrigin;
  const customDocBaseUrl = proxySettings?.LITELLM_UI_API_DOC_BASE_URL;
  if (customDocBaseUrl && customDocBaseUrl.trim()) {
    base_url = customDocBaseUrl;
  } else if (proxySettings?.PROXY_BASE_URL) {
    base_url = proxySettings.PROXY_BASE_URL;
  }

  // Agent Chat State (Self-Hosted OpenAPI Chat)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Hello! I am **Wolinet AI Agent**, your Sovereign Developer Intelligence Assistant connected to the live OpenAPI specification.\n\n" +
        "Ask me anything about discovering endpoints, writing production client code in Python or TypeScript, streaming completions, managing enterprise quotas, or designing sovereign agentic workflows.",
    },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  const scalarUrl = effectiveKey
    ? `${gatewayOrigin}/docs?token=${encodeURIComponent(effectiveKey)}`
    : `${gatewayOrigin}/docs`;
  const statusUrl = `${gatewayOrigin}/wolinet/status`;

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    setStatusError(null);
    try {
      const res = await fetch(statusUrl, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: WolinetStatus = await res.json();
      setStatus(data);
      try {
        const modelsRes = await fetch(`${gatewayOrigin}/v1/models`, {
          headers: { Authorization: `Bearer ${effectiveKey}` },
          cache: "no-store",
        });
        if (!modelsRes.ok) throw new Error(`HTTP ${modelsRes.status}`);
        const modelPayload = await modelsRes.json();
        const rows = Array.isArray(modelPayload?.data) ? modelPayload.data : [];
        setGatewayModels(rows.filter((model: any) => typeof model?.id === "string").map((model: any) => ({
          id: model.id,
          type: "LLM",
          icon: "🤖",
          engine: model.owned_by || "Wolinet AI",
          quantization: "",
          size_b: null,
          context_length: null,
          ability: ["chat"],
          description: "Enabled in the Wolinet AI Gateway",
        })));
      } catch {
        setGatewayModels([]);
      }
      setLastRefresh(new Date());
    } catch (err) {
      setStatusError(err instanceof Error ? err.message : "Failed to fetch status");
    } finally {
      setLoading(false);
    }
  }, [statusUrl, gatewayOrigin, effectiveKey]);

  // Fetch on mount + auto-refresh every 30s
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30_000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // Route the embedded assistant through a model currently advertised by the gateway.
  const sendChatMessage = async (promptText?: string) => {
    const textToSend = promptText || chatInput;
    if (!textToSend.trim() || chatLoading) return;
    const selectedModel = llmModels.find(model => model.id === "Wolinet Coder")?.id ?? llmModels[0]?.id;
    if (!selectedModel) {
      setChatMessages(prev => [...prev, { role: "assistant", content: "No active gateway model is available right now." }]);
      return;
    }

    const userMsg: ChatMessage = { role: "user", content: textToSend };
    setChatMessages(prev => [...prev, userMsg]);
    setChatInput("");
    setChatLoading(true);

    try {
      const res = await fetch(`${gatewayOrigin}/v1/chat/completions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer sk-wolinet-local-dev",
        },
        body: JSON.stringify({
          model: selectedModel,
          messages: [
            {
              role: "system",
              content:
                "You are Wolinet AI Agent, an expert developer assistant for Wolinet AI. " +
                "You provide exact, production-ready code examples for calling Wolinet AI endpoints (OpenAI-compatible /v1/chat/completions, /v1/models, /wolinet/status, and enterprise token quota management). " +
                "Always format code in standard markdown codeblocks.",
            },
            ...chatMessages,
            userMsg,
          ],
          temperature: 0.2,
        }),
      });

      if (!res.ok) {
        throw new Error(`Gateway returned HTTP ${res.status}`);
      }

      const data = await res.json();
      const reply = data.choices?.[0]?.message?.content || "No response received.";
      setChatMessages(prev => [...prev, { role: "assistant", content: reply }]);
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      setChatMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: `⚠ Error contacting local model: ${errorMsg}. Make sure the gateway is running on ${gatewayOrigin}.`,
        },
      ]);
    } finally {
      setChatLoading(false);
      setTimeout(() => {
        if (chatScrollRef.current) {
          chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
        }
      }, 50);
    }
  };

  const handleCopyKey = () => {
    navigator.clipboard.writeText(effectiveKey);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  const gwStatus = status?.gateway.status ?? "unknown";
  const infStatus = status?.inference.status ?? "unknown";
  const models = gatewayModels;
  const nodes = status?.inference.nodes ?? [];
  const llmModels = models.filter(m => m.type === "LLM");
  const defaultModel = llmModels.find(model => model.id === "Wolinet Coder")?.id ?? llmModels[0]?.id ?? "";
  const embedModels = models.filter(m => m.type === "embedding");
  const rerankModels = models.filter(m => m.type === "rerank");

  return (
    <div className="flex flex-col w-full" style={{ height: "calc(100vh - 64px)", background: "#0d0d12" }}>
      {/* ── Top bar ──────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-[rgba(124,109,250,0.15)] bg-[#0d0d12] shrink-0">
        <div className="flex items-center gap-4">
          {/* Brand */}
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[15px] font-bold text-white tracking-tight">Wolinet AI</span>
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-violet-500/20 text-violet-300 border border-violet-500/30 font-medium">
                Sovereign Gateway
              </span>
            </div>
            <div className="text-[11px] text-muted-foreground mt-0.5 flex items-center gap-2">
              <StatusDot status={gwStatus} label={`Gateway ${gwStatus}`} />
              <span className="text-[rgba(255,255,255,0.15)]">·</span>
              <StatusDot status={infStatus} label={`Inference ${infStatus}`} />
              {lastRefresh && (
                <>
                  <span className="text-[rgba(255,255,255,0.15)]">·</span>
                  <span className="text-[10px]">Updated {lastRefresh.toLocaleTimeString()}</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Auth indicator */}
          <button
            onClick={handleCopyKey}
            title="Click to copy your authenticated API key"
            className="hidden md:flex items-center gap-1.5 text-[11px] font-mono px-2.5 py-1.5 rounded-lg border border-violet-500/20 bg-violet-500/5 text-violet-300 hover:bg-violet-500/10 transition-colors"
          >
            <span>🔑</span>
            <span>{effectiveKey.length > 20 ? `${effectiveKey.slice(0, 8)}...${effectiveKey.slice(-4)}` : effectiveKey}</span>
            <span className="text-[10px] text-muted-foreground">{copiedKey ? "✓ Copied" : "Copy"}</span>
          </button>

          {/* View toggle */}
          <div className="flex rounded-lg border border-[rgba(255,255,255,0.1)] overflow-hidden text-[11px]">
            {(
              [
                { id: "explorer", label: "🔭 Explorer (Scalar)" },
                { id: "models", label: "🧠 Live Models" },
                { id: "sdk", label: "⚡ Client SDKs" },
                { id: "agent", label: "🤖 Wolinet AI Agent" },
                { id: "mock", label: "🧪 Mock Server" },
              ] as const
            ).map((tab, idx) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-3 py-1.5 transition-colors capitalize ${activeTab === tab.id
                  ? "bg-violet-600 text-white font-medium"
                  : "bg-transparent text-muted-foreground hover:text-foreground"
                  } ${idx !== 0 ? "border-l border-[rgba(255,255,255,0.1)]" : ""}`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <button
            onClick={fetchStatus}
            disabled={loading}
            className="text-[11px] px-3 py-1.5 rounded-lg border border-[rgba(255,255,255,0.1)] hover:bg-white/5 transition-colors text-muted-foreground hover:text-foreground disabled:opacity-40"
            title="Refresh status"
          >
            {loading ? "⟳" : "↺"} Refresh
          </button>

          <a
            href={scalarUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] px-3 py-1.5 rounded-lg border border-violet-500/30 hover:bg-violet-500/10 transition-colors text-violet-300 hover:text-violet-200"
          >
            Open Scalar ↗
          </a>
        </div>
      </div>

      {/* ── Content area ─────────────────────────────────────────────────────── */}

      {/* 1. EXPLORER: Scalar iframe with multi-target switcher */}
      {activeTab === "explorer" && (
        <div className="flex-1 flex flex-col w-full relative">
          <div className="px-5 py-2 bg-[#13131c] border-b border-white/5 flex items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center gap-3">
              <span>🎯 <strong>Platform:</strong> Wolinet AI Sovereign Gateway</span>
              <span>·</span>
              <span>🔒 <strong>Pre-authorized:</strong> <code>Bearer {effectiveKey}</code></span>
            </div>
            <span className="text-[11px]">Powered by Wolinet Technologies Ltd</span>
          </div>
          <iframe
            src={scalarUrl}
            title="Wolinet AI — API Reference (Scalar)"
            className="flex-1 w-full border-0"
            loading="lazy"
            allow="clipboard-write"
          />
        </div>
      )}

      {/* 2. MODELS: live model cards */}
      {activeTab === "models" && (
        <div className="flex-1 overflow-y-auto p-5" style={{ background: "#0d0d12" }}>
          {statusError && (
            <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/25 text-rose-300 text-sm">
              ⚠ {statusError} — showing cached data if available
            </div>
          )}

          {/* Stats row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            <StatCard
              label="Total Models"
              value={status?.inference.model_count ?? "—"}
              sub="loaded on inference"
              accent
            />
            <StatCard label="LLM" value={llmModels.length} sub="language models" />
            <StatCard
              label="Embedding + Rerank"
              value={embedModels.length + rerankModels.length}
              sub="vector & ranking"
            />
            <StatCard
              label="Cluster Nodes"
              value={nodes.length}
              sub={nodes.some(n => n.gpus > 0) ? `${nodes.reduce((s, n) => s + n.gpus, 0)} GPU(s)` : "CPU only"}
            />
          </div>

          {/* Brand + endpoint info */}
          <div className="mb-5 p-4 rounded-xl border border-[rgba(124,109,250,0.18)] bg-violet-500/5">
            <div className="text-xs font-semibold text-violet-300 mb-2 uppercase tracking-widest">
              {status?.brand.name ?? "Wolinet AI"} — Platform Endpoints
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[12px] font-mono">
              <div className="flex gap-2">
                <span className="text-muted-foreground w-20 shrink-0">Gateway</span>
                <span className="text-foreground">{status?.brand.gateway ?? base_url}</span>
              </div>
              <div className="flex gap-2">
                <span className="text-muted-foreground w-20 shrink-0">Inference</span>
                <span className="text-foreground">{status?.brand.inference ?? (gatewayOrigin ? `${gatewayOrigin}/inference` : "Distributed Inference Engine")}</span>
              </div>
              <div className="flex gap-2">
                <span className="text-muted-foreground w-20 shrink-0">OpenAPI</span>
                <a
                  href={status?.brand.openapi ?? `${gatewayOrigin}/openapi.json`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-violet-300 hover:underline"
                >
                  {status?.brand.openapi ?? `${gatewayOrigin}/openapi.json`}
                </a>
              </div>
              <div className="flex gap-2">
                <span className="text-muted-foreground w-20 shrink-0">Scalar Docs</span>
                <a
                  href={status?.brand.docs ?? scalarUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-violet-300 hover:underline"
                >
                  {status?.brand.docs ?? scalarUrl}
                </a>
              </div>
            </div>
          </div>

          {/* Models sections */}
          <div className="space-y-5">
            {llmModels.length > 0 && (
              <section>
                <h2 className="text-[11px] uppercase tracking-widest text-muted-foreground mb-2 font-semibold">
                  💬 Large Language Models ({llmModels.length})
                </h2>
                <div className="space-y-2">
                  {llmModels.map(m => (
                    <ModelCard key={m.id} model={m} base_url={base_url} />
                  ))}
                </div>
              </section>
            )}
            {embedModels.length > 0 && (
              <section>
                <h2 className="text-[11px] uppercase tracking-widest text-muted-foreground mb-2 font-semibold">
                  📄 Embedding Models ({embedModels.length})
                </h2>
                <div className="space-y-2">
                  {embedModels.map(m => (
                    <ModelCard key={m.id} model={m} base_url={base_url} />
                  ))}
                </div>
              </section>
            )}
            {rerankModels.length > 0 && (
              <section>
                <h2 className="text-[11px] uppercase tracking-widest text-muted-foreground mb-2 font-semibold">
                  🔍 Rerank Models ({rerankModels.length})
                </h2>
                <div className="space-y-2">
                  {rerankModels.map(m => (
                    <ModelCard key={m.id} model={m} base_url={base_url} />
                  ))}
                </div>
              </section>
            )}
          </div>
        </div>
      )}

      {/* 3. CLIENT SDKS (Phase 4): Wolinet SDKs & OpenAI Drop-in */}
      {activeTab === "sdk" && (
        <div className="flex-1 overflow-y-auto p-5" style={{ background: "#0d0d12" }}>
          <div className="mb-4">
            <h2 className="text-sm font-semibold text-foreground">Official Client SDKs & Libraries</h2>
            <p className="text-[12px] text-muted-foreground mt-1">
              Use our native SDKs generated via Scalar tools or any standard OpenAI client library.
            </p>
          </div>

          <Tabs defaultValue="ts-sdk">
            <TabsList variant="line" className="border-b rounded-none w-full justify-start h-auto p-0">
              <TabsTrigger value="ts-sdk" className="rounded-none px-4 py-2 flex-none text-[12px]">
                TypeScript SDK (@wolinet/sdk)
              </TabsTrigger>
              <TabsTrigger value="py-sdk" className="rounded-none px-4 py-2 flex-none text-[12px]">
                Python SDK (wolinet)
              </TabsTrigger>
              <TabsTrigger value="openai" className="rounded-none px-4 py-2 flex-none text-[12px]">
                OpenAI Client (Python)
              </TabsTrigger>
              <TabsTrigger value="quotas" className="rounded-none px-4 py-2 flex-none text-[12px]">
                Enterprise Quotas & Billing
              </TabsTrigger>
              <TabsTrigger value="curl" className="rounded-none px-4 py-2 flex-none text-[12px]">
                cURL
              </TabsTrigger>
            </TabsList>

            <TabsContent value="ts-sdk" keepMounted>
              <div className="space-y-3">
                <div className="p-3 bg-white/5 rounded-lg text-xs font-mono">
                  npm install @wolinet/sdk
                </div>
                <CodeBlock
                  language="typescript"
                  code={`import { WolinetAI } from '@wolinet/sdk';

const client = new WolinetAI({
  baseUrl: '${base_url}',
  apiKey: '${effectiveKey}',
});

// Run code generation with local sovereign model
const completion = await client.chat.completions.create({
  model: '${defaultModel}',
  messages: [{ role: 'user', content: 'Write a Fibonacci sequence in Rust' }],
});

console.log(completion.choices[0].message.content);

// Check live system telemetry
const status = await client.status();
console.log('Cluster status:', status.inference.status);`}
                />
              </div>
            </TabsContent>

            <TabsContent value="py-sdk" keepMounted>
              <div className="space-y-3">
                <div className="p-3 bg-white/5 rounded-lg text-xs font-mono">
                  pip install -e packages/wolinet-python
                </div>
                <CodeBlock
                  language="python"
                  code={`from wolinet import WolinetAI

client = WolinetAI(base_url="${base_url}", api_key="${effectiveKey}")

# Generate response with local sovereign model
res = client.chat_completion(
    model="${defaultModel}",
    messages=[{"role": "user", "content": "Explain async/await in Python"}],
)

print(res["choices"][0]["message"]["content"])

# Check cluster telemetry
status = client.status()
print(f"Gateway: {status['gateway']['status']}, Models: {status['inference']['model_count']}")`}
                />
              </div>
            </TabsContent>

            <TabsContent value="openai" keepMounted>
              <CodeBlock
                language="python"
                code={`import openai

# Wolinet AI Gateway is 100% OpenAI-compatible
client = openai.OpenAI(
    api_key="${effectiveKey}",
    base_url="${base_url}"
)

response = client.chat.completions.create(
    model="${defaultModel}",
    messages=[
        {"role": "system", "content": "You are Wolinet AI, a sovereign intelligence."},
        {"role": "user", "content": "How do I optimize local GGUF models?"}
    ],
    stream=True
)

for chunk in response:
    content = chunk.choices[0].delta.content or ""
    print(content, end="", flush=True)`}
              />
            </TabsContent>

            <TabsContent value="quotas" keepMounted>
              <CodeBlock
                language="typescript"
                code={`import { WolinetAI } from '@wolinet/sdk';

const client = new WolinetAI({ baseUrl: '${base_url}', apiKey: '${effectiveKey}' });

// Query real-time token quota, spend attribution, and rate limits
const quota = await client.user.info();
console.log('Active Token Quota & User Limits:', quota);`}
              />
            </TabsContent>

            <TabsContent value="curl" keepMounted>
              <CodeBlock
                language="bash"
                code={`# Chat completion with streaming
curl ${base_url}/v1/chat/completions \\
  -H "Authorization: Bearer ${effectiveKey}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${defaultModel}",
    "stream": true,
    "messages": [
      {"role": "user", "content": "Write hello world in Zig"}
    ]
  }'

# Live platform status aggregator
curl ${base_url}/wolinet/status`}
              />
            </TabsContent>
          </Tabs>
        </div>
      )}

      {/* 4. WOLINET AI DEVELOPER ASSISTANT: Sovereign "Chat with your API" */}
      {activeTab === "agent" && (
        <div className="flex-1 flex flex-col overflow-hidden p-5" style={{ background: "#0d0d12" }}>
          <div className="flex items-center justify-between mb-3 shrink-0">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-semibold text-white">Wolinet AI Sovereign Assistant — Chat with your API</span>
                <span className="text-[10px] bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                  {defaultModel || "No active gateway model"}
                </span>
              </div>
              <p className="text-[12px] text-muted-foreground mt-0.5">
                Sovereign developer assistant trained on Wolinet AI OpenAPI specifications and routing rules.
              </p>
            </div>
            <button
              onClick={() =>
                setChatMessages([
                  {
                    role: "assistant",
                    content: "Chat cleared. What can I help you query on Wolinet AI?",
                  },
                ])
              }
              className="text-xs px-2.5 py-1 rounded border border-white/10 hover:bg-white/5 text-muted-foreground"
            >
              Clear
            </button>
          </div>

          {/* Quick prompts */}
          <div className="flex items-center gap-2 mb-3 overflow-x-auto pb-1 shrink-0">
            {[
              "How do I use POST /guardrails/apply_guardrail?",
              "How do I stream responses in Python?",
              "How do I manage enterprise token quotas?",
              "Generate cURL command for completions",
              "What endpoints are available on /wolinet/status?",
            ].map(prompt => (
              <button
                key={prompt}
                onClick={() => sendChatMessage(prompt)}
                disabled={chatLoading}
                className="text-[11px] whitespace-nowrap px-2.5 py-1 rounded-full border border-violet-500/20 bg-violet-500/5 text-violet-300 hover:bg-violet-500/15 transition-colors disabled:opacity-50"
              >
                + {prompt}
              </button>
            ))}
          </div>

          {/* Messages container */}
          <div
            ref={chatScrollRef}
            className="flex-1 overflow-y-auto space-y-3 p-4 rounded-xl border border-white/10 bg-[#13131c] mb-3"
          >
            {chatMessages.map((msg, i) => (
              <div
                key={i}
                className={`flex gap-3 text-xs leading-relaxed ${msg.role === "user" ? "justify-end" : "justify-start"
                  }`}
              >
                <div
                  className={`p-3.5 rounded-xl max-w-[85%] ${msg.role === "user"
                    ? "bg-violet-600 text-white"
                    : "bg-[#1a1a28] text-gray-200 border border-white/5 font-sans"
                    }`}
                >
                  <div className="font-semibold text-[11px] mb-1 opacity-70">
                    {msg.role === "user" ? "You" : "🤖 Wolinet AI Agent"}
                  </div>
                  <div className="whitespace-pre-wrap">{msg.content}</div>
                </div>
              </div>
            ))}
            {chatLoading && (
              <div className="flex gap-2 text-xs text-muted-foreground items-center p-2">
                <span className="w-2 h-2 rounded-full bg-violet-400 animate-pulse" />
                <span>Wolinet AI is generating response...</span>
              </div>
            )}
          </div>

          {/* Input field */}
          <form
            onSubmit={e => {
              e.preventDefault();
              sendChatMessage();
            }}
            className="flex gap-2 shrink-0"
          >
            <input
              type="text"
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              placeholder="Ask about endpoints, request schemas, or code snippets..."
              disabled={chatLoading}
              className="flex-1 px-4 py-2.5 rounded-xl border border-white/10 bg-[#13131c] text-white text-xs placeholder:text-muted-foreground focus:outline-hidden focus:border-violet-500/50"
            />
            <button
              type="submit"
              disabled={chatLoading || !chatInput.trim()}
              className="px-4 py-2.5 rounded-xl bg-violet-600 text-white font-medium text-xs hover:bg-violet-500 disabled:opacity-40 transition-colors"
            >
              Send
            </button>
          </form>
        </div>
      )}

      {/* 5. MOCK SERVER (Phase 3): Zero-GPU Testing */}
      {activeTab === "mock" && (
        <div className="flex-1 overflow-y-auto p-5" style={{ background: "#0d0d12" }}>
          <div className="mb-4">
            <h2 className="text-sm font-semibold text-foreground"> wolinet  Mock Server (Phase 3)</h2>
            <p className="text-[12px] text-muted-foreground mt-1">
              Develop frontends and run CI/CD tests with zero GPU memory and $0 cloud cost.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div className="p-4 rounded-xl border border-white/10 bg-[#13131c]">
              <div className="text-xs font-semibold text-violet-300 mb-2">How to Run Locally</div>
              <p className="text-xs text-muted-foreground mb-3 leading-relaxed">
                Launch the standalone Wolinet Mock Gateway. It mocks streaming chat completions,
                models, health status, and hosts an embedded Scalar reference.
              </p>
              <div className="p-3 bg-black/40 rounded-lg text-xs font-mono text-emerald-400">
                make mock
              </div>
              <div className="text-[11px] text-muted-foreground mt-2">
                Or directly: <code>python3 scripts/mock_server.py</code>
              </div>
            </div>

            <div className="p-4 rounded-xl border border-white/10 bg-[#13131c]">
              <div className="text-xs font-semibold text-violet-300 mb-2">Mock Server Features</div>
              <ul className="text-xs text-muted-foreground space-y-1.5 list-disc list-inside">
                <li>Server-Sent Events (SSE) streaming support</li>
                <li>Simulates high-throughput chat completions, embeddings, and multimodal models</li>
                <li>Built-in Scalar API Reference at <code>{base_url}/docs</code></li>
                <li>Zero dependencies — runs instantly on any server or workstation</li>
              </ul>
            </div>
          </div>

          <div className="p-4 rounded-xl border border-violet-500/20 bg-violet-500/5">
            <div className="text-xs font-semibold text-white mb-2">Test Mock Streaming Request</div>
            <CodeBlock
              language="bash"
              code={`# Call the mock server streaming endpoint
curl \${base_url}/v1/chat/completions \\
  -H "Authorization: Bearer \${effectiveKey}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "\${defaultModel}",
    "stream": true,
    "messages": [{"role": "user", "content": "Testing mock server"}]
  }'`}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default APIReferenceView;
