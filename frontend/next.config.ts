import type { NextConfig } from "next";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8989";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      { source: "/api/backend/:path*", destination: `${apiBase}/api/:path*` },
    ];
  },
};

export default nextConfig;
