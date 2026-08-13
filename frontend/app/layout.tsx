import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "知衡 · 股票复盘 Agent",
  description: "收盘后自动完成市场复盘、多角色研判、风险复核与次日观察池生成。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
