"use client";

import React, { useState } from "react";
import { ChevronDown, ExternalLink, Globe, Scale } from "lucide-react";
import { EvidenceItem } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

interface SourceReferencesProps {
  evidence: EvidenceItem[];
  citationMap?: Map<string, number>;
  className?: string;
}

export const SourceReferences: React.FC<SourceReferencesProps> = ({
  evidence,
  className,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!evidence || evidence.length === 0) {
    return null;
  }

  // Deduplicate sources by document title / number or strip id
  const uniqueEvidence: { item: EvidenceItem; refNum: number }[] = [];
  const seenKeys = new Set<string>();

  evidence.forEach((item, i) => {
    const key = item.strip_id || item.evidence_id || `${item.document_number}_${item.heading}` || `item_${i}`;
    if (!seenKeys.has(key)) {
      seenKeys.add(key);
      uniqueEvidence.push({ item, refNum: uniqueEvidence.length + 1 });
    }
  });

  if (uniqueEvidence.length === 0) return null;

  return (
    <div className={cn("mt-4 border-t border-border/70 pt-3", className)}>
      <div className="flex items-center justify-between gap-2 mb-2.5">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground/80">
          <Scale className="h-3.5 w-3.5 text-primary" />
          <span>Căn cứ & Nguồn trích dẫn ({uniqueEvidence.length})</span>
        </div>
        {uniqueEvidence.length > 3 && (
          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
          >
            <span>{isExpanded ? "Thu gọn" : `Xem tất cả ${uniqueEvidence.length} nguồn`}</span>
            <ChevronDown className={cn("h-3 w-3 transition-transform", isExpanded && "rotate-180")} />
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {(isExpanded ? uniqueEvidence : uniqueEvidence.slice(0, 3)).map(({ item, refNum }) => {
          const isWeb = item.retrieval_source === "web" || item.strip_id?.startsWith("WEB_");
          const title = item.document_title || item.document_number || "Văn bản quy phạm pháp luật";
          const heading = item.heading || item.locator;
          const scorePercent = item.score != null ? Math.round(item.score * 100) : null;

          return (
            <Popover key={item.strip_id || refNum}>
              <PopoverTrigger asChild>
                <div
                  role="button"
                  tabIndex={0}
                  className="group relative flex flex-col justify-between rounded-xl border border-border/70 bg-card/60 p-2.5 hover:bg-accent/50 hover:border-border transition-all cursor-pointer text-left"
                >
                  <div className="flex items-start gap-2">
                    <span className="flex-shrink-0 flex h-4 w-4 items-center justify-center rounded bg-primary/10 text-[10px] font-bold text-primary">
                      {refNum}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-medium text-foreground line-clamp-1 group-hover:text-primary transition-colors">
                        {title}
                      </div>
                      {heading && (
                        <div className="text-[11px] text-muted-foreground line-clamp-1 mt-0.5">
                          {heading}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="mt-2 flex items-center justify-between text-[10px] text-muted-foreground pt-1.5 border-t border-border/40">
                    <span className="flex items-center gap-1 truncate max-w-[150px]">
                      {isWeb ? (
                        <>
                          <Globe className="h-2.5 w-2.5 text-blue-500" />
                          <span>Cổng thông tin</span>
                        </>
                      ) : (
                        <>
                          <Scale className="h-2.5 w-2.5 text-primary" />
                          <span>Kho văn bản nội bộ</span>
                        </>
                      )}
                    </span>
                    {scorePercent != null && (
                      <span className="font-medium text-emerald-600 dark:text-emerald-400">
                        {scorePercent}%
                      </span>
                    )}
                  </div>
                </div>
              </PopoverTrigger>
              <PopoverContent
                align="center"
                side="top"
                sideOffset={6}
                className="z-50 w-80 sm:w-96 rounded-xl border border-border bg-popover p-3.5 text-popover-foreground shadow-lg backdrop-blur-sm"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-primary">
                      {isWeb ? <Globe className="h-3.5 w-3.5" /> : <Scale className="h-3.5 w-3.5" />}
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-bold text-foreground">
                        [{refNum}] {title}
                      </div>
                      <div className="text-[10px] text-muted-foreground">
                        {isWeb ? "Cổng thông tin pháp luật chính thống" : "Kho tri thức văn bản QPPL"}
                      </div>
                    </div>
                  </div>
                  {scorePercent != null && (
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                      {scorePercent}% phù hợp
                    </span>
                  )}
                </div>

                {heading && (
                  <div className="mt-2.5 rounded-md bg-muted/60 px-2 py-1 text-[11px] font-medium text-foreground/90">
                    📌 {heading}
                  </div>
                )}

                {item.text && (
                  <div className="mt-2 max-h-40 overflow-y-auto rounded-lg border border-border/60 bg-muted/30 p-2.5 text-xs leading-relaxed text-muted-foreground">
                    &ldquo;{item.text}&rdquo;
                  </div>
                )}

                <div className="mt-2.5 flex items-center justify-between border-t border-border/60 pt-2 text-[10px] text-muted-foreground">
                  <span>Mã trích dẫn: {item.strip_id || item.evidence_id || `REF_${refNum}`}</span>
                </div>
              </PopoverContent>
            </Popover>
          );
        })}
      </div>
    </div>
  );
};
