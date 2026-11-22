import { NextResponse } from "next/server";
import { SITE_URL } from "@/lib/utils";

interface FeedItem {
  title: string;
  path: string;
  pubDate: string;
  description: string;
}

const FEED_ITEMS: readonly FeedItem[] = [
  {
    title: "Keelway v1.1.0 — Local-First Agent Runtime & 10-View Unified Studio",
    path: "/changelog",
    pubDate: "Thu, 01 Oct 2026 00:00:00 GMT",
    description:
      "Run open-weight OpenCore models locally at $0 token COGS alongside 0%-markup BYOM cloud routing and P-10 human approval gates.",
  },
  {
    title: "Signed Marketplace & 85/15 Creator Split",
    path: "/pricing",
    pubDate: "Wed, 30 Sep 2026 00:00:00 GMT",
    description:
      "Install Ed25519-signed agents, multi-agent squads, skills, and workflow extensions verified by SHA-256 digests.",
  },
  {
    title: "4D Deterministic Routing & Hash-Chained Execution Proofs",
    path: "/product",
    pubDate: "Tue, 29 Sep 2026 00:00:00 GMT",
    description:
      "Verify SHA-256 flight-tape continuity, manifest drift protection, and zero-egress privacy boundaries.",
  },
];

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export function GET() {
  const itemsXml = FEED_ITEMS.map((item) => {
    const url = `${SITE_URL}${item.path}`;
    return [
      "    <item>",
      `      <title>${escapeXml(item.title)}</title>`,
      `      <link>${escapeXml(url)}</link>`,
      `      <guid isPermaLink="true">${escapeXml(url)}</guid>`,
      `      <pubDate>${item.pubDate}</pubDate>`,
      `      <description>${escapeXml(item.description)}</description>`,
      "    </item>",
  ].join("\n");
  }).join("\n");

  const xml = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
    "  <channel>",
    "    <title>Keelway — Sovereign Agent Platform</title>",
    `    <link>${escapeXml(SITE_URL)}</link>`,
    "    <description>Release notes, architecture documentation, and security updates from Keelway.</description>",
    "    <language>en-us</language>",
    `    <atom:link href="${escapeXml(`${SITE_URL}/feed.xml`)}" rel="self" type="application/rss+xml" />`,
    itemsXml,
    "  </channel>",
    "</rss>",
  ].join("\n");

  return new NextResponse(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600, s-maxage=3600",
    },
  });
}
