import { useState, useMemo } from 'react';
import { Card } from '../ui/card';
import { Button } from '../ui/button';
import { Switch } from '../ui/switch';
import { Download, ExternalLink, Star, Cpu, Search, CheckCircle2, KeyRound } from 'lucide-react';
import communityExtensionsData from '../../community-extensions.json';
import { FixedExtensionEntry } from '../ConfigContext';

export interface CatalogExtensionItem {
  id: string;
  name: string;
  display_name: string;
  description: string;
  cmd?: string;
  args?: string[];
  env_keys?: string[];
  type: 'builtin' | 'platform' | 'stdio' | 'streamable_http';
  category: string;
  github: string;
  stars: string;
  timeout?: number;
}

interface BrowseExtensionsCatalogProps {
  installedExtensions: FixedExtensionEntry[];
  onToggleInstalled: (extension: FixedExtensionEntry) => Promise<boolean | void> | void;
  onInstallExtension: (item: CatalogExtensionItem) => Promise<void> | void;
  onConfigureExtension?: (item: CatalogExtensionItem) => void;
  searchTerm?: string;
}

// Built-in catalog entries with GitHub links and star ratings matching Goose core
const BUILTIN_CATALOG: CatalogExtensionItem[] = [
  {
    id: 'autovisualiser',
    name: 'autovisualiser',
    display_name: 'Auto Visualiser',
    description: 'Automatic data visualisation via MCP-UI with interactive charts, sankey, radar, donut, and treemaps.',
    type: 'builtin',
    category: 'Built-in',
    github: 'https://github.com/aaif-goose/goose/tree/main/crates/goose-mcp/src/autovisualiser',
    stars: '56.0k',
    env_keys: [],
    timeout: 300,
  },
  {
    id: 'code_execution',
    name: 'code_execution',
    display_name: 'Code Mode',
    description: 'Execute JavaScript code to interact with MCP tools efficiently and minimize token overhead.',
    type: 'platform',
    category: 'Built-in',
    github: 'https://github.com/aaif-goose/goose/tree/main/crates/goose/src/agents/platform_extensions/code_execution.rs',
    stars: '56.0k',
    env_keys: [],
  },
  {
    id: 'computercontroller',
    name: 'computercontroller',
    display_name: 'Computer Controller',
    description: 'Built-in computer controls for webscraping, file caching, keyboard/mouse actions, and automations.',
    type: 'builtin',
    category: 'Built-in',
    github: 'https://github.com/aaif-goose/goose/tree/main/crates/goose-mcp/src/computercontroller',
    stars: '56.0k',
    env_keys: [],
    timeout: 300,
  },
  {
    id: 'developer',
    name: 'developer',
    display_name: 'Developer',
    description: 'Built-in developer tools for file editing, directory inspection, and shell command execution.',
    type: 'platform',
    category: 'Built-in',
    github: 'https://github.com/aaif-goose/goose/tree/main/crates/goose-mcp/src/developer',
    stars: '56.0k',
    env_keys: [],
    timeout: 300,
  },
  {
    id: 'memory',
    name: 'memory',
    display_name: 'Memory',
    description: 'Built-in memory system for persistent context, user preferences, and information storage across agent sessions.',
    type: 'builtin',
    category: 'Built-in',
    github: 'https://github.com/aaif-goose/goose/tree/main/crates/goose-mcp/src/memory',
    stars: '56.0k',
    env_keys: [],
    timeout: 300,
  },
  {
    id: 'summon',
    name: 'summon',
    display_name: 'Summon',
    description: 'Load skills, subagent teams, and delegate specialized tasks to autonomous multi-agent swarms.',
    type: 'platform',
    category: 'Built-in',
    github: 'https://github.com/aaif-goose/goose/tree/main/crates/goose/src/agents/platform_extensions/summon.rs',
    stars: '56.0k',
    env_keys: [],
  },
  {
    id: 'tom',
    name: 'tom',
    display_name: 'Top of Mind',
    description: 'Inject persistent instructions into working memory every turn via MOIM message hooks.',
    type: 'platform',
    category: 'Built-in',
    github: 'https://github.com/aaif-goose/goose/tree/main/crates/goose/src/agents/platform_extensions/tom.rs',
    stars: '56.0k',
    env_keys: [],
  },
  {
    id: 'tutorial',
    name: 'tutorial',
    display_name: 'Tutorial',
    description: 'Built-in tutorial and learning management system with step-by-step interactive walk-throughs.',
    type: 'builtin',
    category: 'Built-in',
    github: 'https://github.com/aaif-goose/goose/tree/main/crates/goose-mcp/src/tutorial',
    stars: '56.0k',
    env_keys: [],
  },
  {
    id: 'apps',
    name: 'apps',
    display_name: 'Apps',
    description: 'Create and manage custom sandboxed apps and graphical interfaces directly from chat.',
    type: 'platform',
    category: 'Built-in',
    github: 'https://github.com/aaif-goose/goose/tree/main/crates/goose/src/agents/platform_extensions/apps.rs',
    stars: '56.0k',
    env_keys: [],
  },
];

