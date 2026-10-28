<template>
    <div class="ai-chat-view">
        <RouterButton :buttons="headerButtons" />

        <div class="ai-chat-container">
            <!-- Top Controls Bar -->
            <div class="ai-chat-header-bar">
                <div class="ai-chat-header-bar__left">
                    <div class="control-item">
                        <span class="control-label">{{ t('aiTools.chat.agentSelect') }}:</span>
                        <el-select
                            v-model="selectedAgentId"
                            class="agent-select"
                            placeholder="Select Agent"
                            @change="onAgentChange"
                            size="default"
                        >
                            <el-option
                                v-for="agent in agentOptions"
                                :key="agent.id"
                                :label="agent.name"
                                :value="agent.id"
                            >
                                <div class="select-option-row">
                                    <span>{{ agent.name }}</span>
                                    <el-tag
                                        size="small"
                                        :type="agent.status === 'Running' ? 'success' : 'info'"
                                        effect="plain"
                                    >
                                        {{ agent.status }}
                                    </el-tag>
                                </div>
                            </el-option>
                        </el-select>
                    </div>

                    <div class="control-item">
                        <span class="control-label">{{ t('aiTools.chat.modelSelect') }}:</span>
                        <el-select
                            v-model="selectedModel"
                            class="model-select"
                            placeholder="Select Model"
                            size="default"
                        >
                            <el-option
                                v-for="model in modelOptions"
                                :key="model.id"
                                :label="model.name || model.id"
                                :value="model.id"
                            >
                                <div class="select-option-row">
                                    <span>{{ model.name || model.id }}</span>
                                    <span class="model-id-hint">{{ model.id }}</span>
                                </div>
                            </el-option>
                        </el-select>
                    </div>
                </div>

                <div class="ai-chat-header-bar__right">
                    <el-button type="success" plain class="studio-btn" @click="openWebUI">
                        <el-icon class="mr-1"><Position /></el-icon>
                        {{ t('aiTools.chat.openWebuiTitle') }}
                    </el-button>
                    <el-button plain :disabled="messages.length === 0" @click="clearHistory">
                        <el-icon class="mr-1"><Delete /></el-icon>
                        {{ t('aiTools.chat.clearChat') }}
                    </el-button>
                </div>
            </div>

            <!-- Quick Action Prompts Bar -->
            <div class="quick-actions-bar">
                <span class="quick-actions-title">
                    <el-icon><Lightning /></el-icon>
                    {{ t('aiTools.chat.quickActions') }}:
                </span>
                <div class="quick-actions-list">
                    <el-tag
                        v-for="(action, idx) in quickActions"
                        :key="idx"
                        class="quick-action-tag"
                        effect="light"
                        @click="useQuickAction(action.prompt)"
                    >
                        {{ action.label }}
                    </el-tag>
                </div>
            </div>

            <!-- Messages Window -->
            <div ref="messagesScrollRef" class="messages-viewport" v-loading="initialLoading">
                <!-- Welcome Banner if empty -->
                <div v-if="messages.length === 0 && !initialLoading" class="chat-welcome">
                    <div class="chat-welcome__card">
                        <div class="chat-welcome__icon">
                            <el-icon :size="48" color="#409eff"><Cpu /></el-icon>
                        </div>
                        <h2 class="chat-welcome__title">{{ t('aiTools.chat.welcomeTitle') }}</h2>
                        <p class="chat-welcome__desc">{{ t('aiTools.chat.welcomeDesc') }}</p>

                        <div class="chat-welcome__features">
                            <div class="feature-item">
                                <div class="feature-icon">
                                    <el-icon><Monitor /></el-icon>
                                </div>
                                <div class="feature-content">
                                    <div class="feature-title">Hardware Inference Core</div>
                                    <div class="feature-desc">
                                        Integrated with Lango AI Gateway and sovereign Mitambo GPU/CPU runtime.
                                    </div>
                                </div>
                            </div>
                            <div class="feature-item">
                                <div class="feature-icon">
                                    <el-icon><Connection /></el-icon>
                                </div>
                                <div class="feature-content">
                                    <div class="feature-title">Obscura Browser Sandbox</div>
                                    <div class="feature-desc">
                                        Autonomous web automation tools available via MCP on port 8080.
                                    </div>
                                </div>
                            </div>
                            <div class="feature-item">
                                <div class="feature-icon">
                                    <el-icon><Operation /></el-icon>
                                </div>
                                <div class="feature-content">
                                    <div class="feature-title">DevOps & System Auditing</div>
                                    <div class="feature-desc">
                                        Generate verified shell commands, inspect Docker containers, and diagnose logs.
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="chat-welcome__presets">
                            <div class="presets-label">Click a prompt to get started:</div>
                            <div class="preset-cards">
                                <div
                                    v-for="(action, idx) in quickActions"
                                    :key="idx"
                                    class="preset-card"
                                    @click="useQuickAction(action.prompt)"
                                >
                                    <div class="preset-card__title">{{ action.label }}</div>
                                    <div class="preset-card__prompt">{{ action.prompt }}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Messages List -->
                <div v-else class="messages-list">
                    <div v-for="(msg, index) in messages" :key="index" class="message-row" :class="[`is-${msg.role}`]">
                        <div class="message-avatar">
                            <el-avatar v-if="msg.role === 'user'" :size="36" class="user-avatar">
                                <el-icon><UserFilled /></el-icon>
                            </el-avatar>
                            <el-avatar v-else :size="36" class="bot-avatar">
                                <el-icon><Cpu /></el-icon>
                            </el-avatar>
                        </div>

                        <div class="message-body">
                            <div class="message-meta">
                                <span class="message-author">
                                    {{
                                        msg.role === 'user'
                                            ? 'Admin'
                                            : msg.agentName || activeAgentName || 'Wolinet Copilot'
                                    }}
                                </span>
                                <el-tag
                                    v-if="msg.role === 'assistant' && msg.model"
                                    size="small"
                                    effect="plain"
                                    type="info"
                                    class="model-tag"
                                >
                                    {{ msg.model }}
                                </el-tag>
                                <span v-if="msg.durationMs" class="message-duration">{{ msg.durationMs }}ms</span>
                                <span v-if="msg.usageTokens" class="message-tokens">{{ msg.usageTokens }} tokens</span>
                            </div>

                            <div class="message-bubble">
                                <div v-if="msg.role === 'user'" class="user-content">
                                    {{ msg.content }}
                                </div>
                                <div v-else class="markdown-content">
                                    <MarkDownEditor :content="msg.content" />
                                </div>
                            </div>

                            <div v-if="msg.role === 'assistant'" class="message-actions">
                                <CopyButton :content="msg.content" />
                            </div>
                        </div>
                    </div>

                    <!-- Generating indicator -->
                    <div v-if="generating" class="message-row is-assistant is-thinking">
                        <div class="message-avatar">
                            <el-avatar :size="36" class="bot-avatar thinking-pulse">
                                <el-icon><Loading /></el-icon>
                            </el-avatar>
                        </div>
                        <div class="message-body">
                            <div class="message-meta">
                                <span class="message-author">{{ activeAgentName || 'Wolinet Copilot' }}</span>
                                <span class="thinking-text">{{ t('aiTools.chat.sending') }}</span>
                            </div>
                            <div class="message-bubble thinking-bubble">
                                <div class="dot-typing">
                                    <span></span>
                                    <span></span>
                                    <span></span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Input Bar -->
            <div class="ai-chat-input-bar">
                <div class="input-wrapper">
                    <el-input
                        ref="inputAreaRef"
                        v-model="inputText"
                        type="textarea"
                        :rows="2"
                        :autosize="{ minRows: 2, maxRows: 6 }"
                        :placeholder="t('aiTools.chat.inputPlaceholder')"
                        :disabled="generating"
                        resize="none"
                        @keydown.enter.exact.prevent="handleSend"
                    />
                    <div class="input-actions">
                        <span class="keyboard-hint">Enter to send, Shift+Enter for new line</span>
                        <el-button
                            type="primary"
                            :loading="generating"
                            :disabled="!inputText.trim()"
                            class="send-btn"
                            @click="handleSend"
                        >
                            <el-icon class="mr-1"><Promotion /></el-icon>
                            {{ t('aiTools.chat.send') }}
                        </el-button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { AI } from '@/api/interface/ai';
