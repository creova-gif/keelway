import fs from "fs";
import path from "path";
import React from "react";
import type { Metadata } from "next";
import {
  ApiExplorer,
  type OpenApiOperationSummary,
} from "@/components/api/ApiExplorer";
import { LiveRoutingSandbox } from "@/components/api/LiveRoutingSandbox";
import { SITE_URL } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Interactive API Reference (OpenAPI 3.1)",
  description:
    "Explore all 183 endpoints in Keelway's OpenAPI 3.1 specification with runnable cURL, Python SDK v1, OpenAI-compatible, and CLI snippets.",
  alternates: {
    canonical: "/api-reference",
  },
  openGraph: {
    title: "Interactive API Reference · Keelway",
    description:
      "Unified Responses API, OpenCore Runtime, 4D Routing Provenance, and Multi-Tenant Governance REST reference.",
    url: `${SITE_URL}/api-reference`,
  },
};

interface RawOpenApiDoc {
  openapi?: string;
  info?: { version?: string; title?: string };
  paths?: Record<
    string,
    Record<
      string,
      {
        tags?: string[];
        summary?: string;
        responses?: Record<string, unknown>;
      }
    >
  >;
}

function loadOpenApiOperations(): {
  operations: OpenApiOperationSummary[];
  tags: string[];
  specVersion: string;
} {
  const filePath = path.join(process.cwd(), "public", "openapi.json");
  const raw = JSON.parse(fs.readFileSync(filePath, "utf8")) as RawOpenApiDoc;
  const pathsObj = raw.paths ?? {};
  const operations: OpenApiOperationSummary[] = [];
  const tagSet = new Set<string>();

  const httpMethods = new Set(["get", "post", "put", "delete", "patch"]);

  for (const [routePath, methods] of Object.entries(pathsObj)) {
    for (const [m, spec] of Object.entries(methods)) {
      if (!httpMethods.has(m.toLowerCase())) continue;
      const tag = spec.tags?.[0] ?? "Core";
      tagSet.add(tag);
      operations.push({
        method: m.toUpperCase(),
        path: routePath,
        tag,
        summary: spec.summary ?? routePath,
        statusCodes: Object.keys(spec.responses ?? { "200": {} }),
      });
    }
  }

  // Prioritize /v1/* Hybrid AI routes at the top of the directory
  operations.sort((a, b) => {
    const aV1 = a.path.startsWith("/v1/") ? 0 : 1;
    const bV1 = b.path.startsWith("/v1/") ? 0 : 1;
    if (aV1 !== bV1) return aV1 - bV1;
    return a.path.localeCompare(b.path);
  });

  return {
    operations,
    tags: Array.from(tagSet).sort(),
    specVersion: raw.openapi ?? "3.1.0",
  };
}

/**
 * Page 7 (Stage 5b): Interactive API Reference (/api-reference)
 * Server-renders a compact operation index directly from `public/openapi.json`
 * and also handles permanent redirects from legacy `/api.html`.
 */
export default function ApiReferencePage() {
  const { operations, tags, specVersion } = loadOpenApiOperations();

  return (
    <div>
      <section
        aria-labelledby="api-hero-heading"
        className="blueprint-surface border-b border-border-subtle py-12 sm:py-16"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-sm border border-border-strong bg-surface/90 px-3 py-1 font-mono text-xs">
              <span className="chip-teal rounded-sm px-2 py-0.5">
                OPENAPI {specVersion}
              </span>
              <span className="text-fg-muted">
                {operations.length} Verified Endpoints · {tags.length} Domain
                Groups
              </span>
            </div>

            <h1
              id="api-hero-heading"
              className="mt-4 text-3xl font-extrabold tracking-tight text-fg sm:text-5xl"
            >
              Interactive API Reference
            </h1>

            <p className="mt-3 text-base leading-relaxed text-fg-muted sm:text-lg">
              One consistent REST &amp; SSE contract across OpenCore local
              weights and commercial Frontier providers — generated directly
              from Keelway&apos;s live FastAPI schema.
            </p>
          </div>
        </div>
      </section>

      <section className="py-12 sm:py-16">
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <LiveRoutingSandbox />
          <ApiExplorer operations={operations} tags={tags} />
        </div>
      </section>
    </div>
  );
}
