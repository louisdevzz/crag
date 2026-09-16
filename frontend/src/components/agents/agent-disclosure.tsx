"use client";

import React, { ReactNode } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { EASE_OUT } from "@/lib/ease";
import { cn } from "@/lib/utils";

export interface AgentDisclosureProps {
  id?: string;
  open: boolean;
  role?: string;
  "aria-labelledby"?: string;
  openHeight?: number;
  children: ReactNode;
  className?: string;
}

export const AgentDisclosure: React.FC<AgentDisclosureProps> = ({
  id,
  open,
  role,
  "aria-labelledby": ariaLabelledby,
  openHeight,
  children,
  className,
}) => {
  const reduce = useReducedMotion() ?? false;

  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.div
          id={id}
          role={role}
          aria-labelledby={ariaLabelledby}
          initial={reduce ? { opacity: 0 } : { opacity: 0, height: 0 }}
          animate={
            reduce
              ? { opacity: 1 }
              : { opacity: 1, height: openHeight != null ? openHeight : "auto" }
          }
          exit={reduce ? { opacity: 0 } : { opacity: 0, height: 0 }}
          transition={reduce ? { duration: 0 } : { duration: 0.22, ease: EASE_OUT }}
          className={cn("overflow-hidden", className)}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  );
};