export default function BrowseExtensionsCatalog({
  installedExtensions,
  onToggleInstalled,
  onInstallExtension,
  onConfigureExtension: _onConfigureExtension,
  searchTerm = '',
}: BrowseExtensionsCatalogProps) {
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [localSearch, setLocalSearch] = useState<string>('');

  // Combine built-in and community extensions
  const allCatalogExtensions: CatalogExtensionItem[] = useMemo(() => {
    return [
      ...BUILTIN_CATALOG,
      ...(communityExtensionsData as CatalogExtensionItem[]),
    ];
  }, []);

  const categories = useMemo(() => {
    const set = new Set<string>();
    set.add('All');
    set.add('Built-in');
    allCatalogExtensions.forEach((item) => {
      if (item.category) set.add(item.category);
    });
    return Array.from(set);
  }, [allCatalogExtensions]);

  // Map to quickly check if an extension is installed and its status
  const installedMap = useMemo(() => {
    const map = new Map<string, FixedExtensionEntry>();
    installedExtensions.forEach((ext) => {
      const key = ext.name.toLowerCase().replace(/[\s-_]/g, '');
      map.set(key, ext);
      if (ext.configKey) {
        map.set(ext.configKey.toLowerCase().replace(/[\s-_]/g, ''), ext);
      }
    });
    return map;
  }, [installedExtensions]);

  const activeQuery = (localSearch || searchTerm).trim().toLowerCase();

  const filteredExtensions = useMemo(() => {
    return allCatalogExtensions.filter((item) => {
      // Category filter
      if (selectedCategory !== 'All') {
        if (selectedCategory === 'Built-in' && item.type !== 'builtin' && item.type !== 'platform') {
          return false;
        }
        if (selectedCategory !== 'Built-in' && item.category !== selectedCategory) {
          return false;
        }
      }

      // Query filter
      if (!activeQuery) return true;
      const nameMatch = item.display_name.toLowerCase().includes(activeQuery) || item.name.toLowerCase().includes(activeQuery);
      const descMatch = item.description.toLowerCase().includes(activeQuery);
      const catMatch = item.category.toLowerCase().includes(activeQuery);
      const cmdMatch = (item.cmd || '').toLowerCase().includes(activeQuery) || (item.args || []).some(a => a.toLowerCase().includes(activeQuery));
      return nameMatch || descMatch || catMatch || cmdMatch;
    });
  }, [allCatalogExtensions, selectedCategory, activeQuery]);

  return (
    <div className="space-y-6">
      {/* Category Pills & Search */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
            <input
              type="text"
              value={localSearch}
              onChange={(e) => setLocalSearch(e.target.value)}
              placeholder="Search community extensions (e.g. GitHub, Supabase, Playwright, Blender)..."
              className="w-full pl-9 pr-4 py-2 bg-background-secondary/80 border border-border-subtle rounded-xl text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-blue-500/50"
            />
          </div>
        </div>

        <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
          {categories.map((cat) => {
            const isSelected = selectedCategory === cat;
            return (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`text-xs px-3 py-1.5 rounded-full font-medium transition-all whitespace-nowrap ${
                  isSelected
                    ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/20'
                    : 'bg-background-secondary text-text-secondary hover:text-text-primary hover:bg-background-tertiary border border-border-subtle'
                }`}
              >
                {cat}
                {cat === 'All' && ` (${allCatalogExtensions.length})`}
                {cat === 'Built-in' && ` (${BUILTIN_CATALOG.length})`}
              </button>
            );
          })}
        </div>

        <div className="flex items-center justify-between text-xs text-text-muted">
          <span>
            Showing <strong className="text-text-primary">{filteredExtensions.length}</strong> extensions
            {selectedCategory !== 'All' ? ` in ${selectedCategory}` : ''}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
            MCP 2026 Compatible StdIO & Built-in Engine Servers
          </span>
        </div>
      </div>

      {/* Catalog Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3.5">
        {filteredExtensions.map((item) => {
          const normKey = item.name.toLowerCase().replace(/[\s-_]/g, '');
          const normId = item.id.toLowerCase().replace(/[\s-_]/g, '');
          const installed = installedMap.get(normKey) || installedMap.get(normId);
          const isBuiltin = item.type === 'builtin' || item.type === 'platform';
          const requiresEnv = (item.env_keys || []).length > 0;

          return (
            <Card
              key={item.id}
              className="flex flex-col justify-between p-4 bg-background-primary/80 backdrop-blur border border-border-subtle hover:border-blue-500/40 transition-all duration-200 rounded-xl group relative overflow-hidden"
            >
              <div>
                {/* Header: Name, Tag, Star Badge */}
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <h3 className="font-semibold text-sm text-text-primary truncate" title={item.display_name}>
                        {item.display_name}
                      </h3>
                      {isBuiltin ? (
                        <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-blue-500/15 text-blue-400 border border-blue-500/20 rounded">
                          Built-in
                        </span>
                      ) : (
                        <span className="px-1.5 py-0.5 text-[10px] font-medium bg-purple-500/15 text-purple-400 border border-purple-500/20 rounded">
                          {item.category}
                        </span>
                      )}
                    </div>
                  </div>

                  {item.stars && (
                    <a
                      href={item.github}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-[11px] text-text-muted hover:text-yellow-400 transition-colors shrink-0 bg-background-secondary/60 px-1.5 py-0.5 rounded border border-border-subtle"
                      title="View on GitHub"
                    >
                      <Star className="w-3 h-3 fill-yellow-400/80 text-yellow-400" />
                      <span>{item.stars}</span>
                      <ExternalLink className="w-2.5 h-2.5 opacity-60" />
                    </a>
                  )}
                </div>

                {/* Description */}
                <p className="text-xs text-text-secondary line-clamp-3 mb-3 leading-relaxed">
                  {item.description}
                </p>
              </div>

              {/* Bottom: Command & Action */}
              <div className="pt-2 mt-auto border-t border-border-subtle/40 flex flex-col gap-2.5">
                <div className="flex items-center justify-between text-[11px] font-mono text-text-muted truncate">
                  <span className="truncate" title={isBuiltin ? 'Built-in Engine Tool' : `${item.cmd} ${(item.args || []).join(' ')}`}>
                    {isBuiltin ? (
                      <span className="text-cyan-400/90 flex items-center gap-1">
                        <Cpu className="w-3 h-3" /> native core
                      </span>
                    ) : (
                      <span className="text-text-muted/80">
                        {item.cmd} {(item.args || []).slice(0, 2).join(' ')}
                      </span>
                    )}
                  </span>
                  {requiresEnv && (
                    <span
                      className="text-[10px] px-1.5 py-0.2 bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded shrink-0 flex items-center gap-1"
                      title={`Requires: ${(item.env_keys || []).join(', ')}`}
                    >
                      <KeyRound className="w-2.5 h-2.5" /> API Key
                    </span>
                  )}
                </div>

                <div className="flex items-center justify-between gap-2">
                  {installed ? (
                    <>
                      <div className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Installed</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={installed.enabled}
                          onCheckedChange={() => onToggleInstalled(installed)}
                          variant="mono"
                          aria-label={`Toggle ${item.display_name}`}
                        />
                      </div>
                    </>
                  ) : (
                    <Button
                      size="sm"
                      variant="default"
                      className="w-full text-xs h-7 gap-1.5 bg-blue-600 hover:bg-blue-500 text-white font-medium"
                      onClick={() => onInstallExtension(item)}
                    >
                      <Download className="w-3 h-3" />
                      {requiresEnv ? 'Configure & Install' : 'Install'}
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {filteredExtensions.length === 0 && (
        <div className="text-center py-12 border border-dashed border-border-subtle rounded-xl">
          <Search className="w-8 h-8 text-text-muted mx-auto mb-2 opacity-50" />
          <h4 className="text-sm font-medium text-text-primary">No extensions found</h4>
          <p className="text-xs text-text-secondary mt-1">Try searching with different keywords or switch categories</p>
        </div>
      )}
    </div>
  );
}
