import type { Metadata } from "next";
import { PresentationProvider } from "../lib/presentation/context";
import "./styles.css";

export const metadata: Metadata = {
  title: "Night Voyager｜你的留学路线应该从你出发",
  description: "从学生条件出发，看懂推荐、备选与取舍，再把本地合成路线比较变成可执行计划。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body><PresentationProvider>{children}</PresentationProvider></body>
    </html>
  );
}
