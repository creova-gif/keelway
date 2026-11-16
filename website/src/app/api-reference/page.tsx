import fs from "fs";
import path from "path";
import React from "react";
import type { Metadata } from "next";
import { Download } from "lucide-react";
import { ApiExplorer, type OpenApiOperationSummary } from "@/components/api/ApiExplorer";
import { LiveRoutingSandbox } from "@/components/api/LiveRoutingSandbox";
import { SITE_URL } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Core Public SDK & OpenAI-Compatible API",
  description:
    "Drop-in base_url replacement + deterministic governance headers across OpenCore local inference and commercial Frontier APIs.",
  alternates: { canonical: "/api-reference" },
  openGraph: {
    title: "Core Public SDK & OpenAI-Compatible API · Keelway",
    description:
      "Drop-in base_url replacement, stateful /v1/responses, 4D routing provenance, and enterprise governance REST API.",
    url: `${SITE_URL}/api-reference`,
  },
};

interface RawOpenApiDoc {
  openapi?: string;
  paths?: Record<string, Record<string, { tags?: string[]; summary?: string; responses?: Record<string, unknown> }>>;
}

function isCorePublicSurfacePath(routePath: string): boolean {
  return (
    routePath === "/health" ||
    routePath.startsWith("/v1/chat/") ||
    routePath.startsWith("/v1/responses") ||
    routePath.startsWith("/v1/models") ||
    routePath.startsWith("/v1/routing") ||
    routePath.startsWith("/v1/usage") ||
    routePath.startsWith("/v1/governance")
  );
}

function loadOpenApiOperations(): {
  operations: OpenApiOperationSummary[];
  tags: string[];
  specVersion: string;
} {
  const filePath = path.join(process.cwd(), "public", "openapi.json");
  const raw = JSON.parse(fs.readFileSync(filePath, "utf8")) as RawOpenApiDoc;
  const operations: OpenApiOperationSummary[] = [];
  const tagSet = new Set<string>();
  const httpMethods = new Set(["get", "post", "put", "delete", "patch"]);

  for (const [routePath, methods] of Object.entries(raw.paths ?? {})) {
    if (!isCorePublicSurfacePath(routePath)) continue;
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

  operations.sort((a, b) => {
    const aV1 = a.path.startsWith("/v1/") ? 0 : 1;
    const bV1 = b.path.startsWith("/v1/") ? 0 : 1;
    return aV1 !== bV1 ? aV1 - bV1 : a.path.localeCompare(b.path);
  });

  return { operations, tags: Array.from(tagSet).sort(), specVersion: raw.openapi ?? "3.1.0" };
}

/**
 * Core Public SDK & OpenAI-Compatible API (/api-reference)
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
          <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
            <div className="max-w-3xl">
              <div className="inline-flex flex-wrap items-center gap-2 rounded-full border border-border-strong bg-surface/90 px-3.5 py-1.5 font-mono text-xs">
                <span className="h-2 w-2 rounded-full bg-teal-accent" aria-hidden="true" />
                <span className="font-semibold text-fg">OPENAPI {specVersion}</span>
                <span className="text-fg-dim">·</span>
                <span className="text-fg-muted">Inference · Routing · Usage · Governance</span>
              </div>
              <h1 id="api-hero-heading" className="mt-4 text-3xl font-extrabold tracking-tight text-fg sm:text-5xl">
                Core Public SDK &amp; OpenAI-Compatible API
              </h1>
              <p className="mt-3 text-base leading-relaxed text-fg-muted sm:text-lg">
                Drop-in <code className="font-mono text-sm text-fg">base_url</code> replacement + deterministic governance headers across local OpenCore weights and commercial Frontier providers.
              </p>
            </div>

            <a
              href="/openapi.json"
              download="keelway-openapi-3.1.json"
              className="kw-btn kw-btn-secondary shrink-0 font-mono text-xs"
            >
              <Download className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Download openapi.json</span>
            </a>
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
