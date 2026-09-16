import { Suspense } from "react";
import DocumentDetailClient from "./DocumentDetailClient";

export default function DocumentDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen w-screen items-center justify-center text-sm text-muted-foreground">
          Đang tải...
        </div>
      }
    >
      <DocumentDetailClient />
    </Suspense>
  );
}
