import type { NextConfig } from "next";

const config: NextConfig = {
  devIndicators: false,
  // The SDK auto-mounts a CDN-backed inspector in development; keep the research UI self-contained.
  turbopack: { resolveAlias: { "@openuidev/devtools": "./src/lib/openui-devtools-disabled.ts" } },
  experimental: { proxyClientMaxBodySize: "24mb" },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${process.env.GATEWAY_URL ?? "http://127.0.0.1:8001"}/api/:path*` }];
  },
};
export default config;