import { getAgentChatOptions, chatWithAgent } from '@/api/modules/ai';
import MarkDownEditor from '@/components/mkdown-editor/index.vue';
import CopyButton from '@/components/copy-button/index.vue';
import { MsgError } from '@/utils/message';
import {
    Cpu,
    Monitor,
    Connection,
    Operation,
    UserFilled,
    Loading,
    Promotion,
    Delete,
    Position,
    Lightning,
} from '@element-plus/icons-vue';

const { t } = useI18n();
const route = useRoute();

const headerButtons = [
    {
        label: t('aiTools.agents.agent'),
        path: '/ai/agents/agent',
    },
    {
        label: t('aiTools.agents.account'),
        path: '/ai/model/account',
    },
    {
        label: t('aiTools.chat.title'),
        path: '/ai/chat',
    },
];

interface ChatUIMessage extends AI.AgentChatMessage {
    agentName?: string;
    model?: string;
    durationMs?: number;
    usageTokens?: number;
}

const initialLoading = ref(true);
const generating = ref(false);
const inputText = ref('');
const inputAreaRef = ref();
const messagesScrollRef = ref<HTMLDivElement | null>(null);

const agentOptions = ref<AI.AgentItem[]>([]);
const modelOptions = ref<AI.AgentAccountModelItem[]>([]);
const selectedAgentId = ref<number | undefined>(undefined);
const selectedModel = ref<string>('wolinet-coder');
const messages = ref<ChatUIMessage[]>([]);

