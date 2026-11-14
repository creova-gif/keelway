import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/utils";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const routes = [
    { path: "/", priority: 1.0 },
    { path: "/playground", priority: 0.95 },
    { path: "/models", priority: 0.9 },
    { path: "/governance", priority: 0.9 },
    { path: "/pricing", priority: 0.85 },
    { path: "/docs", priority: 0.9 },
    { path: "/api-reference", priority: 0.85 },
    { path: "/brand", priority: 0.6 },
  ];

  return routes.map((r) => ({
    url: `${SITE_URL}${r.path === "/" ? "" : r.path}`,
    lastModified: now,
    changeFrequency: "weekly",
    priority: r.priority,
  }));
}
