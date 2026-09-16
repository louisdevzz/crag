"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import {
  Briefcase,
  Building2,
  Database,
  Folder,
  HeartPulse,
  MessageSquare,
  MessageSquarePlus,
  PanelLeft,
  Receipt,
  Scale,
  Search,
  Sparkles,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { ConversationSummary, groupConversationsByDay } from "@/lib/history";
import { groupDocumentsByCategory } from "@/lib/categories";
import { LegalDocument } from "@/lib/types";
import { cn } from "@/lib/utils";

const CATEGORY_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  "Bảo hiểm xã hội": HeartPulse,
  "Đăng ký doanh nghiệp": Building2,
  "Luật lao động": Briefcase,
  "Thuế doanh nghiệp": Receipt,
};

interface AppSidebarProps {
  clientId: string;
  documents: LegalDocument[];
  conversations: ConversationSummary[];
  activeSessionId: string;
  memoryCount: number;
  onNewChat: () => void;
  onSelectConversation: (sessionId: string) => void;
  onSelectPrompt: (prompt: string) => void;
  onOpenSettings?: () => void;
}

export const AppSidebar: React.FC<AppSidebarProps> = ({
  clientId,
  documents,
  conversations,
  activeSessionId,
  memoryCount,
  onNewChat,
  onSelectConversation,
  onSelectPrompt,
  onOpenSettings,
}) => {
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const { state } = useSidebar();
  const isCollapsed = state === "collapsed";

  const categoryGroups = useMemo(() => groupDocumentsByCategory(documents), [documents]);
  const dayGroups = useMemo(() => groupConversationsByDay(conversations), [conversations]);

  const filteredConversations = conversations.filter((c) =>
    c.title.toLowerCase().includes(query.toLowerCase())
  );
  const filteredDocuments = documents.filter(
    (d) =>
      d.title.toLowerCase().includes(query.toLowerCase()) ||
      d.document_number.toLowerCase().includes(query.toLowerCase())
  );

  const runSearch = (handler: () => void) => {
    handler();
    setIsSearchOpen(false);
    setQuery("");
  };

  return (
    <>
      <Sidebar collapsible="icon" className="border-r border-sidebar-border bg-sidebar">
        {/* Brand Header */}
        <SidebarHeader className="px-3 pt-3 pb-2 gap-2.5">
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={onNewChat}
              className="flex items-center gap-2.5 text-left group-data-[collapsible=icon]:justify-center focus:outline-none cursor-pointer"
            >
              <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-xs">
                <Scale className="h-4 w-4" />
              </div>
              <div className="flex flex-col min-w-0 group-data-[collapsible=icon]:hidden">
                <span className="text-sm font-bold tracking-tight text-sidebar-foreground truncate leading-tight">
                  Legal CRAG
                </span>
                <span className="text-[10px] font-medium text-sidebar-foreground/50 tracking-wide uppercase">
                  Assistant
                </span>
              </div>
            </button>

            <SidebarTrigger className="h-7 w-7 text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent rounded-md group-data-[collapsible=icon]:hidden" />
          </div>

          {/* Primary Action: New Chat (DeepSeek Harness style) */}
          <div className="pt-1">
            <button
              type="button"
              onClick={onNewChat}
              className={cn(
                "flex items-center gap-2 w-full rounded-xl border border-sidebar-border bg-sidebar-accent/50 px-2.5 py-2 text-xs font-semibold text-sidebar-foreground transition-all hover:bg-sidebar-accent hover:border-sidebar-border/80 shadow-2xs cursor-pointer",
                "group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:w-7 group-data-[collapsible=icon]:h-7 group-data-[collapsible=icon]:mx-auto"
              )}
              title="Cuộc trò chuyện mới"
            >
              <MessageSquarePlus className="h-4 w-4 text-primary flex-shrink-0" />
              <span className="truncate group-data-[collapsible=icon]:hidden">Cuộc trò chuyện mới</span>
            </button>
          </div>

          {/* Quick Navigation Panels */}
          <SidebarMenu className="mt-1">
            <SidebarMenuItem>
              <SidebarMenuButton onClick={() => setIsSearchOpen(true)} tooltip="Tìm kiếm nhanh">
                <Search className="h-4 w-4 text-sidebar-foreground/60" />
                <span className="text-xs">Tìm kiếm</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton asChild tooltip="Kho dữ liệu văn bản">
                <Link href="/admin">
                  <Database className="h-4 w-4 text-sidebar-foreground/60" />
                  <span className="text-xs">Quản lý Dữ liệu</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>

        <SidebarSeparator className="my-1" />

        {/* Scrollable Main Area: History first, then Legal Categories */}
        <SidebarContent className="px-2">
          {/* Conversation History */}
          {dayGroups.length === 0 ? (
            <div className="px-2 py-4 text-center text-xs text-sidebar-foreground/40 group-data-[collapsible=icon]:hidden">
              Chưa có cuộc trò chuyện nào
            </div>
          ) : (
            dayGroups.map(({ label, conversations: convs }) => (
              <SidebarGroup key={label} className="py-1">
                <SidebarGroupLabel className="text-[11px] font-semibold text-sidebar-foreground/50 px-2 py-1">
                  {label}
                </SidebarGroupLabel>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {convs.map((conversation) => (
                      <SidebarMenuItem key={conversation.sessionId}>
                        <SidebarMenuButton
                          onClick={() => onSelectConversation(conversation.sessionId)}
                          isActive={conversation.sessionId === activeSessionId}
                          tooltip={conversation.title}
                          className={cn(
                            "rounded-lg text-xs transition-colors",
                            conversation.sessionId === activeSessionId
                              ? "bg-sidebar-accent text-sidebar-accent-foreground font-semibold"
                              : "text-sidebar-foreground/80 hover:bg-sidebar-accent/50"
                          )}
                        >
                          <MessageSquare className="h-3.5 w-3.5 flex-shrink-0 text-sidebar-foreground/50" />
                          <span className="truncate">{conversation.title}</span>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    ))}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            ))
          )}

          {/* Legal Categories Section */}
          {categoryGroups.length > 0 && (
            <SidebarGroup className="mt-2 pt-2 border-t border-sidebar-border/40">
              <SidebarGroupLabel className="text-[11px] font-semibold text-sidebar-foreground/50 px-2 py-1">
                Kho quy phạm
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {categoryGroups.map(({ category, documents: docs }) => {
                    const Icon = CATEGORY_ICONS[category] || Folder;
                    return (
                      <SidebarMenuItem key={category}>
                        <SidebarMenuButton
                          onClick={() =>
                            onSelectPrompt(
                              `Cho tôi biết những quy định pháp lý chính trong nhóm văn bản "${category}".`
                            )
                          }
                          tooltip={`${category} (${docs.length})`}
                          className="text-xs text-sidebar-foreground/75 hover:bg-sidebar-accent/50 rounded-lg"
                        >
                          <Icon className="h-3.5 w-3.5 text-sidebar-foreground/50 flex-shrink-0" />
                          <span className="truncate">{category}</span>
                        </SidebarMenuButton>
                        <SidebarMenuBadge className="text-[10px] font-mono text-sidebar-foreground/50">
                          {docs.length}
                        </SidebarMenuBadge>
                      </SidebarMenuItem>
                    );
                  })}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          )}
        </SidebarContent>

      </Sidebar>

      {/* Quick Search Dialog */}
      <CommandDialog open={isSearchOpen} onOpenChange={setIsSearchOpen}>
        <CommandInput
          placeholder="Tìm cuộc trò chuyện hoặc văn bản pháp lý..."
          value={query}
          onValueChange={setQuery}
        />
        <CommandList>
          <CommandEmpty>Không tìm thấy kết quả phù hợp.</CommandEmpty>
          {filteredConversations.length > 0 && (
            <CommandGroup heading="Cuộc trò chuyện">
              {filteredConversations.map((conversation) => (
                <CommandItem
                  key={conversation.sessionId}
                  value={`conv-${conversation.sessionId}`}
                  onSelect={() => runSearch(() => onSelectConversation(conversation.sessionId))}
                >
                  <MessageSquare className="mr-2 h-4 w-4 text-primary" />
                  <span className="truncate">{conversation.title}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          )}

          {filteredDocuments.length > 0 && (
            <CommandGroup heading="Văn bản pháp luật">
              {filteredDocuments.map((doc) => (
                <CommandItem
                  key={doc.id}
                  value={`doc-${doc.id}`}
                  onSelect={() =>
                    runSearch(() =>
                      onSelectPrompt(`Tóm tắt nội dung chính của ${doc.document_number}: ${doc.title}`)
                    )
                  }
                >
                  <Folder className="mr-2 h-4 w-4 text-indigo-500" />
                  <div className="flex flex-col min-w-0">
                    <span className="font-semibold text-xs">{doc.document_number}</span>
                    <span className="text-[11px] text-muted-foreground truncate">{doc.title}</span>
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          )}
        </CommandList>
      </CommandDialog>
    </>
  );
};
