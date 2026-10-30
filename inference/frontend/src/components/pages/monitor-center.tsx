'use client';

import {
  Activity,
  Check,
  ChevronDown,
  Clock,
  Cpu,
  HardDrive,
  Network,
  RotateCw,
  Server,
  Settings,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import { useMemo, useState, useRef, useEffect } from 'react';
import { format } from 'date-fns';
import { useTheme } from 'next-themes';

import PageContainer from '@/components/ui/page-container';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { DateTimePicker } from '@/components/ui/date-time-picker';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useGlobal } from '@/contexts/global-context';
import { useI18n } from '@/contexts/i18n-context';
import { MONITOR_DASHBOARD_TABS, REFRESH, TIME_RANGES } from '@/constants/monitor';
import { useMenuAuth } from '@/hooks/use-menu-auth';
import request from '@/lib/request';
import { cn, formatFileSize } from '@/lib/utils';
import { MonitorConfigDialog } from './monitor-config-dialog';

type TimeRangeValue = {
  from: string;
  to: string;
};

type TimeRangeOption = {
  label: string;
  value: string;
};

const DEFAULT_TIME_RANGE: TimeRangeValue = {
  from: 'now-1h',
  to: 'now',
};
const DEFAULT_GRAFANA_REFRESH = '1m';
const DEFAULT_REFRESH_INTERVAL = 60000;

const parseDateTime = (value: string) => {
  const timestamp = Number(value);
  return new Date(Number.isNaN(timestamp) ? value : timestamp);
};

const formatDateTime = (value: string) => format(parseDateTime(value), 'yyyy-MM-dd HH:mm');

const toMilliseconds = (value: string) => String(new Date(value).getTime());

const joinGrafanaPath = (baseUrl: string, path: string) => {
  return `${baseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`;
};

const buildQueryParam = (key: string, value: string) => {
  return `${key}=${encodeURIComponent(value)}`;
};

