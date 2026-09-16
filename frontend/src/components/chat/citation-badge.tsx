"use client";

import React, { useState } from "react";
import { BookOpen, ExternalLink, Globe, Scale, Sparkles } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { EvidenceItem } from "@/lib/types";
import { cn } from "@/lib/utils";

interface CitationBadgeProps {
  index: number;
  evidence?: EvidenceItem;
  sourceId?: string;
  className?: string;
}

export const CitationBadge: React.FC<CitationBadgeProps> = ({
  index,
  evidence,
  sourceId,
  className,
}) => {
  const [open, setOpen] = useState(false);

  const isWeb = evidence?.retrieval_source === "web" || evidence?.strip_id?.startsWith("WEB_");
  const docTitle = evidence?.document_title || evidence?.document_number || "Căn cứ pháp luật";
  const heading = evidence?.heading || evidence?.locator;
  const scorePercent = evidence?.score != null ? Math.round(evidence.score * 100) : null;
  const excerpt = evidence?.text;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Trích dẫn [${index}]`}
          className={cn(
            "group inline-flex items-center justify-center align-baseline mx-0.5 px-1.5 py-0.5 rounded text-[11px] font-semibold leading-none cursor-pointer select-none transition-all duration-150",
            "bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20 hover:border-primary/40",
            "focus:outline-none focus:ring-1 focus:ring-primary/40",
            className
          )}
        >
          <span>[{index}]</span>
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        sideOffset={6}
        className="z-50 w-80 sm:w-96 rounded-xl border border-border bg-popover p-3.5 text-popover-foreground shadow-lg backdrop-blur-sm"
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-primary">
              {isWeb ? <Globe className="h-3.5 w-3.5" /> : <Scale className="h-3.5 w-3.5" />}
            </div>
            <div className="min-w-0">
              <div className="text-xs font-bold text-foreground line-clamp-1">
                {docTitle}
              </div>
              <div className="text-[10px] text-muted-foreground">
                {isWeb ? "Cổng thông tin pháp luật chính thống" : "Kho tri thức văn bản QPPL"}
              </div>
            </div>
          </div>
          {scorePercent != null && (
            <span
              className={cn(
                "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium",
                scorePercent >= 80
                  ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
                  : "bg-amber-500/10 text-amber-600 border border-amber-500/20"
              )}
            >
              {scorePercent}% phù hợp
            </span>
          )}
        </div>

        {heading && (
          <div className="mt-2.5 rounded-md bg-muted/60 px-2 py-1 text-[11px] font-medium text-foreground/90">
            📌 {heading}
          </div>
        )}

        {excerpt ? (
          <div className="mt-2 max-h-40 overflow-y-auto rounded-lg border border-border/60 bg-muted/30 p-2.5 text-xs leading-relaxed text-muted-foreground">
            &ldquo;{excerpt}&rdquo;
          </div>
        ) : (
          <div className="mt-2 text-xs italic text-muted-foreground">
            Trích dẫn đã được kiểm định hợp lệ theo nguồn: {sourceId || evidence?.strip_id}
          </div>
        )}

        <div className="mt-2.5 flex items-center justify-between border-t border-border/60 pt-2 text-[10px] text-muted-foreground">
          <span>Mã căn cứ: {evidence?.strip_id || sourceId || `REF_${index}`}</span>
          <span className="font-medium text-primary">Căn cứ trích dẫn #{index}</span>
        </div>
      </PopoverContent>
    </Popover>
  );
};
