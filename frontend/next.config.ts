import type { NextConfig } from "next";

/**
 * Next.js configuration.
 *
 * - `proxyTimeout`: Extended to 2 minutes because hybrid-mode queries involve
 *   three sequential LLM calls that can take up to ~90 seconds.
 * - `rewrites`: Proxies all `/api/*` requests to the FastAPI backend running
 *   on `localhost:8000` so the frontend needs no explicit base URL.
 */
const nextConfig: NextConfig = {
  experimental: {
    proxyTimeout: 120_000, // 2 minutes — hybrid mode makes 3 LLM calls
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
