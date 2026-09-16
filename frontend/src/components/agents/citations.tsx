"use client";

import React, { ReactNode, useCallback, useId, useState } from "react";
import { BookOpenText, ChevronDown, ExternalLink, Globe, Scale } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { AgentDisclosure } from "@/components/agents/agent-disclosure";
import { EASE_OUT, SPRING_LAYOUT, SPRING_SWAP } from "@/lib/ease";
import { cn } from "@/lib/utils";

export interface CitationItem {
  id: string;
  title: ReactNode;
  domain?: ReactNode;
  url?: string;
  excerpt?: string;
  score?: number;
}

export interface CitationsProps {
  citations: CitationItem[];
  title?: ReactNode;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  idPrefix?: string;
  className?: string;
}

export interface CitationProps {
  citationId: string;
  index: number;
  idPrefix?: string;
  className?: string;
  onClick?: () => void;
}

export interface CitationListProps {
  citations: CitationItem[];
  idPrefix?: string;
  className?: string;
}

export interface CitationStackProps {
  citations: CitationItem[];
  limit?: number;
  className?: string;
}

function citationTargetId(prefix: string, citationId: string) {
  return `${prefix}-${citationId.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

export function Citation({
  citationId,
  index,
  idPrefix = "citation",
  className,
  onClick,
}: CitationProps) {
  return (
    <a
      href={`#${citationTargetId(idPrefix, citationId)}`}
      aria-label={`Xem trích dẫn [${index}]`}
      onClick={onClick}
      className={cn(
        "mx-0.5 inline-flex min-w-4 -translate-y-0.5 items-center justify-center rounded-md bg-primary/10 px-1 py-0.5 text-[10px] font-semibold leading-none text-primary no-underline outline-none transition-colors hover:bg-primary/20 hover:text-primary focus-visible:ring-1 focus-visible:ring-ring select-none",
        className
      )}
    >
      [{index}]
    </a>
  );
}

export function CitationStack({
  citations,
  limit = 3,
  className,
}: CitationStackProps) {
  return (
    <span aria-hidden="true" className={cn("flex -space-x-1.5 items-center", className)}>
      {citations.slice(0, limit).map((citation, i) => {
        const isWeb = citation.url || citation.domain;
        return (
          <span
            key={citation.id || i}
            className="flex size-5 items-center justify-center rounded-full bg-muted border border-border text-muted-foreground shadow-2xs"
          >
            {isWeb ? <Globe className="size-3 text-blue-500" /> : <Scale className="size-3 text-primary" />}
          </span>
        );
      })}
    </span>
  );
}

function CitationRow({
  citation,
  index,
  idPrefix,
}: {
  citation: CitationItem;
  index: number;
  idPrefix: string;
}) {
  const isWeb = Boolean(citation.url || citation.domain);
  const id = citationTargetId(idPrefix, citation.id);

  const inner = (
    <>
      <span className="flex size-5 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
        {isWeb ? <Globe className="size-3 text-blue-500" /> : <Scale className="size-3 text-primary" />}
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="flex items-center gap-2">
          <span className="truncate text-xs font-semibold text-foreground/90 group-hover/citation:text-primary transition-colors">
            {citation.title}
          </span>
          {citation.score != null && (
            <span className="text-[10px] font-medium text-emerald-600 bg-emerald-500/10 px-1 rounded">
              {Math.round(citation.score * 100)}%
            </span>
          )}
        </span>
        {citation.domain && (
          <span className="truncate text-[10px] text-muted-foreground/70">
            {citation.domain}
          </span>
        )}
        {citation.excerpt && (
          <span className="text-[11px] text-muted-foreground line-clamp-1 mt-0.5">
            &ldquo;{citation.excerpt}&rdquo;
          </span>
        )}
      </span>
      <span className="flex shrink-0 items-center gap-1.5 ml-1">
        <span className="grid size-5 place-items-center rounded-md bg-foreground/[0.05] text-[10px] font-semibold tabular-nums text-muted-foreground">
          {index}
        </span>
        {citation.url ? (
          <ExternalLink className="size-3 text-muted-foreground/40 transition-colors group-hover/citation:text-muted-foreground" />
        ) : null}
      </span>
    </>
  );

  const rowClass =
    "group/citation flex items-center gap-2.5 rounded-lg border border-border/50 bg-card/60 p-2 text-left outline-none hover:bg-muted/40 transition-colors focus-visible:ring-1 focus-visible:ring-ring";

  return citation.url ? (
    <a id={id} href={citation.url} target="_blank" rel="noreferrer noopener" className={rowClass}>
      {inner}
    </a>
  ) : (
    <div id={id} className={rowClass}>
      {inner}
    </div>
  );
}

export function CitationList({
  citations,
  idPrefix,
  className,
}: CitationListProps) {
  const reduce = useReducedMotion() ?? false;
  const baseId = useId();
  const resolvedPrefix = idPrefix ?? `citation-list-${baseId.replace(/:/g, "")}`;

  return (
    <div className={cn("grid gap-1.5", className)}>
      <AnimatePresence mode="popLayout">
        {citations.map((citation, index) => (
          <motion.div
            layout="position"
            key={citation.id}
            initial={reduce ? { opacity: 1 } : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, y: -3 }}
            transition={
              reduce
                ? { duration: 0 }
                : {
                    opacity: { duration: 0.18, ease: EASE_OUT },
                    y: SPRING_LAYOUT,
                    layout: SPRING_LAYOUT,
                  }
            }
          >
            <CitationRow citation={citation} index={index + 1} idPrefix={resolvedPrefix} />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

export function Citations({
  citations,
  title = "Căn cứ & Nguồn trích dẫn",
  open,
  defaultOpen = false,
  onOpenChange,
  idPrefix,
  className,
}: CitationsProps) {
  const reduce = useReducedMotion() ?? false;
  const baseId = useId();
  const contentId = `${baseId}-content`;
  const resolvedPrefix = idPrefix ?? `citation-${baseId.replace(/:/g, "")}`;
  const [internalOpen, setInternalOpen] = useState(defaultOpen);
  const currentOpen = open ?? internalOpen;
  const setOpen = useCallback(
    (next: boolean) => {
      if (open === undefined) setInternalOpen(next);
      onOpenChange?.(next);
    },
    [onOpenChange, open]
  );

  if (citations.length === 0) return null;

  return (
    <div className={cn("w-full text-xs mt-3 pt-2 border-t border-border/60", className)}>
      <button
        type="button"
        aria-expanded={currentOpen}
        aria-controls={contentId}
        onClick={() => setOpen(!currentOpen)}
        className="group flex min-h-7 items-center gap-2 rounded-lg px-1.5 py-1 text-left text-muted-foreground outline-none transition-colors hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring cursor-pointer"
      >
        <BookOpenText className="size-3.5 text-primary" />
        <span className="font-semibold">{title}</span>
        <span className="rounded-full bg-muted px-1.5 py-0.2 text-[10px] font-semibold tabular-nums">
          {citations.length}
        </span>
        <motion.span
          aria-hidden="true"
          animate={{ rotate: currentOpen ? 180 : 0 }}
          transition={reduce ? { duration: 0 } : SPRING_SWAP}
          className="text-muted-foreground/60 group-hover:text-foreground"
        >
          <ChevronDown className="size-3" />
        </motion.span>
      </button>

      <AgentDisclosure id={contentId} open={currentOpen}>
        <CitationList citations={citations} idPrefix={resolvedPrefix} className="mt-2" />
      </AgentDisclosure>
    </div>
  );
}
