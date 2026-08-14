import type { Metadata } from "next";
import { PresentationProvider } from "../lib/presentation/context";
import "./styles.css";
import "./portfolio.css";
import "./workspace.css";

export const metadata: Metadata = {
  title: "Night Voyager｜为留学顾问打造的 AI 协作平台",
  description: "Night Voyager 帮助顾问把散落在对话里的预算、目标、时间和现实条件整理清楚，再据此比较不同路线、说明推荐理由，并推进下一步。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body><PresentationProvider>{children}</PresentationProvider></body>
    </html>
  );
}
