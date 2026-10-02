// *****************************************************************************
// Copyright (C) 2024 EclipseSource GmbH.
//
// This program and the accompanying materials are made available under the
// terms of the Eclipse Public License v. 2.0 which is available at
// http://www.eclipse.org/legal/epl-2.0.
//
// This Source Code may also be made available under the following Secondary
// Licenses when the conditions for such availability set forth in the Eclipse
// Public License v. 2.0 are satisfied: GNU General Public License, version 2
// with the GNU Classpath Exception which is available at
// https://www.gnu.org/software/classpath/license.html.
//
// SPDX-License-Identifier: EPL-2.0 OR GPL-2.0-only WITH Classpath-exception-2.0
// *****************************************************************************

import {
    AI_CORE_PREFERENCES_TITLE, MODEL_PROVIDER_TYPE_DETAIL, ModelProviderTypeDetail, PREFERENCE_NAME_SERVER_SIDE_COMPACTION
} from '@theia/ai-core/lib/common/ai-core-preferences';
import { SERVER_SIDE_COMPACTION_TOKEN_THRESHOLD_MINIMUM } from '@theia/ai-core/lib/common/language-model';
import { LINUX_ENV_HINT, nls, PreferenceSchema } from '@theia/core';

export const API_KEY_PREF = 'ai-features.openAiOfficial.openAiApiKey';
export const ALLOW_ENV_API_KEY_PREF = 'ai-features.openAiOfficial.allowEnvironmentApiKey';
export const MODEL_OVERRIDES_PREF = 'ai-features.openAiOfficial.modelOverrides';
export const USE_RESPONSE_API_PREF = 'ai-features.openAiOfficial.useResponseApi';
export const SERVER_SIDE_COMPACTION_PREF = 'ai-features.openAiOfficial.serverSideCompaction';
export const SERVER_SIDE_COMPACTION_TOKEN_THRESHOLD_PREF = 'ai-features.openAiOfficial.serverSideCompactionTokenThreshold';
export const CUSTOM_ENDPOINTS_PREF = 'ai-features.openAiCustom.customOpenAiModels';

