"use client";

import React, { useMemo, useState } from "react";
import {
  Briefcase,
  Building2,
  Folder,
  HeartPulse,
  MessageSquarePlus,
  Receipt,
  Search,
  Settings,
  Sparkles,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { ConversationSummary, groupConversationsByDay } from "@/lib/history";
import { groupDocumentsByCategory } from "@/lib/categories";
import { LegalDocument } from "@/lib/types";

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
  onOpenSettings: () => void;
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

  const clientLabel = clientId ? clientId.replace(/^client_/, "").slice(0, 8) : "…";

  return (
    <>
      <Sidebar collapsible="icon" className="border-sidebar-border">
        <SidebarHeader className="gap-3 px-2 py-3">
          <div className="flex items-center gap-2 px-1.5">
            <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
              <Sparkles className="h-3.5 w-3.5" />
            </div>
            <span className="truncate text-[15px] font-bold tracking-tight text-sidebar-foreground group-data-[collapsible=icon]:hidden">
              Trợ Lý Pháp Lý
            </span>
          </div>

          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton onClick={onNewChat} tooltip="Cuộc trò chuyện mới">
                <MessageSquarePlus />
                <span>Cuộc trò chuyện mới</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton onClick={() => setIsSearchOpen(true)} tooltip="Tìm kiếm">
                <Search />
                <span>Tìm kiếm</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>

        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Kho Tri Thức</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {categoryGroups.length === 0 ? (
                  <SidebarMenuItem>
                    <span className="px-2 text-xs italic text-sidebar-foreground/50">
                      Đang tải danh mục...
                    </span>
                  </SidebarMenuItem>
                ) : (
                  categoryGroups.map(({ category, documents: docs }) => {
                    const Icon = CATEGORY_ICONS[category] || Folder;
                    return (
                      <SidebarMenuItem key={category}>
                        <SidebarMenuButton
                          onClick={() =>
                            onSelectPrompt(
                              `Cho tôi biết những quy định pháp lý chính trong nhóm văn bản "${category}".`
                            )
                          }
                          tooltip={category}
                        >
                          <Icon />
                          <span>{category}</span>
                        </SidebarMenuButton>
                        <SidebarMenuBadge>
                          {String(docs.length).padStart(2, "0")}
                        </SidebarMenuBadge>
                      </SidebarMenuItem>
                    );
                  })
                )}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>

          {dayGroups.map(({ label, conversations: convs }) => (
            <SidebarGroup key={label}>
              <SidebarGroupLabel>{label}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {convs.map((conversation) => (
                    <SidebarMenuItem key={conversation.sessionId}>
                      <SidebarMenuButton
                        onClick={() => onSelectConversation(conversation.sessionId)}
                        isActive={conversation.sessionId === activeSessionId}
                        tooltip={conversation.title}
                      >
                        <span className="truncate">{conversation.title}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          ))}
        </SidebarContent>

        <SidebarSeparator />

        <SidebarFooter className="px-2 pb-2">
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" onClick={onOpenSettings} tooltip="Cài đặt">
                <Avatar className="h-6 w-6">
                  <AvatarFallback className="bg-primary/10 text-[10px] font-bold text-primary">
                    {clientLabel.slice(0, 2).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div className="flex min-w-0 flex-1 flex-col leading-tight group-data-[collapsible=icon]:hidden">
                  <span className="truncate text-xs font-semibold">Ẩn danh · {clientLabel}</span>
                  <span className="truncate text-[10px] text-sidebar-foreground/60">
                    {memoryCount > 0 ? `${memoryCount} hồ sơ đã ghi nhận` : "Chưa có hồ sơ"}
                  </span>
                </div>
                <Settings className="h-3.5 w-3.5 flex-shrink-0 text-sidebar-foreground/50 group-data-[collapsible=icon]:hidden" />
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      </Sidebar>

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
                  <MessageSquarePlus className="mr-2 h-4 w-4" />
                  <span className="truncate">{conversation.title}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          )}
          {filteredDocuments.length > 0 && (
            <CommandGroup heading="Văn bản pháp lý">
              {filteredDocuments.slice(0, 8).map((doc) => (
                <CommandItem
                  key={doc.id}
                  value={`doc-${doc.id}`}
                  onSelect={() =>
                    runSearch(() =>
                      onSelectPrompt(
                        `Tóm tắt nội dung chính của văn bản ${doc.document_number} - ${doc.title}.`
                      )
                    )
                  }
                >
                  <Folder className="mr-2 h-4 w-4" />
                  <div className="flex min-w-0 flex-col">
                    <span className="truncate font-mono text-xs font-semibold">
                      {doc.document_number}
                    </span>
                    <span className="truncate text-xs text-muted-foreground">{doc.title}</span>
                  </div>
                  <Badge variant="outline" className="ml-auto text-[10px]">
                    {doc.status === "effective" ? "Còn hiệu lực" : "Hết hiệu lực"}
                  </Badge>
                </CommandItem>
              ))}
            </CommandGroup>
          )}
        </CommandList>
      </CommandDialog>
    </>
  );
};
