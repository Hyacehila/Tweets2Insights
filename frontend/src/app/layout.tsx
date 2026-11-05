import type { Metadata } from "next";
import "./globals.css";
import "./intelligent-ui.css";
import { ThemeProvider } from "@/components/theme-provider";
import { LanguageProvider } from "@/components/language-provider";
export const metadata: Metadata = {
  title: "Tweets2Insights",
  description: "事件复盘、证据分析、预测与条件情景研究",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body>
        <ThemeProvider>
          <LanguageProvider>{children}</LanguageProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