export const OpenAiPreferencesSchema: PreferenceSchema = {
    properties: {
        [API_KEY_PREF]: {
            type: 'string',
            typeDetails: { [MODEL_PROVIDER_TYPE_DETAIL]: { label: 'OpenAI' } satisfies ModelProviderTypeDetail },
            markdownDescription: nls.localize('theia/ai/openai/apiKey/mdDescription',
                'Enter an API Key of your official OpenAI Account. **Please note:** By using this preference the Open AI API key will be stored in clear text \
on the machine running Theia. Use the environment variable `OPENAI_API_KEY` to set the key securely.') + LINUX_ENV_HINT,
            title: AI_CORE_PREFERENCES_TITLE,
        },
        [ALLOW_ENV_API_KEY_PREF]: {
            type: 'boolean',
            default: false,
            title: AI_CORE_PREFERENCES_TITLE,
            markdownDescription: nls.localize('theia/ai/openai/allowEnvApiKey/description',
                'Allow Theia to use an OpenAI API key found in the environment (`OPENAI_API_KEY`). '
                + 'You are asked to confirm this once before the key is used; set it back to `false` to revoke consent.'),
        },
        [MODEL_OVERRIDES_PREF]: {
            type: 'array',
            default: [],
            items: {
                type: 'string'
            },
            title: AI_CORE_PREFERENCES_TITLE,
            markdownDescription: nls.localize('theia/ai/openai/modelOverrides/description',
                'Override the models discovered from OpenAI. When empty (default), the available models are discovered from the provider. '
                + 'Set explicit model ids to use exactly those instead; discovery is then not used at all.')
        },
        [USE_RESPONSE_API_PREF]: {
            type: 'boolean',
            default: false,
            title: AI_CORE_PREFERENCES_TITLE,
            markdownDescription: nls.localize('theia/ai/openai/useResponseApi/mdDescription',
                'Use the newer OpenAI Response API instead of the Chat Completion API for official OpenAI models. ' +
                'This setting only applies to official OpenAI models - custom providers must configure this individually.')
        },
        [SERVER_SIDE_COMPACTION_PREF]: {
            type: 'string',
            enum: ['default', 'enabled', 'disabled'],
            enumDescriptions: [
                nls.localize('theia/ai/openai/compaction/default', 'Follow the global chat server-side compaction setting.'),
                nls.localize('theia/ai/openai/compaction/enabled', 'Always request server-side compaction for official OpenAI models.'),
                nls.localize('theia/ai/openai/compaction/disabled', 'Never request server-side compaction for official OpenAI models.')
            ],
            default: 'default',
            markdownDescription: nls.localize('theia/ai/openai/compaction/description',
                'Override provider-native server-side compaction for official OpenAI models. This applies to the OpenAI Response API only; ' +
                'the Chat Completions API ignores it. "default" follows the global chat setting ({0}). When effectively ' +
                'enabled, the Response API is asked to summarize older turns once the conversation grows past the provider\'s threshold.',
                `\`#${PREFERENCE_NAME_SERVER_SIDE_COMPACTION}#\``),
            title: AI_CORE_PREFERENCES_TITLE,
        },
        [SERVER_SIDE_COMPACTION_TOKEN_THRESHOLD_PREF]: {
            type: 'integer',
            minimum: SERVER_SIDE_COMPACTION_TOKEN_THRESHOLD_MINIMUM,
            markdownDescription: nls.localize('theia/ai/openai/compactionTokenThreshold/description',
                'Override the global input-token threshold for server-side compaction for official OpenAI models. When unset, the global setting or provider default applies. ' +
                'If set, the value must be at least 50,000 tokens.'),
            title: AI_CORE_PREFERENCES_TITLE,
        },
        [CUSTOM_ENDPOINTS_PREF]: {
            type: 'array',
            typeDetails: {
                [MODEL_PROVIDER_TYPE_DETAIL]: { label: 'Wolinet AI' } satisfies ModelProviderTypeDetail
            },
            title: AI_CORE_PREFERENCES_TITLE,
            markdownDescription: nls.localize('theia/ai/openai/customEndpoints/mdDescription',
                'Integrate models via the Wolinet AI LiteLLM Gateway (http://127.0.0.1:4000/v1). Dynamic routing between local engines and cloud models is managed by the gateway.'),
            default: [],
            items: {
                type: 'object',
                properties: {
                    model: {
                        type: 'string',
                        title: nls.localize('theia/ai/openai/customEndpoints/modelId/title', 'Model ID')
                    },
                    url: {
                        type: 'string',
                        title: nls.localize('theia/ai/openai/customEndpoints/url/title', 'The Open AI API compatible endpoint where the model is hosted')
                    },
                    id: {
                        type: 'string',
                        title: nls.localize('theia/ai/openai/customEndpoints/id/title', 'A unique identifier which is used in the UI to identify the custom model'),
                    },
                    apiKey: {
                        type: ['string', 'boolean'],
                        title: nls.localize('theia/ai/openai/customEndpoints/apiKey/title',
                            'Either the key to access the API served at the given url or `true` to use the global OpenAI API key'),
                    },
                    apiVersion: {
                        type: ['string', 'boolean'],
                        title: nls.localize('theia/ai/openai/customEndpoints/apiVersion/title',
                            'Either the version to access the API served at the given url in Azure or `true` to use the global OpenAI API version'),
                    },
                    deployment: {
                        type: 'string',
                        title: nls.localize('theia/ai/openai/customEndpoints/deployment/title',
                            'The deployment name to access the API served at the given url in Azure'),
                    },
                    developerMessageSettings: {
                        type: 'string',
                        enum: ['user', 'system', 'developer', 'mergeWithFollowingUserMessage', 'skip'],
                        default: 'developer',
                        title: nls.localize('theia/ai/openai/customEndpoints/developerMessageSettings/title',
                            'Controls the handling of system messages: `user`, `system`, and `developer` will be used as a role, `mergeWithFollowingUserMessage` will prefix\
                         the following user message with the system message or convert the system message to user message if the next message is not a user message.\
                         `skip` will just remove the system message), defaulting to `developer`.')
                    },
                    supportsStructuredOutput: {
                        type: 'boolean',
                        title: nls.localize('theia/ai/openai/customEndpoints/supportsStructuredOutput/title',
                            'Indicates whether the model supports structured output. `true` by default.'),
                    },
                    enableStreaming: {
                        type: 'boolean',
                        title: nls.localize('theia/ai/openai/customEndpoints/enableStreaming/title',
                            'Indicates whether the streaming API shall be used. `true` by default.'),
                    },
                    useResponseApi: {
                        type: 'boolean',
                        title: nls.localize('theia/ai/openai/customEndpoints/useResponseApi/title',
                            'Use the newer OpenAI Response API instead of the Chat Completion API. `false` by default for custom providers.'
                            + 'Note: Will automatically fall back to Chat Completions API when tools are used.'),
                    },
                    reasoningSupport: {
                        type: 'object',
                        title: nls.localize('theia/ai/openai/customEndpoints/reasoningSupport/title',
                            'Declares the model\'s reasoning capabilities. When set the chat shows a reasoning selector for this model.'),
                        properties: {
                            supportedLevels: {
                                type: 'array',
                                items: {
                                    type: 'string',
                                    enum: ['off', 'minimal', 'low', 'medium', 'high', 'auto']
                                }
                            },
                            defaultLevel: {
                                type: 'string',
                                enum: ['off', 'minimal', 'low', 'medium', 'high', 'auto']
                            }
                        }
                    },
                    headers: {
                        type: 'object',
                        additionalProperties: { type: 'string' },
                        title: nls.localize('theia/ai/openai/customEndpoints/headers/title',
                            'Additional HTTP headers sent with every request to the endpoint'),
                    }
                }
            }
        }
    }
};
