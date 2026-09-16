"use client";

import React, {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Button } from "./atoms/Button";
import { Shimmer } from "./atoms/Shimmer";
import { StreamText } from "./atoms/StreamText";

/* ─────────────────────────────────────────────────────────
 * SELECTION ACTIONS
 * A contextual AI bar attached beneath selected text.
 * Allows highlighting any legal passage and asking the agent to:
 * - Giải thích (Explain)
 * - Cải thiện / Viết lại (Rewrite / Improve)
 * - Rút gọn (Shorten)
 * - Thay đổi văn phong (Change tone)
 * - Gửi vào khung chat (Hand to agent composer)
 * ───────────────────────────────────────────────────────── */

export type SelectionText = {
  lead?: string;
  original: string;
  rewrite?: string;
};

export type SelectionAction = {
  id: string;
  label: string;
  icon: ReactNode;
  action?: string;
  busyLabel?: string;
};

export type SelectionActionsLabels = {
  keep: string;
  discard: string;
  placeholder: string;
};

const DEFAULT_LABELS: SelectionActionsLabels = {
  keep: "Áp dụng",
  discard: "Hủy",
  placeholder: "Mô tả yêu cầu viết lại...",
};

type Mode = "idle" | "thinking" | "streaming" | "result";

const icons = {
  explain: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  ),
  improve: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
      <path d="m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5L12 2Z" />
    </svg>
  ),
  shorten: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="6" cy="6" r="3" />
      <circle cx="6" cy="18" r="3" />
      <line x1="20" y1="4" x2="8.12" y2="15.88" />
      <line x1="14.47" y1="14.48" x2="20" y2="20" />
      <line x1="8.12" y1="8.12" x2="12" y2="12" />
    </svg>
  ),
  tone: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M8 14s1.5 2 4 2 4-2 4-2" />
      <line x1="9" y1="9" x2="9.01" y2="9" />
      <line x1="15" y1="9" x2="15.01" y2="9" />
    </svg>
  ),
  send: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 19V5M5 12l7-7 7 7" />
    </svg>
  ),
  check: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6L9 17l-5-5" />
    </svg>
  ),
  close: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  ),
  retry: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l6.73-6.19" />
    </svg>
  ),
};

export interface SelectionActionsProps {
  text?: SelectionText;
  labels?: Partial<SelectionActionsLabels>;
  onAction?: (actionId: string, originalText: string) => void;
  onApplyRewrite?: (newText: string) => void;
  onDismiss?: () => void;
  children?: ReactNode;
  className?: string;
}

