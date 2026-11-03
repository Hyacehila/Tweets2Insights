import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "Tweets2Insights · 研究工作台", description: "事件复盘、证据分析、预测与条件情景研究" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="zh-CN"><body>{children}</body></html>; }
