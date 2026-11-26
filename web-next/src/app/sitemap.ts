import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/utils";

const ROUTES = [
  "",
  "/product",
  "/pricing",
  "/docs",
  "/changelog",
  "/about",
  "/blog",
  "/contact",
  "/legal",
  "/sign-in",
  "/signup",
];

export default function sitemap(): MetadataRoute.Sitemap {
  return ROUTES.map((path) => ({
    url: `${SITE_URL}${path}`,
    lastModified: new Date(),
    changeFrequency: path === "" ? "weekly" : "monthly",
    priority: path === "" ? 1 : 0.7,
  }));
}
