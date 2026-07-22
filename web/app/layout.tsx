import type { Metadata } from "next";
import { PresentationProvider } from "../lib/presentation/context";
import "./styles.css";

export const metadata: Metadata = {
  title: "Night Voyager｜把家庭事实变成可追溯的留学决策与行动计划",
  description: "使用本地合成数据，从已确认家庭事实走到顾问审核、家庭决定与行动回执。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body><PresentationProvider>{children}</PresentationProvider></body>
    </html>
  );
}
