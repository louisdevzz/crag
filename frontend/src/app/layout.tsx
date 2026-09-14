import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Legal CRAG Assistant — Trợ lý Pháp lý & Tuân thủ",
  description: "Trợ lý AI hỗ trợ tra cứu pháp luật doanh nghiệp Việt Nam với Corrective RAG (CRAG) và Session Memory",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
