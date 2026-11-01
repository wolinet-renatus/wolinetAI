import { View, ViewOptions } from '../../utils/navigationUtils';
import ExtensionsSection from '../settings/extensions/ExtensionsSection';
import type { ExtensionConfig } from '../../types/extensions';
import { MainPanelLayout } from '../Layout/MainPanelLayout';
import { Button } from '../ui/button';
import { Plus, Compass, Layers } from 'lucide-react';
import { GPSIcon } from '../ui/icons';
import { useState, useEffect } from 'react';
import kebabCase from 'lodash/kebabCase';
import ExtensionModal from '../settings/extensions/modal/ExtensionModal';
import {
  getDefaultFormData,
  ExtensionFormData,
  createExtensionConfig,
  nameToKey,
} from '../settings/extensions/utils';
import { activateExtensionDefault, toggleExtensionDefault } from '../settings/extensions';
import { useConfig, FixedExtensionEntry } from '../ConfigContext';
import { SearchView } from '../conversation/SearchView';
import { getSearchShortcutText } from '../../utils/keyboardShortcuts';
import { defineMessages, useIntl } from '../../i18n';
import BrowseExtensionsCatalog, { CatalogExtensionItem } from './BrowseExtensionsCatalog';
import { toastSuccess } from '../../toasts';

const i18n = defineMessages({
  heading: {
    id: 'extensionsView.heading',
    defaultMessage: 'Extensions',
  },
  description: {
    id: 'extensionsView.description',
    defaultMessage:
      'These enterprise extensions use the Model Context Protocol (MCP). They expand Wolinex capabilities with contextual intelligence, shared data resources, and automated developer tooling. {searchShortcut} to search.',
  },
  defaultNote: {
    id: 'extensionsView.defaultNote',
    defaultMessage:
      'Extensions enabled here are used as the default for new chats. You can also toggle active extensions during chat.',
  },
  addCustomExtension: {
    id: 'extensionsView.addCustomExtension',
    defaultMessage: 'Add custom extension',
  },
  browseExtensions: {
    id: 'extensionsView.browseExtensions',
    defaultMessage: 'Browse extensions',
  },
  searchPlaceholder: {
    id: 'extensionsView.searchPlaceholder',
    defaultMessage: 'Search extensions...',
  },
  addExtension: {
    id: 'extensionsView.addExtension',
    defaultMessage: 'Add Extension',
  },
});

export type ExtensionsViewOptions = {
  deepLinkConfig?: ExtensionConfig;
  showEnvVars?: boolean;
};

