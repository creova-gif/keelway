import path from "path";
import type { NextConfig } from "next";

/**
 * Next.js 15 Configuration for Keelway Website
 * Preserves legacy .html URLs via permanent redirects so existing external
 * links, bookmarks, and README references never break.
 */
const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  outputFileTracingRoot: path.join(__dirname),
  async redirects() {
    return [
      {
        source: "/index.html",
        destination: "/",
        permanent: true,
      },
      {
        source: "/docs.html",
        destination: "/docs",
        permanent: true,
      },
      {
        source: "/api.html",
        destination: "/api-reference",
        permanent: true,
      },
      {
        source: "/brand.html",
        destination: "/brand",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
