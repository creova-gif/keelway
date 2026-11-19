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
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), payment=()",
          },
          {
            key: "Cross-Origin-Opener-Policy",
            value: "same-origin",
          },
        ],
      },
    ];
  },
  async redirects() {
    return [
      {
        source: "/favicon.ico",
        destination: "/favicon.svg",
        permanent: true,
      },
      {
        source: "/playground",
        destination: "/",
        permanent: true,
      },
      {
        source: "/index.html",
        destination: "/",
        permanent: true,
      },
      {
        source: "/docs.html",
        destination: "/changelog",
        permanent: true,
      },
      {
        source: "/releases",
        destination: "/changelog",
        permanent: true,
      },
      {
        source: "/api.html",
        destination: "/product",
        permanent: true,
      },
      {
        source: "/brand.html",
        destination: "/about",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
