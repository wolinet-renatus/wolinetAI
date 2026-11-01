import {
  AppWindow,
  Clock,
  Code2,
  FileText,
  History,
  MessageSquarePlus,
  Network,
  Puzzle,
  Settings,
  Zap,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { defineMessages, type IntlShape, type MessageDescriptor } from 'react-intl';

export type NavGroupId = 'workspace' | 'agents' | 'automate' | 'integrate';

export interface NavItem {
  id: string;
  path: string;
  label: string;
  icon: LucideIcon;
  group: NavGroupId;
}

export interface NavGroup {
  id: NavGroupId;
  label: string;
}

export const NAV_GROUPS: NavGroup[] = [
  { id: 'workspace', label: 'Workspace' },
  { id: 'agents', label: 'Agents' },
  { id: 'automate', label: 'Automate' },
  { id: 'integrate', label: 'Integrate' },
];

/** Top-level nav items grouped logically by capability. */
export const NAV_ITEMS: NavItem[] = [
  // Workspace (Core Pairing & In-Editor Coding)
  { id: 'home', path: '/', label: 'New Chat', icon: MessageSquarePlus, group: 'workspace' },
  { id: 'code', path: '/code', label: 'Code', icon: Code2, group: 'workspace' },
  { id: 'sessions', path: '/sessions', label: 'Session History', icon: History, group: 'workspace' },

  // Agents (Swarm Orchestration, Skills & Recipes)
  { id: 'swarm', path: '/swarm', label: 'Swarm', icon: Network, group: 'agents' },
  { id: 'skills', path: '/skills', label: 'Skills', icon: Zap, group: 'agents' },
  { id: 'recipes', path: '/recipes', label: 'Recipes', icon: FileText, group: 'agents' },

  // Automate (Time-Based Autonomous Execution)
  { id: 'scheduler', path: '/schedules', label: 'Scheduler', icon: Clock, group: 'automate' },

  // Integrate (Extensions & Interactive MCP Cards)
  { id: 'extensions', path: '/extensions', label: 'Extensions', icon: Puzzle, group: 'integrate' },
  { id: 'apps', path: '/apps', label: 'Apps', icon: AppWindow, group: 'integrate' },
];

/** Settings is rendered separately, pinned to the bottom of the sidebar. */
export const SETTINGS_NAV_ITEM: Omit<NavItem, 'group'> & { group?: NavGroupId } = {
  id: 'settings',
  path: '/settings',
  label: 'Settings',
  icon: Settings,
};

// Translation descriptors for nav labels & groups.
const navItemMessages = defineMessages({
  home: {
    id: 'navigation.itemHome',
    defaultMessage: 'New Chat',
  },
  code: {
    id: 'navigation.itemCode',
    defaultMessage: 'Code',
  },
  sessions: {
    id: 'navigation.itemSessions',
    defaultMessage: 'Session History',
  },
  swarm: {
    id: 'navigation.itemSwarm',
    defaultMessage: 'Swarm',
  },
  skills: {
    id: 'navigation.itemSkills',
    defaultMessage: 'Skills',
  },
  recipes: {
    id: 'navigation.itemRecipes',
    defaultMessage: 'Recipes',
  },
  scheduler: {
    id: 'navigation.itemScheduler',
    defaultMessage: 'Scheduler',
  },
  extensions: {
    id: 'navigation.itemExtensions',
    defaultMessage: 'Extensions',
  },
  apps: {
    id: 'navigation.itemApps',
    defaultMessage: 'Apps',
  },
  settings: {
    id: 'navigation.itemSettings',
    defaultMessage: 'Settings',
  },
  groupWorkspace: {
    id: 'navigation.groupWorkspace',
    defaultMessage: 'Workspace',
  },
  groupAgents: {
    id: 'navigation.groupAgents',
    defaultMessage: 'Agents',
  },
  groupAutomate: {
    id: 'navigation.groupAutomate',
    defaultMessage: 'Automate',
  },
  groupIntegrate: {
    id: 'navigation.groupIntegrate',
    defaultMessage: 'Integrate',
  },
});

const NAV_ITEM_MESSAGES: Record<string, MessageDescriptor> = navItemMessages;

/** Format a NavItem's label using the provided intl instance, falling back to `item.label`. */
export function getNavItemLabel(item: Pick<NavItem, 'id' | 'label'>, intl: IntlShape): string {
  const descriptor = NAV_ITEM_MESSAGES[item.id];
  return descriptor ? intl.formatMessage(descriptor) : item.label;
}

export function getNavGroupLabel(groupId: NavGroupId, intl: IntlShape): string {
  const map: Record<NavGroupId, MessageDescriptor> = {
    workspace: navItemMessages.groupWorkspace,
    agents: navItemMessages.groupAgents,
    automate: navItemMessages.groupAutomate,
    integrate: navItemMessages.groupIntegrate,
  };
  const descriptor = map[groupId];
  return descriptor ? intl.formatMessage(descriptor) : groupId.toUpperCase();
}
