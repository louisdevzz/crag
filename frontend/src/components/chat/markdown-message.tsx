"use client";

import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ClaimItem, EvidenceItem } from "@/lib/types";
import { CitationBadge } from "./citation-badge";
import { cn } from "@/lib/utils";

interface MarkdownMessageProps {
  content: string;
  evidence?: EvidenceItem[];
  claims?: ClaimItem[];
  isStreaming?: boolean;
  className?: string;
}

export const MarkdownMessage: React.FC<MarkdownMessageProps> = ({
  content,
  evidence = [],
  claims = [],
  isStreaming = false,
  className,
}) => {
  // Build a lookup record from identifiers (DOC_..., E1, strip_id) to the 1-based index and EvidenceItem
  const { idToRef, numToEvidence } = useMemo(() => {
    const idMap: Record<string, { index: number; evidence?: EvidenceItem }> = {};
    const numMap: Record<number, EvidenceItem> = {};

    evidence.forEach((item, idx) => {
      const refNum = idx + 1;
      numMap[refNum] = item;

      // Map strip_id
      if (item.strip_id) {
        idMap[item.strip_id.toLowerCase()] = { index: refNum, evidence: item };
      }
      // Map evidence_id
      if (item.evidence_id) {
        idMap[item.evidence_id.toLowerCase()] = { index: refNum, evidence: item };
      }
      // Map document_id
      if (item.document_id) {
        idMap[item.document_id.toLowerCase()] = { index: refNum, evidence: item };
      }
      // Map document_number
      if (item.document_number) {
        idMap[item.document_number.toLowerCase()] = { index: refNum, evidence: item };
      }
      // Common shorthand E1, E2...
      idMap[`e${refNum}`] = { index: refNum, evidence: item };
    });

    return { idToRef: idMap, numToEvidence: numMap };
  }, [evidence]);

  // Pre-process content: if content does not have any bracketed citations [1], [E1], [DOC_...],
  // but evidence exists, attach citations to the key statements/claims
  const processedContent = useMemo(() => {
    if (!content) return "";
    if (evidence.length === 0) return content;

    const hasBracketCitation = /\[([A-Za-z0-9_\-]+)\]/.test(content);
    if (hasBracketCitation) {
      return content;
    }

    // If claims are available, try to match claim sentences
    let modified = content;
    let injected = false;

    if (claims && claims.length > 0) {
      claims.forEach((claim, idx) => {
        const claimText = (claim.text || "").trim();
        if (!claimText) return;

        // Try exact match or substring
        const pos = modified.indexOf(claimText);
        if (pos !== -1) {
          const refIndex = idx + 1 <= evidence.length ? idx + 1 : 1;
          const endPos = pos + claimText.length;
          modified = modified.slice(0, endPos) + ` [${refIndex}]` + modified.slice(endPos);
          injected = true;
        }
      });
    }

    // If no claims matched, or no claims provided, attach to law mentions e.g. "Điều ...", or end of first sentence
    if (!injected && evidence.length > 0) {
      // Find statutory mention or first period
      const lawMentionRegex = /(Điều\s+\d+[^,.;:]*|Khoản\s+\d+[^,.;:]*|Bộ luật[^,.;:]*|Luật[^,.;:]*)/i;
      const match = lawMentionRegex.exec(modified);
      if (match) {
        const insertAt = match.index + match[0].length;
        modified = modified.slice(0, insertAt) + " [1]" + modified.slice(insertAt);
      } else {
        const firstSentenceEnd = modified.indexOf(".");
        if (firstSentenceEnd !== -1) {
          modified = modified.slice(0, firstSentenceEnd) + " [1]" + modified.slice(firstSentenceEnd);
        } else {
          modified = modified + " [1]";
        }
      }
    }

    return modified;
  }, [content, evidence, claims]);

  // Function to replace raw citation brackets [DOC_...], [E1], [1] with interactive CitationBadge
  const renderTextWithCitations = (text: string): React.ReactNode => {
    if (!text) return null;

    // Matches [1], [2], [E1], [DOC_2ec2302442c9], etc.
    const citationRegex = /\[([A-Za-z0-9_\-]+)\]/g;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = citationRegex.exec(text)) !== null) {
      const fullMatch = match[0];
      const idOrNum = match[1];
      const matchStart = match.index;

      // Push prior text
      if (matchStart > lastIndex) {
        parts.push(text.slice(lastIndex, matchStart));
      }

      // Check if it is a pure number: e.g. [1], [2]
      const parsedNum = parseInt(idOrNum, 10);
      if (!Number.isNaN(parsedNum) && String(parsedNum) === idOrNum) {
        const item = numToEvidence[parsedNum] || evidence[parsedNum - 1];
        parts.push(
          <CitationBadge
            key={`cit-${matchStart}-${parsedNum}`}
            index={parsedNum}
            evidence={item}
            sourceId={`REF_${parsedNum}`}
          />
        );
      } else {
        // It is an identifier like [DOC_...] or [E1]
        const matched = idToRef[idOrNum.toLowerCase()];
        if (matched) {
          parts.push(
            <CitationBadge
              key={`cit-${matchStart}-${idOrNum}`}
              index={matched.index}
              evidence={matched.evidence}
              sourceId={idOrNum}
            />
          );
        } else {
          // If no direct evidence mapping found, check if it looks like a source id
          if (idOrNum.startsWith("DOC_") || idOrNum.startsWith("E") || idOrNum.startsWith("strip_")) {
            const fallbackIndex = parts.length + 1;
            parts.push(
              <CitationBadge
                key={`cit-${matchStart}-${idOrNum}`}
                index={fallbackIndex}
                sourceId={idOrNum}
              />
            );
          } else {
            // Leave unchanged (e.g. [options], [text])
            parts.push(fullMatch);
          }
        }
      }

      lastIndex = matchStart + fullMatch.length;
    }

    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex));
    }

    return parts.length > 0 ? parts : text;
  };

  return (
    <div className={cn("prose prose-neutral dark:prose-invert max-w-none text-sm leading-relaxed", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => {
            const processedChildren = React.Children.map(children, (child) => {
              if (typeof child === "string") {
                return renderTextWithCitations(child);
              }
              return child;
            });
            return <p className="mb-3 last:mb-0 leading-relaxed text-foreground">{processedChildren}</p>;
          },
          li: ({ children }) => {
            const processedChildren = React.Children.map(children, (child) => {
              if (typeof child === "string") {
                return renderTextWithCitations(child);
              }
              return child;
            });
            return <li className="leading-relaxed text-foreground">{processedChildren}</li>;
          },
          h1: ({ children }) => (
            <h1 className="text-lg font-bold mt-4 mb-2 text-foreground tracking-tight">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-base font-bold mt-3.5 mb-2 text-foreground tracking-tight">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-semibold mt-2.5 mb-1.5 text-foreground">{children}</h3>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-5 my-2.5 space-y-1 text-foreground">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-5 my-2.5 space-y-1 text-foreground">{children}</ol>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-primary/60 pl-3.5 italic my-2.5 text-muted-foreground bg-muted/20 py-1 rounded-r-md">
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <div className="my-3 w-full overflow-x-auto rounded-lg border border-border">
              <table className="w-full border-collapse text-left text-xs">{children}</table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-muted/80 text-foreground font-semibold border-b border-border">{children}</thead>
          ),
          tbody: ({ children }) => <tbody className="divide-y divide-border/60 bg-card">{children}</tbody>,
          tr: ({ children }) => <tr className="hover:bg-muted/30 transition-colors">{children}</tr>,
          th: ({ children }) => <th className="px-3.5 py-2.5 font-semibold text-foreground">{children}</th>,
          td: ({ children }) => <td className="px-3.5 py-2.5 text-foreground/90">{children}</td>,
          code: ({ className: codeClassName, children, ...props }) => {
            const match = /language-(\w+)/.exec(codeClassName || "");
            const isInline = !match && !String(children).includes("\n");
            return isInline ? (
              <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground" {...props}>
                {children}
              </code>
            ) : (
              <pre className="my-2.5 overflow-x-auto rounded-xl border border-border bg-muted/60 p-3 font-mono text-xs text-foreground">
                <code className={codeClassName} {...props}>
                  {children}
                </code>
              </pre>
            );
          },
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline underline-offset-4 hover:text-primary/80 transition-colors inline-flex items-center gap-0.5"
            >
              {children}
            </a>
          ),
        }}
      >
        {processedContent}
      </ReactMarkdown>

      {isStreaming && (
        <span className="inline-block h-3.5 w-1.5 animate-pulse bg-primary align-middle ml-1" />
      )}
    </div>
  );
};
