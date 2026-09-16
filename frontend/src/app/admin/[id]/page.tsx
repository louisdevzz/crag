import DocumentDetailClient from "./DocumentDetailClient";

export async function generateStaticParams() {
  return [{ id: "default" }];
}

export default function DocumentDetailPage() {
  return <DocumentDetailClient />;
}
