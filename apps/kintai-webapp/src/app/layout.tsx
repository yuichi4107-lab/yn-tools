import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "勤怠管理Webアプリ",
  description: "勤怠データの集計・管理",
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