const quickActions = [
    {
        label: '⚡ Server Resource Audit',
        prompt: 'Audit current server hardware resources, CPU load, memory utilization, and list the top 5 resource-consuming processes.',
    },
    {
        label: '🐳 Docker & Sandbox Health',
        prompt: 'Check the operational health of Docker containers, particularly Obscura browser sandbox (wolinet-browser:8080), Lango gateway (port 4000), and Postgres database.',
    },
    {
        label: '🧠 AI Mesh Diagnostics',
        prompt: 'Probe the local Mitambo inference cluster (port 9997), OrcaCyber Defense core (port 8088), and Lango AI gateway routes (port 4000). Benchmark TTFB, model latency, and inference readiness with bearer auth.',
    },
    {
        label: '🛠️ Automation Script Generator',
        prompt: 'Generate a clean, defensive bash maintenance script to audit disk consumption, prune dead container caches, and verify systemd service uptime.',
    },
    {
        label: '🔍 Error Log Investigation',
        prompt: 'Review common systemd journalctl and container error signals, and suggest standard troubleshooting steps for unexpected service terminations.',
    },
];

const activeAgentName = computed(() => {
    if (selectedAgentId.value) {
        const found = agentOptions.value.find((a) => a.id === selectedAgentId.value);
        if (found) return found.name;
    }
    return 'Wolinet DevOps Copilot';
});

const loadOptions = async () => {
    initialLoading.value = true;
    try {
        const res = await getAgentChatOptions();
        const data = res.data;
        if (data) {
            agentOptions.value = data.agents || [];
            modelOptions.value = data.models || [];
            if (data.defaultModel) {
                selectedModel.value = data.defaultModel;
            }

            // Check if agentId passed in query
            const queryAgentId = Number(route.query.agentId);
            if (queryAgentId && agentOptions.value.some((a) => a.id === queryAgentId)) {
                selectedAgentId.value = queryAgentId;
                const match = agentOptions.value.find((a) => a.id === queryAgentId);
                if (match?.model) {
                    selectedModel.value = match.model;
                }
            } else if (agentOptions.value.length > 0) {
                selectedAgentId.value = agentOptions.value[0].id;
                if (agentOptions.value[0].model) {
                    selectedModel.value = agentOptions.value[0].model;
                }
            }
        }
    } catch (err: any) {
        MsgError(String(err?.message || 'Failed to load AI options'));
    } finally {
        initialLoading.value = false;
    }
};

const onAgentChange = (id: number) => {
    const found = agentOptions.value.find((a) => a.id === id);
    if (found?.model) {
        selectedModel.value = found.model;
    }
};

const openWebUI = () => {
    window.open('http://localhost:8081', '_blank');
};

const clearHistory = () => {
    messages.value = [];
};

const scrollToBottom = async () => {
    await nextTick();
    if (messagesScrollRef.value) {
        messagesScrollRef.value.scrollTop = messagesScrollRef.value.scrollHeight;
    }
};

const useQuickAction = (promptText: string) => {
    inputText.value = promptText;
    handleSend();
};

const handleSend = async () => {
    const text = inputText.value.trim();
    if (!text || generating.value) return;

    const userMessage: ChatUIMessage = {
        role: 'user',
        content: text,
        timestamp: Date.now(),
    };
    messages.value.push(userMessage);
    inputText.value = '';
    scrollToBottom();

    generating.value = true;
    try {
        const historyForApi: AI.AgentChatMessage[] = messages.value.map((m) => ({
            role: m.role,
            content: m.content,
        }));

        const req: AI.AgentChatReq = {
            agentId: selectedAgentId.value,
            model: selectedModel.value,
            messages: historyForApi,
        };

        const res = await chatWithAgent(req);
        if (res.data) {
            const assistantMsg: ChatUIMessage = {
                role: 'assistant',
                content: res.data.content,
                model: res.data.model || selectedModel.value,
                agentName: res.data.agentName || activeAgentName.value,
                durationMs: res.data.durationMs,
                usageTokens: res.data.usageTokens,
                timestamp: Date.now(),
            };
            messages.value.push(assistantMsg);
        }
    } catch (err: any) {
        const errorMsg: ChatUIMessage = {
            role: 'assistant',
            content: `**Error:** ${err?.message || 'AI generation failed. Please verify Lango and Mitambo are running.'}`,
            agentName: 'System Error',
            timestamp: Date.now(),
        };
        messages.value.push(errorMsg);
    } finally {
        generating.value = false;
        scrollToBottom();
    }
};