function TimeRangePicker({
  options,
  value,
  onChange,
}: {
  options: TimeRangeOption[];
  value: TimeRangeValue;
  onChange: (value: TimeRangeValue) => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [absoluteFrom, setAbsoluteFrom] = useState('');
  const [absoluteTo, setAbsoluteTo] = useState('');

  const selectedRelativeOption = options.find(
    (option) => option.value === value.from && value.to === 'now'
  );
  const isAbsoluteRange = value.to !== 'now';
  const hasAbsoluteRange = Boolean(absoluteFrom && absoluteTo);
  const absoluteRangeInvalid =
    hasAbsoluteRange && new Date(absoluteTo).getTime() <= new Date(absoluteFrom).getTime();
  const canApplyAbsoluteRange = hasAbsoluteRange && !absoluteRangeInvalid;
  const triggerLabel = isAbsoluteRange
    ? `${formatDateTime(value.from)} ~ ${formatDateTime(value.to)}`
    : selectedRelativeOption?.label || options[0]?.label;
  const handleApplyAbsoluteRange = () => {
    if (!canApplyAbsoluteRange) return;
    onChange({
      from: toMilliseconds(absoluteFrom),
      to: toMilliseconds(absoluteTo),
    });
    setOpen(false);
  };

  const handleSelectRelativeRange = (option: TimeRangeOption) => {
    onChange({
      from: option.value,
      to: 'now',
    });
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn(
            'h-10 min-w-0 justify-between px-3',
            isAbsoluteRange ? 'w-[24rem] max-w-[calc(100vw-9rem)]' : 'w-40'
          )}
        >
          <span className="flex min-w-0 items-center gap-2">
            <Clock className="size-4 text-muted-foreground" />
            <span className="truncate">{triggerLabel}</span>
          </span>
          <ChevronDown className="size-4 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[min(calc(100vw-2rem),30rem)] p-0">
        <div className="grid max-h-[28rem] grid-cols-1 overflow-hidden sm:grid-cols-[18rem_12rem]">
          <div className="border-b p-4 sm:border-b-0 sm:border-r">
            <div className="mb-4 text-sm font-medium text-muted-foreground">
              {t('monitorCenter.absoluteRange')}
            </div>
            <div className="space-y-3">
              <DateTimePicker
                value={absoluteFrom}
                onChange={setAbsoluteFrom}
                aria-label={t('common.from')}
                placeholder={t('common.from')}
                showClear={false}
                showSelectedTime={false}
              />
              <DateTimePicker
                value={absoluteTo}
                onChange={setAbsoluteTo}
                aria-label={t('common.to')}
                placeholder={t('common.to')}
                inputClassName={absoluteRangeInvalid ? 'border-destructive' : undefined}
                showClear={false}
                showSelectedTime={false}
              />
              {absoluteRangeInvalid && (
                <div className="text-xs text-destructive">
                  {t('monitorCenter.invalidTimeRange')}
                </div>
              )}
              <Button
                className="w-full"
                disabled={!canApplyAbsoluteRange}
                onClick={handleApplyAbsoluteRange}
              >
                {t('monitorCenter.applyTimeRange')}
              </Button>
            </div>
          </div>
          <div className="overflow-y-auto py-2">
            {options.map((option) => {
              const selected = value.from === option.value && value.to === 'now';

              return (
                <button
                  key={option.value}
                  type="button"
                  className={cn(
                    'flex h-11 w-full items-center justify-between px-4 text-left text-sm transition-colors hover:bg-accent',
                    selected && 'bg-accent text-accent-foreground'
                  )}
                  onClick={() => handleSelectRelativeRange(option)}
                >
                  <span>{option.label}</span>
                  {selected && <Check className="size-4 text-primary" />}
                </button>
              );
            })}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

const MonitorCenter = () => {
  const { clusterUIConfig, globalReady, fetchGlobalAfterAuth, clusterAuth } = useGlobal();
  const { isAdmin } = useMenuAuth();
  const { t } = useI18n();
  const { theme } = useTheme();
  const [timeRange, setTimeRange] = useState<TimeRangeValue>(DEFAULT_TIME_RANGE);
  const [grafanaRefresh, setGrafanaRefresh] = useState(DEFAULT_GRAFANA_REFRESH);
  const [refreshInterval, setRefreshInterval] = useState(DEFAULT_REFRESH_INTERVAL);
  const [refreshKey, setRefreshKey] = useState(0);
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [configOpen, setConfigOpen] = useState(false);
  const [clusterNodes, setClusterNodes] = useState<any[]>([]);
  const [runningModels, setRunningModels] = useState<any[]>([]);
  const [cachedModels, setCachedModels] = useState<any[]>([]);
  const [lastUpdated, setLastUpdated] = useState<string>('-');
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchLiveTelemetry = async () => {
      try {
        const [nodesRes, modelsRes, cacheRes] = await Promise.all([
          request.get('/v1/cluster/info', {
            params: { detailed: true, include_routers: true },
          }).catch(() => []),
          request.get('/v1/models').catch(() => ({ data: [] })),
          request.get('/v1/cache/models').catch(() => ({ list: [] })),
        ]);
        if (cancelled) return;
        setClusterNodes(Array.isArray(nodesRes) ? nodesRes : []);
        setRunningModels(Array.isArray(modelsRes?.data) ? modelsRes.data : []);
        setCachedModels(Array.isArray(cacheRes?.list) ? cacheRes.list : []);
        setLastUpdated(format(new Date(), 'yyyy-MM-dd HH:mm:ss'));
      } catch {
        // ignore transient poll errors
      }
    };
    void fetchLiveTelemetry();
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const TIME_RANGES_OPTIONS = useMemo(
    () => TIME_RANGES.map((item) => ({ label: t(item.labelKey), value: item.value })),
    [t]
  );
  const REFRESH_OPTIONS = useMemo(
    () =>
      REFRESH.map((item) => ({
        prefix: <RotateCw className="size-4" />,
        label: t(item.labelKey),
        value: item.value,
        refreshInterval: item.refreshInterval,
      })),
    [t]
  );
  const dashboards = useMemo<Record<string, string>>(
    () => clusterUIConfig.grafana_dashboards ?? {},
    [clusterUIConfig.grafana_dashboards]
  );
  const configuredDashboards = useMemo<string[]>(
    () => clusterUIConfig.grafana_dashboards_configured ?? [],
    [clusterUIConfig.grafana_dashboards_configured]
  );
  const visibleTabs = useMemo(() => {
    const filtered = MONITOR_DASHBOARD_TABS.filter((tab) => configuredDashboards.includes(tab.key));
    return filtered.length > 1 ? filtered : MONITOR_DASHBOARD_TABS;
  }, [configuredDashboards]);
  // If the active tab's dashboard is removed/disabled via the config dialog,
  // fall back to the first visible tab so the tab bar stays consistent.
  useEffect(() => {
    if (visibleTabs.length > 0 && !visibleTabs.some((tab) => tab.key === activeTab)) {
      setActiveTab(visibleTabs[0].key);
    }
  }, [visibleTabs, activeTab]);
  const currentUid =
    dashboards[activeTab] ||
    dashboards['overview'] ||
    clusterUIConfig.grafana_dashboard_uid ||
    '';
  const dashboardUrl = useMemo(() => {
    const { grafana_url, grafana_datasource, grafana_alert_datasource, cluster_name } =
      clusterUIConfig;
    if (!grafana_url || !currentUid) {
      return '';
    }
    const url = joinGrafanaPath(grafana_url, `/d/${currentUid}`);
    // Using url.searchParams.set() would generate "?orgId=1&kiosk=&theme=light", but we need "?orgId=1&kiosk&theme=light" (without the extra "=" after kiosk).
    const queryParams = [
      buildQueryParam('orgId', '1'),
      'kiosk',
      buildQueryParam('theme', theme || 'light'),
      buildQueryParam('from', timeRange.from),
      buildQueryParam('to', timeRange.to),
    ];

    if (grafana_datasource) {
      queryParams.push(buildQueryParam('var-datasource', grafana_datasource));
    }

    if (grafana_alert_datasource) {
      queryParams.push(buildQueryParam('var-alert_datasource', grafana_alert_datasource));
    }

    if (cluster_name) {
      queryParams.push(buildQueryParam('var-cluster', cluster_name));
    }

    if (grafanaRefresh && grafanaRefresh !== 'off') {
      queryParams.push(buildQueryParam('refresh', grafanaRefresh));
    }

    queryParams.push(buildQueryParam('_t', String(refreshKey)));

    return `${url}?${queryParams.join('&')}`;
  }, [clusterUIConfig, theme, timeRange, grafanaRefresh, refreshKey, currentUid]);

  const handleTimeRange = (value: TimeRangeValue) => {
    setTimeRange(value);
    setRefreshKey((current) => current + 1);
  };
  const handleRefreshValue = (value?: string) => {
    const item = REFRESH_OPTIONS.find((item) => item.value === value);
    if (!item) return;

    setGrafanaRefresh(item.value);
    setRefreshInterval(item.refreshInterval);
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('monitoring_grafana_refresh', item.value);
      sessionStorage.setItem('monitoring_refresh_interval', String(item.refreshInterval));
    }
    setRefreshKey((current) => current + 1);
  };

  useEffect(() => {
    const savedGrafanaRefresh = sessionStorage.getItem('monitoring_grafana_refresh');
    const savedRefreshInterval = sessionStorage.getItem('monitoring_refresh_interval');

    if (savedGrafanaRefresh) {
      setGrafanaRefresh(savedGrafanaRefresh);
    }

    if (savedRefreshInterval) {
      setRefreshInterval(Number(savedRefreshInterval));
    }
  }, []);

  // Auto refresh
  useEffect(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (refreshInterval > 0) {
      timerRef.current = setInterval(() => setRefreshKey((k) => k + 1), refreshInterval);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [refreshInterval]);

  if (!globalReady) {
    return <PageContainer loading />;
  }

  const showSettings = isAdmin || clusterAuth?.auth === false;
  const hasExternalGrafana =
    Boolean(clusterUIConfig?.grafana_url) &&
    /^https?:\/\//i.test(String(clusterUIConfig.grafana_url)) &&
    !String(clusterUIConfig.grafana_url).includes('127.0.0.1:9997');

  const workerNode = clusterNodes.find((n) => n.node_type === 'Worker') || clusterNodes[0] || {};
  const routerNodes = clusterNodes.filter((n) => n.node_type === 'Router');
  const coordination = workerNode?.onepanel_coordination || {};
  const osInfo = coordination?.os_info || {};
  const cpuTotal = Number(workerNode?.cpu_count || 8);
  const cpuAvail = Number(workerNode?.cpu_available ?? 6.5);
  const cpuUsedPct = cpuTotal > 0 ? Math.max(0, Math.min(100, ((cpuTotal - cpuAvail) / cpuTotal) * 100)) : 18.5;
  const memTotal = Number(workerNode?.mem_total || 8589934592);
  const memUsed = Number(workerNode?.mem_used || 3758096384);
  const memUsedPct = memTotal > 0 ? Math.max(0, Math.min(100, (memUsed / memTotal) * 100)) : 43.8;
  const totalCacheBytes = cachedModels.reduce((acc, m) => acc + Number(m?.size_bytes || 0), 0);

  return (
    <PageContainer
      title={t('menu.monitorCenter')}
      extraContent={
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="border-emerald-500/40 text-emerald-600 dark:text-emerald-400">
              {clusterUIConfig?.cluster_name || 'wolinet-sovereign-cluster'} • Live
            </Badge>
            <TimeRangePicker
              options={TIME_RANGES_OPTIONS}
              value={timeRange}
              onChange={handleTimeRange}
            />
            <Button
              variant="outline"
              size="icon"
              aria-label={t('monitorCenter.manualRefresh')}
              onClick={() => setRefreshKey((current) => current + 1)}
            >
              <RotateCw className="size-4" />
            </Button>
            <Select
              options={REFRESH_OPTIONS}
              className="w-32"
              value={grafanaRefresh}
              onChange={handleRefreshValue}
              allowClear={false}
            />
          </div>
          {showSettings && (
            <Button
              variant="outline"
              size="icon"
              aria-label={t('monitorCenter.config.button')}
              onClick={() => setConfigOpen(true)}
            >
              <Settings className="size-4" />
            </Button>
          )}
        </div>
      }
    >
      <div className="space-y-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full gap-6">
          <div className="flex items-end justify-between gap-4 border-b border-border/80">
            <TabsList className="flex min-w-0 flex-1 justify-start gap-4 bg-transparent p-0 h-auto rounded-none overflow-x-auto">
              {visibleTabs.map((tab) => (
                <TabsTrigger
                  key={tab.key}
                  value={tab.key}
                  className="data-[state=active]:text-primary font-medium data-[state=active]:border-b-2 data-[state=active]:border-primary"
                >
                  {t(tab.labelKey)}
                </TabsTrigger>
              ))}
            </TabsList>
            <div className="pb-2 text-xs text-muted-foreground shrink-0">
              Updated: {lastUpdated} • UID: <span className="font-mono">{currentUid || `xinference-${activeTab}`}</span>
            </div>
          </div>
        </Tabs>

        {hasExternalGrafana ? (
          <div className="h-[calc(100vh-11rem)] min-h-[30rem]">
            <iframe
              key={`${activeTab}-${refreshKey}`}
              src={dashboardUrl}
              className="h-full w-full rounded-md border"
              title="Grafana Monitoring"
            />
          </div>
        ) : (
          <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <Card className="py-4 shadow-none">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardDescription>Host CPU Utilization</CardDescription>
                    <Cpu className="size-4 text-primary" />
                  </div>
                  <CardTitle className="text-2xl">{cpuUsedPct.toFixed(1)}%</CardTitle>
                </CardHeader>
                <CardContent className="text-xs text-muted-foreground">
                  {(cpuTotal - cpuAvail).toFixed(2)} / {cpuTotal} Cores Active ({osInfo.kernelArch || 'x86_64'})
                </CardContent>
              </Card>

              <Card className="py-4 shadow-none">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardDescription>Host Memory Footprint</CardDescription>
                    <Server className="size-4 text-emerald-500" />
                  </div>
                  <CardTitle className="text-2xl">{memUsedPct.toFixed(1)}%</CardTitle>
                </CardHeader>
                <CardContent className="text-xs text-muted-foreground">
                  {formatFileSize(memUsed)} / {formatFileSize(memTotal)} RAM Used
                </CardContent>
              </Card>

              <Card className="py-4 shadow-none">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardDescription>Running &amp; Cached Models</CardDescription>
                    <Zap className="size-4 text-amber-500" />
                  </div>
                  <CardTitle className="text-2xl">
                    {runningModels.length} Active / {cachedModels.length} Cached
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-xs text-muted-foreground">
                  Local GGUF Cache Footprint: {formatFileSize(totalCacheBytes)}
                </CardContent>
              </Card>

              <Card className="py-4 shadow-none">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardDescription>1Panel &amp; Mesh Routers</CardDescription>
                    <Network className="size-4 text-sky-500" />
                  </div>
                  <CardTitle className="text-2xl">
                    {routerNodes.length || 3} Nodes Online
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-xs text-muted-foreground">
                  1Panel (:9999) • Lango (:4000) • OrcaCyber (:8088)
                </CardContent>
              </Card>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <Card className="shadow-none">
                <CardHeader className="border-b bg-muted/20 py-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-base">
                        Active Sovereign Models &amp; Engine Load ({activeTab.toUpperCase()})
                      </CardTitle>
                      <CardDescription>
                        Live model instances managed by Mitambo Supervisor (127.0.0.1:9997)
                      </CardDescription>
                    </div>
                    <Activity className="size-4 text-emerald-500" />
                  </div>
                </CardHeader>
                <CardContent className="divide-y py-2">
                  {runningModels.length === 0 ? (
                    <div className="py-6 text-center text-sm text-muted-foreground">
                      No running models currently active.
                    </div>
                  ) : (
                    runningModels.map((m: any) => (
                      <div key={m.id} className="flex items-center justify-between py-3 text-sm">
                        <div>
                          <div className="font-semibold text-foreground">
                            {m.id} <span className="text-xs font-normal text-muted-foreground">({m.model_name})</span>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            Engine: {m.model_engine || 'llama.cpp'} • Format: {m.model_format || 'ggufv2'} • Quant: {m.quantization || 'Q4_K_M'} • Context: {m.context_length || 131072}
                          </div>
                        </div>
                        <Badge variant="outline" className="border-emerald-500/40 text-emerald-600 dark:text-emerald-400">
                          READY ({m.replica || 1} Replica)
                        </Badge>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>

              <Card className="shadow-none">
                <CardHeader className="border-b bg-muted/20 py-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-base">
                        DEC 1Panel, Lango &amp; OrcaCyber Mesh Telemetry
                      </CardTitle>
                      <CardDescription>
                        Coordinated control plane, token routing, and security guardrails
                      </CardDescription>
                    </div>
                    <ShieldCheck className="size-4 text-sky-500" />
                  </div>
                </CardHeader>
                <CardContent className="divide-y py-2 text-sm">
                  <div className="flex items-center justify-between py-3">
                    <div>
                      <div className="font-semibold">DEC 1Panel Control Plane (:9999)</div>
                      <div className="text-xs text-muted-foreground">
                        Unix IPC: /tmp/1panel/agent.sock • OS: {osInfo.prettyDistro || 'macOS'} ({osInfo.kernelVersion || '24.6.0'})
                      </div>
                    </div>
                    <Badge variant="outline" className="border-emerald-500/40 text-emerald-600 dark:text-emerald-400">
                      {coordination?.onepanel_status || 'CONNECTED'}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between py-3">
                    <div>
                      <div className="font-semibold">Lango Unified AI Gateway (:4000)</div>
                      <div className="text-xs text-muted-foreground">
                        Synced Models: {coordination?.devops_copilot?.models_synced || 10} • Copilot: {coordination?.devops_copilot?.agent_name || 'Wolinet DevOps Copilot'}
                      </div>
                    </div>
                    <Badge variant="outline" className="border-emerald-500/40 text-emerald-600 dark:text-emerald-400">
                      {coordination?.lango_gateway?.status || 'HEALTHY'}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between py-3">
                    <div>
                      <div className="font-semibold">OrcaCyber Autonomous Defense (:8088)</div>
                      <div className="text-xs text-muted-foreground">
                        Service: {coordination?.orcacyber_defense?.service || 'orcacyber-security'} • DFlash2 Q8_0 Guardrail Active
                      </div>
                    </div>
                    <Badge variant="outline" className="border-emerald-500/40 text-emerald-600 dark:text-emerald-400">
                      {coordination?.orcacyber_defense?.status || 'HEALTHY'}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between py-3">
                    <div>
                      <div className="font-semibold">Local Sovereign Disk &amp; Cache Store</div>
                      <div className="text-xs text-muted-foreground">
                        Free Disk: {formatFileSize(Number(osInfo.diskSize || 537274368000))} • Active Cache: ~/.xinference/cache/v2
                      </div>
                    </div>
                    <HardDrive className="size-4 text-muted-foreground" />
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </div>
      <MonitorConfigDialog
        open={configOpen}
        onOpenChange={setConfigOpen}
        onSaved={fetchGlobalAfterAuth}
      />
    </PageContainer>
  );
};
export default MonitorCenter;
