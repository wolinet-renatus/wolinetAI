<template>
    <div>
        <RouterButton :buttons="buttons" />
        <component :is="currentComponent" />
    </div>
</template>

<script lang="ts" setup>
import { computed } from 'vue';
import i18n from '@/lang';
import AccountView from '@/views/ai/agents/model/index.vue';

const buttons = computed<RouterButton[]>(() => {
    return [
        {
            label: i18n.global.t('aiTools.agents.account'),
            path: '/ai/model/account',
        },
        {
            label: i18n.global.t('aiTools.chat.title'),
            path: '/ai/chat',
        },
    ];
});

const currentComponent = computed(() => {
    return AccountView;
});
</script>
