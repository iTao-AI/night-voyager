import type { Metadata } from "next";
import { PresentationProvider } from "../lib/presentation/context";
import "./styles.css";
import "./portfolio.css";
import "./workspace.css";

export const metadata: Metadata = {
  title: "Night Voyager｜留学顾问的 AI 协作工作台",
  description: "把分散在聊天、资料和研究中的信息，整理成可核对、可沟通、可推进的留学方案。",
  icons: {
    icon: "/icon.svg",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body><PresentationProvider>{children}</PresentationProvider></body>
    </html>
  );
}
