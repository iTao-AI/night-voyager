import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "Night Voyager",
  description: "Evidence-grounded study-abroad decision workflow prototype",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