onMounted(() => {
    loadOptions();
});
</script>

<style scoped lang="scss">
.ai-chat-view {
    height: 100%;
    display: flex;
    flex-direction: column;
}

.ai-chat-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color-light);
    border-radius: 8px;
    margin-top: 16px;
    overflow: hidden;
    height: calc(100vh - 165px);
}

.ai-chat-header-bar {
    padding: 12px 20px;
    background: var(--el-bg-color-overlay);
    border-bottom: 1px solid var(--el-border-color-lighter);
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;

    &__left {
        display: flex;
        align-items: center;
        gap: 20px;
        flex-wrap: wrap;
    }

    &__right {
        display: flex;
        align-items: center;
        gap: 10px;
    }
}

.control-item {
    display: flex;
    align-items: center;
    gap: 8px;

    .control-label {
        font-size: 13px;
        font-weight: 500;
        color: var(--el-text-color-regular);
        white-space: nowrap;
    }

    .agent-select {
        width: 220px;
    }

    .model-select {
        width: 250px;
    }
}

.select-option-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;

    .model-id-hint {
        font-size: 11px;
        color: var(--el-text-color-secondary);
        margin-left: 8px;
    }
}

.quick-actions-bar {
    padding: 8px 20px;
    background: var(--el-fill-color-light);
    border-bottom: 1px solid var(--el-border-color-lighter);
    display: flex;
    align-items: center;
    gap: 10px;
    overflow-x: auto;
    white-space: nowrap;

    .quick-actions-title {
        font-size: 12px;
        font-weight: 600;
        color: var(--el-text-color-primary);
        display: flex;
        align-items: center;
        gap: 4px;
    }

    .quick-actions-list {
        display: flex;
        gap: 8px;
    }

    .quick-action-tag {
        cursor: pointer;
        transition: all 0.2s ease;
        border-radius: 12px;
        font-size: 12px;
        padding: 0 10px;

        &:hover {
            transform: translateY(-1px);
            background-color: var(--el-color-primary-light-8);
            color: var(--el-color-primary);
            border-color: var(--el-color-primary-light-5);
        }
    }
}

.messages-viewport {
    flex: 1;
    overflow-y: auto;
    padding: 24px 28px;
    background: var(--el-bg-color-page);
}

.chat-welcome {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100%;
    padding: 20px;

    &__card {
        max-width: 860px;
        background: var(--el-bg-color);
        border: 1px solid var(--el-border-color);
        border-radius: 16px;
        padding: 36px 40px;
        box-shadow: var(--el-box-shadow-light);
        text-align: center;
    }

    &__icon {
        margin-bottom: 16px;
    }

    &__title {
        font-size: 22px;
        font-weight: 700;
        margin-bottom: 8px;
        color: var(--el-text-color-primary);
        letter-spacing: -0.02em;
    }

    &__desc {
        font-size: 14px;
        color: var(--el-text-color-regular);
        line-height: 1.6;
        max-width: 680px;
        margin: 0 auto 28px;
    }

    &__features {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
        gap: 16px;
        margin-bottom: 32px;
        text-align: left;

        .feature-item {
            display: flex;
            gap: 12px;
            padding: 16px;
            background: var(--el-fill-color-light);
            border-radius: 10px;
            border: 1px solid var(--el-border-color-lighter);
        }

        .feature-icon {
            font-size: 20px;
            color: var(--el-color-primary);
            margin-top: 2px;
        }

        .feature-title {
            font-weight: 600;
            font-size: 13px;
            margin-bottom: 4px;
            color: var(--el-text-color-primary);
        }

        .feature-desc {
            font-size: 12px;
            color: var(--el-text-color-secondary);
            line-height: 1.4;
        }
    }

    &__presets {
        text-align: left;

        .presets-label {
            font-size: 13px;
            font-weight: 600;
            color: var(--el-text-color-primary);
            margin-bottom: 12px;
        }

        .preset-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 12px;
        }

        .preset-card {
            padding: 12px 14px;
            background: var(--el-bg-color);
            border: 1px solid var(--el-border-color-light);
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;

            &:hover {
                border-color: var(--el-color-primary);
                background: var(--el-color-primary-light-9);
                transform: translateY(-2px);
            }

            &__title {
                font-weight: 600;
                font-size: 12px;
                color: var(--el-text-color-primary);
                margin-bottom: 4px;
            }

            &__prompt {
                font-size: 11px;
                color: var(--el-text-color-secondary);
                overflow: hidden;
                text-overflow: ellipsis;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                line-height: 1.4;
            }
        }
    }
}

