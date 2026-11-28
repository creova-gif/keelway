import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async redirects() {
    // Permanent 308s for legacy .html bookmarks from the pre-App-Router site.
    return [
      { source: "/index.html", destination: "/", permanent: true },
      { source: "/docs.html", destination: "/docs", permanent: true },
      { source: "/api.html", destination: "/product", permanent: true },
      { source: "/brand.html", destination: "/about", permanent: true },
    ];
  },
};

export default nextConfig;
