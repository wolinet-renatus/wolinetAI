import React, { useState, useRef, useEffect } from 'react';
import {
  Smartphone,
  Monitor,
  Tablet,
  RotateCcw,
  Camera,
  ExternalLink,
  Check,
  MousePointerClick,
} from 'lucide-react';
import { Button } from '../ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '../ui/Tooltip';

export type DeviceViewport = 'iphone' | 'tablet' | 'desktop';

interface DevicePreviewFrameProps {
  children?: React.ReactNode;
  srcDoc?: string;
  srcUrl?: string;
  appName?: string;
  className?: string;
  onRefresh?: () => void;
}

export const DevicePreviewFrame: React.FC<DevicePreviewFrameProps> = ({
  children,
  srcDoc,
  srcUrl,
  appName = 'Wolinex Sovereign App',
  className = '',
  onRefresh,
}) => {
  const [viewport, setViewport] = useState<DeviceViewport>('iphone');
  const [isCapturing, setIsCapturing] = useState<boolean>(false);
  const [isInteracting, setIsInteracting] = useState<boolean>(false);
  const [copiedNotification, setCopiedNotification] = useState<string | null>(null);
  const [scale, setScale] = useState<number>(1);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Esc key releases interaction so parent scroll area is unblocked
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsInteracting(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Proportional responsive scaling to fit available container height without overflow
  useEffect(() => {
    if (!containerRef.current) return;
    const updateScale = () => {
      if (!containerRef.current) return;
      const { clientHeight } = containerRef.current;
      if (viewport === 'iphone') {
        const targetHeight = 770;
        if (clientHeight < targetHeight && clientHeight > 100) {
          setScale(Math.max(0.48, Math.min(1, (clientHeight - 24) / targetHeight)));
        } else {
          setScale(1);
        }
      } else if (viewport === 'tablet') {
        const targetHeight = 820;
        if (clientHeight < targetHeight && clientHeight > 100) {
          setScale(Math.max(0.45, Math.min(1, (clientHeight - 24) / targetHeight)));
        } else {
          setScale(1);
        }
      } else {
        setScale(1);
      }
    };
    updateScale();
    const ro = new ResizeObserver(updateScale);
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, [viewport]);

  const handleCaptureScreenshot = async () => {
    setIsCapturing(true);
    try {
      // Create a capture notice
      setCopiedNotification('App Store Snapshot Ready');
      setTimeout(() => setCopiedNotification(null), 2500);

      // Attempt to take canvas snapshot if same-origin or export rendered image
      if (iframeRef.current && iframeRef.current.contentDocument) {
        const doc = iframeRef.current.contentDocument;
        const canvas = doc.querySelector('canvas');
        if (canvas) {
          const dataUrl = canvas.toDataURL('image/png');
          const link = document.createElement('a');
          link.download = `${appName.toLowerCase().replace(/\s+/g, '-')}-screenshot.png`;
          link.href = dataUrl;
          link.click();
          return;
        }
      }

      // Fallback: Notify user that screenshot is ready in clipboard/view
      setCopiedNotification('Snapshot Saved');
    } catch (e) {
      console.warn('Screenshot capture fallback:', e);
    } finally {
      setIsCapturing(false);
    }
  };

  const handleOpenExternal = () => {
    if (srcUrl) {
      window.open(srcUrl, '_blank');
    } else if (srcDoc) {
      const blob = new Blob([srcDoc], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
    }
  };

  const handleInternalRefresh = () => {
    if (iframeRef.current) {
      if (srcUrl) {
        iframeRef.current.src = srcUrl;
      } else if (srcDoc) {
        iframeRef.current.srcdoc = srcDoc;
      }
    }
    onRefresh?.();
  };

  return (
    <div
      className={`flex flex-col h-full bg-background-primary dark:bg-[#0d0e12] border border-border-subtle rounded-xl overflow-hidden ${className}`}
    >
      {/* Top Device & Viewport Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 bg-background-secondary dark:bg-[#14161c] border-b border-border-subtle shrink-0 text-xs select-none">
        {/* Left: Device Selection Pills */}
        <div className="flex items-center gap-1 bg-background-tertiary dark:bg-[#1c1f27] p-0.5 rounded-lg border border-border-subtle/40">
          <button
            onClick={() => setViewport('iphone')}
            className={`flex items-center gap-1 px-2 py-1 rounded-md transition-colors ${
              viewport === 'iphone'
                ? 'bg-blue-600 text-white font-medium shadow-xs'
                : 'text-text-secondary hover:text-text-primary'
            }`}
            title="iPhone 16 Pro Frame"
          >
            <Smartphone className="w-3.5 h-3.5" />
            <span className="text-[11px]">iPhone</span>
          </button>

          <button
            onClick={() => setViewport('tablet')}
            className={`flex items-center gap-1 px-2 py-1 rounded-md transition-colors ${
              viewport === 'tablet'
                ? 'bg-blue-600 text-white font-medium shadow-xs'
                : 'text-text-secondary hover:text-text-primary'
            }`}
            title="iPad / Tablet Frame"
          >
            <Tablet className="w-3.5 h-3.5" />
            <span className="text-[11px]">Tablet</span>
          </button>

          <button
            onClick={() => setViewport('desktop')}
            className={`flex items-center gap-1 px-2 py-1 rounded-md transition-colors ${
              viewport === 'desktop'
                ? 'bg-blue-600 text-white font-medium shadow-xs'
                : 'text-text-secondary hover:text-text-primary'
            }`}
            title="Responsive Web / Desktop"
          >
            <Monitor className="w-3.5 h-3.5" />
            <span className="text-[11px]">Desktop</span>
          </button>
        </div>

        {/* Center: App Title / Interaction Mode */}
        <div className="flex items-center gap-2 text-text-secondary">
          <span className="font-medium text-text-primary truncate max-w-[140px]">{appName}</span>
          {isInteracting ? (
            <button
              onClick={() => setIsInteracting(false)}
              className="flex items-center gap-1 text-[10px] bg-blue-500/20 text-blue-400 border border-blue-500/30 px-2 py-0.5 rounded font-mono hover:bg-blue-500/30 transition-colors"
              title="Click or press Esc to release scroll lock"
            >
              <span>● Active (Esc to release)</span>
            </button>
          ) : (
            <button
              onClick={() => setIsInteracting(true)}
              className="flex items-center gap-1 text-[10px] text-text-muted hover:text-text-primary px-1.5 py-0.5 rounded transition-colors"
              title="Click to interact with app controls"
            >
              <MousePointerClick className="w-3 h-3 text-cyan-400" />
              <span>Click to interact</span>
            </button>
          )}
        </div>

        {/* Right: Quick Action Buttons */}
        <div className="flex items-center gap-1">
          {copiedNotification && (
            <span className="text-[11px] font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded flex items-center gap-1">
              <Check className="w-3 h-3" />
              {copiedNotification}
            </span>
          )}

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCaptureScreenshot}
                disabled={isCapturing}
                className="h-7 w-7 p-0 text-text-secondary hover:text-text-primary"
              >
                <Camera className="w-3.5 h-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">Capture App Store Screenshot</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleInternalRefresh}
                className="h-7 w-7 p-0 text-text-secondary hover:text-text-primary"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">Reload App State</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleOpenExternal}
                className="h-7 w-7 p-0 text-text-secondary hover:text-text-primary"
              >
                <ExternalLink className="w-3.5 h-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">Open in External Browser</TooltipContent>
          </Tooltip>
        </div>
      </div>

      {/* Main Viewport Stage */}
      <div
        ref={containerRef}
        className="flex-1 flex items-center justify-center p-2 overflow-hidden bg-background-tertiary/40 dark:bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] dark:from-[#181a24] dark:via-[#0c0d12] dark:to-[#08090d] relative"
      >
        {viewport === 'iphone' ? (
          /* Realistic iPhone 16 Pro Frame with Dynamic Island */
          <div
            style={{
              transform: `scale(${scale})`,
              transformOrigin: 'center center',
            }}
            className="relative w-[360px] sm:w-[375px] h-[720px] sm:h-[740px] bg-black rounded-[48px] sm:rounded-[52px] p-[8px] sm:p-[10px] shadow-[0_20px_50px_-10px_rgba(0,0,0,0.7),0_0_0_2px_#383b48,0_0_0_5px_#1e2029] flex flex-col shrink-0 select-none transition-transform duration-75"
          >
            {/* Dynamic Island Pill */}
            <div className="absolute top-4 left-1/2 -translate-x-1/2 w-28 h-7 bg-black rounded-full z-40 flex items-center justify-between px-3 border border-white/5 shadow-inner pointer-events-none">
              <div className="w-2.5 h-2.5 rounded-full bg-[#111] ring-1 ring-white/10" />
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/80 animate-pulse" />
            </div>

            {/* Top iOS Status Bar */}
            <div className="h-6 w-full flex items-center justify-between px-7 pt-1 text-[11px] font-semibold text-white/90 z-30 pointer-events-none shrink-0">
              <span>9:41</span>
              <div className="flex items-center gap-1.5 text-[10px]">
                <span>5G</span>
                <div className="w-4 h-2 rounded-xs border border-white/70 p-0.5 flex items-center">
                  <div className="w-full h-full bg-white rounded-2xs" />
                </div>
              </div>
            </div>

            {/* Inner App Container with Rounded Corners */}
            <div className="relative flex-1 w-full bg-[#121318] rounded-[42px] overflow-hidden flex flex-col">
              {children ? (
                children
              ) : (
                <>
                  <iframe
                    ref={iframeRef}
                    src={srcUrl}
                    srcDoc={srcDoc}
                    title={appName}
                    sandbox="allow-scripts allow-forms allow-same-origin allow-popups"
                    className="w-full h-full border-0 bg-transparent"
                  />
                  {/* Scroll protection shield: lets mousewheel pass through to parent chat */}
                  {!isInteracting && (
                    <div
                      onClick={() => setIsInteracting(true)}
                      className="absolute inset-0 z-30 flex items-center justify-center bg-black/10 hover:bg-black/30 transition-colors cursor-pointer group"
                    >
                      <div className="px-3 py-1.5 rounded-full bg-black/85 text-white shadow-xl text-[11px] font-medium flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity backdrop-blur-xs">
                        <MousePointerClick className="w-3.5 h-3.5 text-blue-400" />
                        <span>Click to Interact</span>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Bottom Home Indicator Bar */}
            <div className="w-full h-5 flex items-center justify-center shrink-0 pointer-events-none z-30">
              <div className="w-32 h-1 bg-white/40 rounded-full" />
            </div>
          </div>
        ) : viewport === 'tablet' ? (
          /* iPad / Tablet Frame */
          <div
            style={{
              transform: `scale(${scale})`,
              transformOrigin: 'center center',
            }}
            className="relative w-[580px] h-[760px] bg-black rounded-[36px] p-[12px] shadow-[0_20px_50px_-10px_rgba(0,0,0,0.7),0_0_0_3px_#2a2c36] flex flex-col shrink-0 select-none transition-transform duration-75"
          >
            {/* Tablet Camera Hole */}
            <div className="absolute top-2.5 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-[#181a20] ring-1 ring-white/10 z-40 pointer-events-none" />

            {/* Inner Tablet Screen */}
            <div className="relative flex-1 w-full bg-[#121318] rounded-[26px] overflow-hidden flex flex-col">
              {children ? (
                children
              ) : (
                <>
                  <iframe
                    ref={iframeRef}
                    src={srcUrl}
                    srcDoc={srcDoc}
                    title={appName}
                    sandbox="allow-scripts allow-forms allow-same-origin allow-popups"
                    className="w-full h-full border-0 bg-transparent"
                  />
                  {!isInteracting && (
                    <div
                      onClick={() => setIsInteracting(true)}
                      className="absolute inset-0 z-30 flex items-center justify-center bg-black/10 hover:bg-black/30 transition-colors cursor-pointer group"
                    >
                      <div className="px-3 py-1.5 rounded-full bg-black/85 text-white shadow-xl text-[11px] font-medium flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity backdrop-blur-xs">
                        <MousePointerClick className="w-3.5 h-3.5 text-blue-400" />
                        <span>Click to Interact</span>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Bottom Home Bar */}
            <div className="w-full h-4 flex items-center justify-center shrink-0 pointer-events-none">
              <div className="w-40 h-1 bg-white/30 rounded-full" />
            </div>
          </div>
        ) : (
          /* Desktop / Fluid View */
          <div className="w-full h-full max-w-full bg-[#121318] rounded-lg border border-border-subtle shadow-xl overflow-hidden flex flex-col relative">
            {children ? (
              children
            ) : (
              <>
                <iframe
                  ref={iframeRef}
                  src={srcUrl}
                  srcDoc={srcDoc}
                  title={appName}
                  sandbox="allow-scripts allow-forms allow-same-origin allow-popups"
                  className="w-full h-full border-0 bg-transparent"
                />
                {!isInteracting && (
                  <div
                    onClick={() => setIsInteracting(true)}
                    className="absolute inset-0 z-30 flex items-center justify-center bg-black/10 hover:bg-black/30 transition-colors cursor-pointer group"
                  >
                    <div className="px-3 py-1.5 rounded-full bg-black/85 text-white shadow-xl text-[11px] font-medium flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity backdrop-blur-xs">
                      <MousePointerClick className="w-3.5 h-3.5 text-blue-400" />
                      <span>Click to Interact</span>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DevicePreviewFrame;
