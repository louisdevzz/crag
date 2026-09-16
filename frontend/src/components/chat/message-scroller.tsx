"use client";

import React, {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { useReducedMotion } from "motion/react";
import { ArrowDown, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface MessageScrollerProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Keep streamed output pinned while the reader remains near the end. */
  followOutput?: boolean;
  /** Distance in px from the end that still counts as following the output. */
  followThreshold?: number;
  /** Smoothly follow growing content. */
  smooth?: boolean;
  /** Reports when the reader leaves or returns to the live edge. */
  onFollowChange?: (following: boolean) => void;
  /** Accessible label for the scrollable transcript. */
  label?: string;
  /** Marks the transcript as waiting for more streamed content. */
  busy?: boolean;
  /** Show a floating scroll-to-bottom button when scrolled away. */
  showScrollToBottom?: boolean;
  viewportClassName?: string;
  contentClassName?: string;
}

export const MessageScroller: React.FC<MessageScrollerProps> = ({
  followOutput = true,
  followThreshold = 56,
  smooth = true,
  onFollowChange,
  label = "Conversation",
  busy = false,
  showScrollToBottom = true,
  viewportClassName,
  contentClassName,
  className,
  children,
  ...props
}) => {
  const reduce = useReducedMotion() ?? false;
  const viewportRef = useRef<HTMLElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const followingRef = useRef(followOutput);
  const programmaticScrollRef = useRef(false);
  const scrollTimerRef = useRef<number | undefined>(undefined);
  const frameRef = useRef<number | undefined>(undefined);

  const [isFollowing, setIsFollowing] = useState(followOutput);

  const setFollowingState = useCallback(
    (next: boolean) => {
      if (followingRef.current === next) return;
      followingRef.current = next;
      setIsFollowing(next);
      onFollowChange?.(next);
    },
    [onFollowChange]
  );

  const scrollToEnd = useCallback(
    (behavior: ScrollBehavior) => {
      const viewport = viewportRef.current;
      if (!viewport) return;

      programmaticScrollRef.current = true;
      if (typeof viewport.scrollTo === "function") {
        viewport.scrollTo({ top: viewport.scrollHeight, behavior });
      } else {
        viewport.scrollTop = viewport.scrollHeight;
      }

      if (scrollTimerRef.current) window.clearTimeout(scrollTimerRef.current);
      scrollTimerRef.current = window.setTimeout(
        () => {
          programmaticScrollRef.current = false;
        },
        behavior === "smooth" ? 320 : 0
      );
    },
    []
  );

  const handleScroll = useCallback(() => {
    const viewport = viewportRef.current;
    if (!viewport || programmaticScrollRef.current) return;

    const distance =
      viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
    setFollowingState(distance <= followThreshold);
  }, [followThreshold, setFollowingState]);

  const leaveLiveEdge = useCallback(() => {
    programmaticScrollRef.current = false;
    setFollowingState(false);
  }, [setFollowingState]);

  // Initial pin to end on mount
  useLayoutEffect(() => {
    followingRef.current = followOutput;
    if (!followOutput) return;

    frameRef.current = requestAnimationFrame(() => scrollToEnd("auto"));
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [followOutput, scrollToEnd]);

  // Follow growing content via ResizeObserver
  useEffect(() => {
    const content = contentRef.current;
    if (!content || typeof ResizeObserver === "undefined") return;

    const observer = new ResizeObserver(() => {
      if (!followOutput || !followingRef.current) return;
      scrollToEnd(reduce || !smooth ? "auto" : "smooth");
    });
    observer.observe(content);

    return () => observer.disconnect();
  }, [followOutput, reduce, scrollToEnd, smooth]);

  useEffect(
    () => () => {
      if (scrollTimerRef.current) window.clearTimeout(scrollTimerRef.current);
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    },
    []
  );

  const handleJumpToBottom = () => {
    setFollowingState(true);
    scrollToEnd(reduce || !smooth ? "auto" : "smooth");
  };

  return (
    <div
      data-slot="message-scroller"
      className={cn("relative flex-1 min-h-0 w-full overflow-hidden", className)}
      {...props}
    >
      <section
        ref={viewportRef}
        aria-label={label}
        onScroll={handleScroll}
        onWheel={(e) => {
          if (e.deltaY < 0) leaveLiveEdge();
        }}
        onTouchStart={leaveLiveEdge}
        onKeyDown={(e) => {
          if (["ArrowUp", "PageUp", "Home"].includes(e.key)) {
            leaveLiveEdge();
          }
        }}
        className={cn(
          "h-full overflow-y-auto overscroll-contain outline-none [overflow-anchor:none]",
          "focus-visible:ring-1 focus-visible:ring-ring [scrollbar-gutter:stable]",
          viewportClassName
        )}
      >
        <div
          ref={contentRef}
          role="log"
          aria-live="polite"
          aria-relevant="additions text"
          aria-busy={busy}
          className={cn("mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6", contentClassName)}
        >
          {children}
        </div>
      </section>

      {/* Floating jump to bottom button when reader scrolls up */}
      {showScrollToBottom && !isFollowing && (
        <button
          type="button"
          onClick={handleJumpToBottom}
          aria-label="Cuộn xuống tin nhắn mới nhất"
          className={cn(
            "absolute bottom-4 right-6 z-20 flex h-9 w-9 items-center justify-center rounded-full",
            "border border-border/80 bg-background/90 text-foreground shadow-md backdrop-blur-xs",
            "transition-all duration-200 hover:bg-muted hover:scale-105 active:scale-95 cursor-pointer"
          )}
          title="Cuộn xuống tin nhắn mới nhất"
        >
          <ArrowDown className="h-4 w-4" />
          {busy && (
            <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-primary" />
            </span>
          )}
        </button>
      )}
    </div>
  );
};