export default function SelectionActions({
  text: textProp,
  labels,
  onAction,
  onApplyRewrite,
  onDismiss,
  children,
  className = "",
}: SelectionActionsProps) {
  const [selectedText, setSelectedText] = useState(textProp?.original || "");
  const [shown, setShown] = useState(false);
  const [mode, setMode] = useState<Mode>("idle");
  const [actionTitle, setActionTitle] = useState("Cải thiện");
  const [customPrompt, setCustomPrompt] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [streamedResult, setStreamedResult] = useState("");

  const hostRef = useRef<HTMLDivElement>(null);
  const barRef = useRef<HTMLDivElement>(null);
  const [anchor, setAnchor] = useState<{ x: number; y: number } | null>(null);

  const copy = { ...DEFAULT_LABELS, ...labels };

  // Listen to text selection within container
  const handleMouseUp = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.toString().trim()) {
      if (mode === "idle" && !textProp?.original) {
        setShown(false);
        setAnchor(null);
      }
      return;
    }

    const text = sel.toString().trim();
    if (text.length < 3) return;

    setSelectedText(text);

    // Calculate position
    try {
      const range = sel.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      const host = hostRef.current?.getBoundingClientRect();

      if (host) {
        setAnchor({
          x: Math.max(16, Math.min(rect.left - host.left + rect.width / 2, host.width - 200)),
          y: rect.bottom - host.top + 8,
        });
        setShown(true);
      }
    } catch {
      // fallback
    }
  }, [mode, textProp?.original]);

  const runAction = (actionId: string, label: string) => {
    setActionTitle(label);
    if (onAction) {
      onAction(actionId, selectedText);
    }

    // Simulate AI thinking and rewrite
    setMode("thinking");
    setTimeout(() => {
      setMode("streaming");
      let mockRewrite = "";
      if (actionId === "shorten") {
        mockRewrite = `• Tóm lược: ${selectedText.slice(0, 100)}...`;
      } else if (actionId === "explain") {
        mockRewrite = `Nội dung này quy định rõ ràng nghĩa vụ và quyền hạn bắt buộc theo pháp luật hiện hành.`;
      } else {
        mockRewrite = `Theo quy định pháp luật: ${selectedText}`;
      }
      setStreamedResult(mockRewrite);
    }, 600);
  };

  const handleApply = () => {
    onApplyRewrite?.(streamedResult);
    setMode("idle");
    setShown(false);
  };

  const handleDismiss = () => {
    setMode("idle");
    setShown(false);
    onDismiss?.();
  };

  return (
    <div
      ref={hostRef}
      onMouseUp={handleMouseUp}
      className={`relative ${className}`}
    >
      {children}

      {/* Floating Action Bar */}
      {shown && anchor && (
        <div
          ref={barRef}
          className="absolute z-40 -translate-x-1/2 rounded-full bg-surface p-1 shadow-overlay border border-line flex items-center gap-1 backdrop-blur-md"
          style={{
            left: `${anchor.x}px`,
            top: `${anchor.y}px`,
            animation: "pop-in 180ms cubic-bezier(0.16,1,0.3,1) both",
          }}
        >
          {mode === "idle" && (
            <>
              <button
                type="button"
                onClick={() => runAction("explain", "Giải thích")}
                className="inline-flex h-7 items-center gap-1.5 rounded-full px-2.5 text-[12px] font-medium text-ink hover:bg-hover transition-colors cursor-pointer"
              >
                {icons.explain}
                <span>Giải thích</span>
              </button>

              <button
                type="button"
                onClick={() => runAction("improve", "Viết lại")}
                className="inline-flex h-7 items-center gap-1.5 rounded-full px-2.5 text-[12px] font-medium text-ink hover:bg-hover transition-colors cursor-pointer"
              >
                {icons.improve}
                <span>Viết lại</span>
              </button>

              <button
                type="button"
                onClick={() => runAction("shorten", "Rút gọn")}
                className="inline-flex h-7 items-center gap-1.5 rounded-full px-2.5 text-[12px] font-medium text-ink hover:bg-hover transition-colors cursor-pointer"
              >
                {icons.shorten}
                <span>Rút gọn</span>
              </button>

              <div className="h-4 w-px bg-line mx-0.5" />

              <button
                type="button"
                onClick={() => {
                  onAction?.("handoff", selectedText);
                  setShown(false);
                }}
                className="inline-flex h-7 items-center gap-1 rounded-full bg-ink px-2.5 text-[12px] font-normal text-canvas shadow-hairline hover:opacity-90 transition-all active:scale-95 cursor-pointer"
                title="Hỏi trợ lý về đoạn này"
              >
                {icons.send}
                <span>Hỏi trợ lý</span>
              </button>
            </>
          )}

          {mode === "thinking" && (
            <div className="flex h-7 items-center gap-2 px-3">
              <Shimmer className="text-[12px] font-medium text-ink">
                Đang xử lý {actionTitle.toLowerCase()}...
              </Shimmer>
            </div>
          )}

          {mode === "streaming" && (
            <div className="flex flex-col gap-2 p-2 max-w-sm">
              <div className="text-[12px] font-medium text-ink-2">
                <StreamText text={streamedResult} onDone={() => setMode("result")} />
              </div>
            </div>
          )}

          {mode === "result" && (
            <div className="flex items-center gap-1.5 px-1.5">
              <span className="text-[12px] text-ink font-medium max-w-xs truncate px-1">
                {streamedResult}
              </span>
              <Button size="xs" variant="primary" onClick={handleApply}>
                {icons.check}
                <span>{copy.keep}</span>
              </Button>
              <Button size="xs" variant="ghost" onClick={handleDismiss}>
                {icons.close}
                <span>{copy.discard}</span>
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
