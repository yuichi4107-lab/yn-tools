import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "営業自動化ツール",
  description: "企業検索・キャンペーン管理・CRM",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