.messages-list {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.message-row {
    display: flex;
    gap: 14px;
    max-width: 92%;

    &.is-user {
        align-self: flex-end;
        flex-direction: row-reverse;

        .message-meta {
            justify-content: flex-end;
        }

        .message-bubble {
            background: var(--el-color-primary);
            color: #ffffff;
            border-radius: 12px 2px 12px 12px;
            box-shadow: 0 2px 6px rgba(64, 158, 255, 0.25);
        }

        .user-content {
            font-size: 14px;
            line-height: 1.6;
            white-space: pre-wrap;
            word-break: break-word;
        }
    }

    &.is-assistant {
        align-self: flex-start;

        .message-bubble {
            background: var(--el-bg-color);
            border: 1px solid var(--el-border-color-light);
            border-radius: 2px 12px 12px 12px;
            box-shadow: var(--el-box-shadow-light);
        }
    }
}

.message-avatar {
    flex-shrink: 0;

    .user-avatar {
        background: var(--el-color-primary);
        color: #ffffff;
    }

    .bot-avatar {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: #ffffff;
    }
}

.message-body {
    display: flex;
    flex-direction: column;
    max-width: calc(100% - 50px);
}

.message-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
    font-size: 12px;

    .message-author {
        font-weight: 600;
        color: var(--el-text-color-primary);
    }

    .model-tag {
        font-size: 11px;
    }

    .message-duration,
    .message-tokens {
        font-size: 11px;
        color: var(--el-text-color-secondary);
    }
}

.message-bubble {
    padding: 12px 16px;
    font-size: 14px;
    line-height: 1.6;

    .markdown-content {
        overflow-x: auto;

        :deep(.md-editor-preview) {
            padding: 0;
            background: transparent !important;
            font-size: 14px;
        }

        :deep(p) {
            margin-bottom: 8px;
            &:last-child {
                margin-bottom: 0;
            }
        }

        :deep(pre) {
            margin: 8px 0;
            border-radius: 6px;
        }
    }
}

.message-actions {
    display: flex;
    gap: 6px;
    margin-top: 6px;
}

.thinking-pulse {
    animation: spin 2s linear infinite;
}

@keyframes spin {
    100% {
        transform: rotate(360deg);
    }
}

.thinking-bubble {
    display: flex;
    align-items: center;
    min-height: 38px;
}

.dot-typing {
    display: flex;
    align-items: center;
    gap: 4px;

    span {
        width: 6px;
        height: 6px;
        background-color: var(--el-text-color-secondary);
        border-radius: 50%;
        display: inline-block;
        animation: dotTyping 1.4s infinite ease-in-out both;

        &:nth-child(1) {
            animation-delay: -0.32s;
        }
        &:nth-child(2) {
            animation-delay: -0.16s;
        }
    }
}

@keyframes dotTyping {
    0%,
    80%,
    100% {
        transform: scale(0);
    }
    40% {
        transform: scale(1);
    }
}

.ai-chat-input-bar {
    padding: 14px 20px;
    background: var(--el-bg-color-overlay);
    border-top: 1px solid var(--el-border-color-lighter);

    .input-wrapper {
        display: flex;
        flex-direction: column;
        gap: 8px;
        background: var(--el-bg-color);
        border: 1px solid var(--el-border-color);
        border-radius: 10px;
        padding: 8px 12px;
        transition: border-color 0.2s;

        &:focus-within {
            border-color: var(--el-color-primary);
        }

        :deep(.el-textarea__inner) {
            border: none;
            box-shadow: none;
            padding: 4px;
            background: transparent;
        }
    }

    .input-actions {
        display: flex;
        justify-content: space-between;
        align-items: center;

        .keyboard-hint {
            font-size: 11px;
            color: var(--el-text-color-secondary);
        }

        .send-btn {
            border-radius: 6px;
            padding: 8px 16px;
        }
    }
}
</style>