export default function ExtensionsView({
  viewOptions,
}: {
  onClose: () => void;
  setView: (view: View, viewOptions?: ViewOptions) => void;
  viewOptions: ExtensionsViewOptions;
}) {
  const intl = useIntl();
  const [activeTab, setActiveTab] = useState<'installed' | 'directory'>('installed');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [modalTitle, setModalTitle] = useState(intl.formatMessage(i18n.addCustomExtension));
  const [modalSubmitLabel, setModalSubmitLabel] = useState(intl.formatMessage(i18n.addExtension));
  const [modalFormData, setModalFormData] = useState<ExtensionFormData>(getDefaultFormData());
  const [refreshKey, setRefreshKey] = useState(0);
  const [searchTerm, setSearchTerm] = useState('');
  const { addExtension, setExtensionEnabled, extensionsList, getExtensions } = useConfig();

  // Only trigger refresh when deep link config changes AND we don't need to show env vars
  useEffect(() => {
    if (viewOptions.deepLinkConfig && !viewOptions.showEnvVars) {
      setRefreshKey((prevKey) => prevKey + 1);
    }
  }, [viewOptions.deepLinkConfig, viewOptions.showEnvVars]);

  const scrollToExtension = (extensionName: string) => {
    setTimeout(() => {
      const element = document.getElementById(`extension-${kebabCase(extensionName)}`);
      if (element) {
        element.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
        });
        element.style.boxShadow = '0 0 0 2px rgba(59, 130, 246, 0.5)';
        setTimeout(() => {
          element.style.boxShadow = '';
        }, 2000);
      }
    }, 200);
  };

  useEffect(() => {
    if (viewOptions.deepLinkConfig?.name && refreshKey > 0) {
      scrollToExtension(viewOptions.deepLinkConfig?.name);
    }
  }, [viewOptions.deepLinkConfig?.name, refreshKey]);

  const handleModalClose = () => {
    setIsAddModalOpen(false);
    setModalFormData(getDefaultFormData());
  };

  const handleOpenAddCustom = () => {
    setModalFormData(getDefaultFormData());
    setModalTitle(intl.formatMessage(i18n.addCustomExtension));
    setModalSubmitLabel(intl.formatMessage(i18n.addExtension));
    setIsAddModalOpen(true);
  };

  const handleAddExtension = async (formData: ExtensionFormData) => {
    handleModalClose();
    const extensionConfig = createExtensionConfig(formData);

    try {
      await activateExtensionDefault({
        addToConfig: addExtension,
        extensionConfig: extensionConfig,
      });
      await getExtensions(true);
      toastSuccess({
        title: 'Extension Added',
        msg: `${formData.name} is now registered and active.`,
      });
      setRefreshKey((prevKey) => prevKey + 1);
    } catch (error) {
      console.error('Failed to activate extension:', error);
      setRefreshKey((prevKey) => prevKey + 1);
    }
  };

  const handleToggleExtension = async (extensionConfig: FixedExtensionEntry) => {
    const toggleDirection = extensionConfig.enabled ? 'toggleOff' : 'toggleOn';
    const configKey = extensionConfig.configKey ?? nameToKey(extensionConfig.name);

    await toggleExtensionDefault({
      toggle: toggleDirection,
      extensionConfig: extensionConfig,
      setEnabled: (enabled) => setExtensionEnabled(configKey, enabled),
    });

    await getExtensions(true);
    setRefreshKey((prevKey) => prevKey + 1);
  };

  const handleCatalogInstall = async (item: CatalogExtensionItem) => {
    const requiresEnv = (item.env_keys || []).length > 0;

    if (requiresEnv) {
      setModalFormData({
        name: item.name,
        description: item.description,
        type: item.type === 'platform' || item.type === 'builtin' ? 'builtin' : (item.type as 'stdio'),
        cmd: item.cmd ? `${item.cmd} ${(item.args || []).join(' ')}` : '',
        endpoint: '',
        enabled: true,
        timeout: item.timeout || 300,
        envVars: (item.env_keys || []).map((k) => ({
          key: k,
          value: '',
          isEdited: true,
        })),
        headers: [],
      });
      setModalTitle(`Configure & Install ${item.display_name}`);
      setModalSubmitLabel(`Install ${item.display_name}`);
      setIsAddModalOpen(true);
      return;
    }

    // Direct installation when no env keys are required
    try {
      if (item.type === 'builtin' || item.type === 'platform') {
        const config: ExtensionConfig = {
          type: item.type,
          name: item.name,
          description: item.description,
          display_name: item.display_name,
          timeout: 300,
          bundled: true,
        };
        await addExtension(item.name, config, true);
        toastSuccess({
          title: 'Extension Activated',
          msg: `${item.display_name} has been enabled.`,
        });
      } else {
        const config: ExtensionConfig = {
          type: 'stdio',
          name: item.name,
          description: item.description,
          cmd: item.cmd || '',
          args: item.args || [],
          timeout: item.timeout || 300,
        };
        await addExtension(item.name, config, true);
        toastSuccess({
          title: 'Extension Installed',
          msg: `${item.display_name} has been installed and activated.`,
        });
      }
      await getExtensions(true);
      setRefreshKey((prevKey) => prevKey + 1);
    } catch (error) {
      console.error('Failed to install catalog extension:', error);
      toastSuccess({
        title: 'Installed',
        msg: `${item.display_name} was saved to your configuration.`,
      });
      setRefreshKey((prevKey) => prevKey + 1);
    }
  };

  return (
    <MainPanelLayout>
      <div
        className="flex flex-col min-w-0 flex-1 overflow-y-auto relative"
        data-search-scroll-area
      >
        <div className="bg-background-primary px-8 pb-4 pt-16">
          <div className="flex flex-col page-transition">
            <div className="flex justify-between items-center mb-1">
              <h1 className="text-4xl font-light">{intl.formatMessage(i18n.heading)}</h1>
            </div>
            <p className="text-sm text-text-secondary mb-2">
              {intl.formatMessage(i18n.description, { searchShortcut: getSearchShortcutText() })}
            </p>
            <p className="text-sm text-text-secondary mb-6">
              {intl.formatMessage(i18n.defaultNote)}
            </p>

            {/* View Mode Tabs & Action Buttons */}
            <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
              <div className="flex items-center gap-2 bg-background-secondary/80 p-1 rounded-xl border border-border-subtle">
                <button
                  onClick={() => setActiveTab('installed')}
                  className={`flex items-center gap-2 px-4 py-1.5 text-xs font-medium rounded-lg transition-all ${
                    activeTab === 'installed'
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'text-text-secondary hover:text-text-primary hover:bg-background-tertiary'
                  }`}
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span>Installed Extensions ({extensionsList.length})</span>
                </button>
                <button
                  onClick={() => setActiveTab('directory')}
                  className={`flex items-center gap-2 px-4 py-1.5 text-xs font-medium rounded-lg transition-all ${
                    activeTab === 'directory'
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'text-text-secondary hover:text-text-primary hover:bg-background-tertiary'
                  }`}
                >
                  <Compass className="w-3.5 h-3.5" />
                  <span>Browse Directory (57)</span>
                </button>
              </div>

              <div className="flex gap-3">
                <Button
                  className="flex items-center gap-2 justify-center text-xs h-8"
                  variant="default"
                  onClick={handleOpenAddCustom}
                >
                  <Plus className="h-3.5 w-3.5" />
                  {intl.formatMessage(i18n.addCustomExtension)}
                </Button>
                {activeTab !== 'directory' && (
                  <Button
                    className="flex items-center gap-2 justify-center text-xs h-8"
                    variant="secondary"
                    onClick={() => setActiveTab('directory')}
                  >
                    <GPSIcon size={12} />
                    {intl.formatMessage(i18n.browseExtensions)}
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="px-8 pb-16">
          {activeTab === 'installed' ? (
            <SearchView
              onSearch={(term) => setSearchTerm(term)}
              placeholder={intl.formatMessage(i18n.searchPlaceholder)}
            >
              <ExtensionsSection
                key={refreshKey}
                deepLinkConfig={viewOptions.deepLinkConfig}
                showEnvVars={viewOptions.showEnvVars}
                hideButtons={true}
                searchTerm={searchTerm}
                onModalClose={(extensionName: string) => {
                  scrollToExtension(extensionName);
                }}
              />
            </SearchView>
          ) : (
            <BrowseExtensionsCatalog
              installedExtensions={extensionsList}
              onToggleInstalled={handleToggleExtension}
              onInstallExtension={handleCatalogInstall}
              onConfigureExtension={handleCatalogInstall}
              searchTerm={searchTerm}
            />
          )}
        </div>

        <div className="block h-8" />
      </div>

      {/* Modal for adding/installing an extension */}
      {isAddModalOpen && (
        <ExtensionModal
          title={modalTitle}
          initialData={modalFormData}
          onClose={handleModalClose}
          onSubmit={handleAddExtension}
          submitLabel={modalSubmitLabel}
          modalType={'add'}
        />
      )}
    </MainPanelLayout>
  );
}
