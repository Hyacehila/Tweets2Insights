import type { NextConfig } from "next";

const config: NextConfig = {
  devIndicators: false,
  experimental: { proxyClientMaxBodySize: "24mb" },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${process.env.GATEWAY_URL ?? "http://127.0.0.1:8001"}/api/:path*` }];
  },
};
export default config;
