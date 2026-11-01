import React, { useState, useEffect, useRef, memo, useMemo, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
// Improved oneDark theme for better comment contrast and readability
const customOneDarkTheme = {
  ...oneDark,
  'code[class*="language-"]': {
    ...oneDark['code[class*="language-"]'],
    color: '#e6e6e6',
    fontSize: '14px',
  },
  'pre[class*="language-"]': {
    ...oneDark['pre[class*="language-"]'],
    color: '#e6e6e6',
    fontSize: '14px',
  },
  comment: { ...oneDark.comment, color: '#a0a0a0', fontStyle: 'italic' },
  prolog: { ...oneDark.prolog, color: '#a0a0a0' },
  doctype: { ...oneDark.doctype, color: '#a0a0a0' },
  cdata: { ...oneDark.cdata, color: '#a0a0a0' },
};

import { Check, Copy } from './icons';
import { Smartphone, Columns, X, Maximize2, Minimize2, PanelRight } from 'lucide-react';
import { DevicePreviewFrame } from './McpApps/DevicePreviewFrame';
import { wrapHTMLInCodeBlock } from '../utils/htmlSecurity';
import { BLOCKED_PROTOCOLS } from '../utils/urlSecurity';
import { getTextDirection } from '../utils/textDirection';
import { defineMessages, useIntl } from '../i18n';

const i18n = defineMessages({
  copyCode: {
    id: 'markdownContent.copyCode',
    defaultMessage: 'Copy code',
  },
  failedToOpenLink: {
    id: 'markdownContent.failedToOpenLink',
    defaultMessage: 'Failed to Open Link',
  },
  noApplicationFound: {
    id: 'markdownContent.noApplicationFound',
    defaultMessage: 'No application found to open this link.',
  },
});

interface CodeProps extends React.ClassAttributes<HTMLElement>, React.HTMLAttributes<HTMLElement> {
  inline?: boolean;
}

interface MarkdownContentProps {
  content: string;
  className?: string;
}

// Minimal hast node shape; avoids importing @types/hast just for this plugin.
interface HastNode {
  type?: string;
  tagName?: string;
  value?: string;
  properties?: Record<string, unknown> | null;
  children?: HastNode[];
}

// Block-level elements that get their own computed dir so mixed-direction
// markdown (e.g. an English paragraph inside an Arabic message) resolves
// punctuation placement per block instead of inheriting the message direction.
const DIRECTIONAL_BLOCK_TAGS = new Set([
  'p',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'li',
  'blockquote',
  'dd',
  'dt',
  'td',
  'th',
  'figcaption',
  'caption',
  'summary',
]);

function collectText(node: HastNode): string {
  // Code and KaTeX output are language-neutral (both render LTR internally),
  // so they don't vote on the direction of the prose block containing them.
  if (node.type === 'element') {
    if (node.tagName === 'code' || node.tagName === 'pre') return '';
    const classNames = node.properties?.className;
    if (Array.isArray(classNames) && classNames.includes('katex')) return '';
  }
  let text = node.type === 'text' ? (node.value ?? '') : '';
  for (const child of node.children ?? []) {
    // Nested blocks other than paragraphs compute their own direction and
    // don't vote on the parent, so a long sublist can't flip the list item
    // containing it. Prose <p> children still count: loose list items and
    // blockquotes hold their own text in direct <p> children, and their
    // marker/indent side follows the parent's own direction.
    if (
      child.type === 'element' &&
      child.tagName &&
      child.tagName !== 'p' &&
      DIRECTIONAL_BLOCK_TAGS.has(child.tagName)
    ) {
      continue;
    }
    text += collectText(child);
  }
  return text;
}

function applyPerBlockDirection(node: HastNode): void {
  if (node.type === 'element' && node.tagName && DIRECTIONAL_BLOCK_TAGS.has(node.tagName)) {
    const direction = getTextDirection(collectText(node));
    if (direction) {
      node.properties = { ...node.properties, dir: direction };
    }
  }
  for (const child of node.children ?? []) {
    applyPerBlockDirection(child);
  }
}

function rehypePerBlockDirection(): (tree: HastNode) => void {
  return (tree) => {
    if (tree) applyPerBlockDirection(tree);
  };
}

// Memoized CodeBlock component to prevent re-rendering when props haven't changed
const CodeBlock = memo(function CodeBlock({
  language,
  children,
}: {
  language: string;
  children: string;
}) {
  const intl = useIntl();
  const [copied, setCopied] = useState(false);
  const timeoutRef = useRef<number | null>(null);
  const [showLivePreview, setShowLivePreview] = useState(false);
  const [previewLayout, setPreviewLayout] = useState<'split' | 'preview-only'>('split');
  const [isExpanded, setIsExpanded] = useState(false);

  const handleDockToCompanion = () => {
    window.dispatchEvent(
      new CustomEvent('wolinex:open-companion-preview', {
        detail: {
          srcDoc: children,
          title: 'Wolinex Sovereign App',
        },
      })
    );
  };

  const isRunnableHtml = useMemo(() => {
    const lang = (language || '').toLowerCase();
    if (['html', 'htm', 'xhtml', 'svg'].includes(lang)) return true;
    const content = (children || '').trim();
    if (
      content.startsWith('<!DOCTYPE html>') ||
      content.startsWith('<html') ||
      (content.includes('<html') && content.includes('</html>'))
    ) {
      return true;
    }
    return false;
  }, [language, children]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(children);
      setCopied(true);

      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current);
      }

      timeoutRef.current = window.setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  // Memoize the SyntaxHighlighter component to prevent re-rendering
  // Only re-render if language or children change
  const memoizedSyntaxHighlighter = useMemo(() => {
    // For very large code blocks, consider truncating or lazy loading
    const isLargeCodeBlock = children.length > 10000; // 10KB threshold

    if (isLargeCodeBlock) {
      console.log(`Large code block detected (${children.length} chars), consider optimization`);
    }

    return (
      <SyntaxHighlighter
        style={customOneDarkTheme}
        language={language}
        PreTag="div"
        customStyle={{
          background: 'var(--code-block-background, #282c34)',
          margin: 0,
          width: '100%',
          maxWidth: '100%',
        }}
        codeTagProps={{
          style: {
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
            overflowWrap: 'break-word',
            fontFamily: 'var(--font-mono)',
            fontSize: '14px',
          },
        }}
        // Performance optimizations for SyntaxHighlighter
        showLineNumbers={false} // Disable line numbers for better performance
        wrapLines={false} // Disable line wrapping for better performance
        lineProps={undefined} // Don't add extra props to each line
      >
        {children}
      </SyntaxHighlighter>
    );
  }, [language, children]);

  return (
    <div className="relative group w-full my-2 flex flex-col" dir="ltr">
      {/* Code Header Bar with language badge and live preview launcher */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-background-secondary border-t border-x border-border-subtle rounded-t-lg text-xs">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] uppercase tracking-wider text-text-secondary font-semibold">
            {language || 'code'}
          </span>
          {isRunnableHtml && (
            <span className="flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.2 rounded font-mono">
              <Smartphone className="w-2.5 h-2.5" /> Mobile Ready
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {isRunnableHtml && (
            <div className="flex items-center bg-background-tertiary p-0.5 rounded-md border border-border-subtle gap-0.5">
              <button
                onClick={() => {
                  if (!showLivePreview) {
                    setShowLivePreview(true);
                    setPreviewLayout('split');
                  } else if (previewLayout === 'split') {
                    setShowLivePreview(false);
                  } else {
                    setPreviewLayout('split');
                  }
                }}
                className={`flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                  showLivePreview && previewLayout === 'split'
                    ? 'bg-blue-600 text-white shadow-xs'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
                title="View code and live mobile simulator side by side"
              >
                <Columns className="h-3 w-3" />
                <span>Side by Side</span>
              </button>

              <button
                onClick={() => {
                  setShowLivePreview(true);
                  setPreviewLayout('preview-only');
                }}
                className={`flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                  showLivePreview && previewLayout === 'preview-only'
                    ? 'bg-blue-600 text-white shadow-xs'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
                title="View live device simulator only"
              >
                <Smartphone className="h-3 w-3" />
                <span>Simulator</span>
              </button>

              <button
                onClick={handleDockToCompanion}
                className="flex items-center gap-1 px-2 py-0.5 rounded text-xs text-text-secondary hover:text-blue-400 transition-colors"
                title="Dock simulator to the right side of chat (companion pane)"
              >
                <PanelRight className="h-3 w-3" />
                <span>Dock to Right</span>
              </button>

              {showLivePreview && (
                <button
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="p-1 text-text-secondary hover:text-text-primary text-xs transition-colors"
                  title={isExpanded ? 'Compact height (460px)' : 'Expand height (660px)'}
                >
                  {isExpanded ? <Minimize2 className="h-3 w-3" /> : <Maximize2 className="h-3 w-3" />}
                </button>
              )}

              {showLivePreview && (
                <button
                  onClick={() => setShowLivePreview(false)}
                  className="px-1.5 py-0.5 text-text-secondary hover:text-rose-400 text-xs transition-colors"
                  title="Close simulator and show code only"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          )}

          <button
            onClick={handleCopy}
            className="flex items-center gap-1 px-2 py-0.5 rounded bg-background-tertiary hover:bg-background-secondary border border-border-subtle text-text-secondary hover:text-text-primary font-sans text-xs transition-colors"
            title={intl.formatMessage(i18n.copyCode)}
          >
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
            <span className="text-[11px]">{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>
      </div>

      {/* Code syntax & Live Simulator area */}
      {showLivePreview && isRunnableHtml ? (
        previewLayout === 'split' ? (
          /* Side-by-Side Split View: Code on Left (50%) + Live Mobile Simulator on Right (50%) */
          <div
            className={`w-full ${
              isExpanded ? 'h-[660px]' : 'h-[460px]'
            } flex flex-col md:flex-row border-x border-b border-border-subtle rounded-b-lg overflow-hidden bg-background-primary shadow-xl transition-all duration-150`}
          >
            {/* Left Column (50%): Code Syntax with internal scroll */}
            <div className="w-full md:w-1/2 h-full overflow-auto border-b md:border-b-0 md:border-r border-border-subtle bg-[var(--code-block-background,#282c34)]">
              {memoizedSyntaxHighlighter}
            </div>

            {/* Right Column (50%): Live Device Simulator Frame right at the top */}
            <div className="w-full md:w-1/2 h-full overflow-hidden flex flex-col bg-background-primary dark:bg-[#0c0d12]">
              <DevicePreviewFrame srcDoc={children} appName="Wolinex Sovereign App" />
            </div>
          </div>
        ) : (
          /* Full Simulator View */
          <div
            className={`w-full ${
              isExpanded ? 'h-[660px]' : 'h-[460px]'
            } border-x border-b border-border-subtle rounded-b-lg overflow-hidden bg-background-primary shadow-xl transition-all duration-150`}
          >
            <DevicePreviewFrame srcDoc={children} appName="Wolinex Sovereign App" />
          </div>
        )
      ) : (
        /* Normal Code View */
        <div className="w-full overflow-x-auto border-x border-b rounded-b-lg border-border-subtle">
          {memoizedSyntaxHighlighter}
        </div>
      )}
    </div>
  );
});

const MarkdownCode = memo(
  React.forwardRef(function MarkdownCode(
    { inline, className, children, ...props }: CodeProps,
    ref: React.Ref<HTMLElement>
  ) {
    const match = /language-(\w+)/.exec(className || '');
    const codeContent = String(children ?? '');

    // react-markdown gives untagged fenced blocks no language-xxx className,
    // so they look like inline code here. Block-level content always ends with
    // a trailing newline, which inline code spans can never contain.
    const isBlockLevelCode = !inline && codeContent.endsWith('\n');

    return isBlockLevelCode ? (
      <CodeBlock language={match ? match[1] : 'text'}>{codeContent.replace(/\n$/, '')}</CodeBlock>
    ) : (
      <code
        ref={ref}
        {...props}
        dir="ltr"
        className="break-all bg-inline-code whitespace-pre-wrap font-mono"
      >
        {children}
      </code>
    );
  })
);

// Custom URL transform to preserve deep link URLs (spotify:, vscode:, slack:, etc.)
// React-markdown's default only allows http/https/mailto and strips all other protocols
// We allow all protocols except dangerous ones (javascript:, data:, file:, etc.)
const customUrlTransform = (url: string): string => {
  try {
    const protocol = new URL(url).protocol;
    if (BLOCKED_PROTOCOLS.includes(protocol)) {
      return '';
    }
  } catch {
    // Not a valid URL, allow it (could be relative path)
  }
  return url;
};

const MarkdownContent = memo(function MarkdownContent({
  content,
  className = '',
}: MarkdownContentProps) {
  const intl = useIntl();
  const processedContent = useMemo(() => {
    try {
      return wrapHTMLInCodeBlock(content);
    } catch (error) {
      console.error('Error processing content:', error);
      return content;
    }
  }, [content]);

  const handleOpenExternal = useCallback(
    async (href: string) => {
      try {
        await window.electron.openExternal(href);
      } catch {
        await window.electron.showMessageBox({
          type: 'error',
          buttons: ['OK'],
          title: intl.formatMessage(i18n.failedToOpenLink),
          message: intl.formatMessage(i18n.noApplicationFound),
          detail: href,
        });
      }
    },
    [intl]
  );

  return (
    <div
      className={`w-full overflow-x-hidden prose prose-sm text-start text-text-primary dark:prose-invert max-w-full word-break font-sans
        prose-pre:p-0 prose-pre:m-0 !p-0
        prose-code:break-all prose-code:whitespace-pre-wrap prose-code:font-mono
        prose-a:break-all prose-a:overflow-wrap-anywhere
        prose-table:table prose-table:w-full
        prose-blockquote:text-inherit
        prose-td:border prose-td:border-border-primary prose-td:p-2
        prose-th:border prose-th:border-border-primary prose-th:p-2
        prose-thead:bg-background-primary
        prose-h1:text-2xl prose-h1:font-normal prose-h1:mb-5 prose-h1:mt-0 prose-h1:font-sans
        prose-h2:text-xl prose-h2:font-normal prose-h2:mb-4 prose-h2:mt-4 prose-h2:font-sans
        prose-h3:text-lg prose-h3:font-normal prose-h3:mb-3 prose-h3:mt-3 prose-h3:font-sans
        prose-p:mt-0 prose-p:mb-2 prose-p:font-sans
        prose-ol:my-2 prose-ol:font-sans
        prose-ul:mt-0 prose-ul:mb-3 prose-ul:font-sans
        prose-li:m-0 prose-li:font-sans ${className}`}
    >
      <ReactMarkdown
        urlTransform={customUrlTransform}
        remarkPlugins={[remarkGfm, remarkBreaks, [remarkMath, { singleDollarTextMath: false }]]}
        rehypePlugins={[
          [
            rehypeKatex,
            {
              throwOnError: false,
              errorColor: '#cc0000',
              strict: false,
            },
          ],
          rehypePerBlockDirection,
        ]}
        components={{
          a: (props) => {
            return (
              <a
                {...props}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  if (!props.href) return;

                  void handleOpenExternal(props.href);
                }}
              />
            );
          },
          code: MarkdownCode,
        }}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
});

export default MarkdownContent;
