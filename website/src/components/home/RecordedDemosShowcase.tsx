"use client";

import React, { useEffect, useRef, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { useReducedMotion } from "framer-motion";
import { Cpu, Film, Pause, Play, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

interface DemoClip {
  id: "studio" | "metal";
  tabLabel: string;
  badge: string;
  title: string;
  subtitle: string;
  command: string;
  webmSrc: string;
  mp4Src: string;
  posterSrc: string;
  metrics: { label: string; value: string }[];
}

const DEMO_CLIPS: DemoClip[] = [
  {
    id: "studio",
    tabLabel: "1. Workspace Approval Gate",
    badge: "60FPS CAPTURE · KEELWAY STUDIO",
    title: "Human-in-the-Loop Code Diff & Cryptographic Audit Receipt",
    subtitle:
      "Real capture of `keelway dev`: reviewing a multi-file billing fix before any file changes on disk, running automated verification, and recording a tamper-evident SHA-256 audit receipt.",
    command: "keelway dev --port 7420",
    webmSrc: "/demos/studio-approval-loop.webm",
    mp4Src: "/demos/studio-approval-loop.mp4",
    posterSrc: "/demos/studio-poster.png",
    metrics: [
      { label: "Safety Gate", value: "Human Approval Required" },
      { label: "Verification", value: "14 / 14 Checks Passed" },
      { label: "Audit Receipt", value: "SHA-256 Verified" },
    ],
  },
  {
    id: "metal",
    tabLabel: "2. Local Private Model Stream",
    badge: "60FPS CAPTURE · APPLE SILICON",
    title: "Private On-Device AI Inference with Zero Cloud Egress",
    subtitle:
      "Captured live running a local OpenCore model on Apple Silicon unified memory (`privacy_level=\"private\"`) — zero prompts or customer files ever leave your machine.",
    command:
      "keelway route --model keelway-core:7b --privacy private --stream",
    webmSrc: "/demos/cli-metal-stream.webm",
    mp4Src: "/demos/cli-metal-stream.mp4",
    posterSrc: "/demos/cli-poster.png",
    metrics: [
      { label: "Hardware", value: "Local Apple Silicon" },
      { label: "Cloud Egress", value: "0 Bytes" },
      { label: "Token Cost", value: "$0.00 / 1M" },
    ],
  },
];

/**
 * High-Frame-Rate Recorded Studio & CLI Demo Loops.
 * Pairs crisp 60fps WebM/MP4 captures alongside interactive React instruments,
 * honoring `prefers-reduced-motion` with explicit Play/Pause controls.
 */
export function RecordedDemosShowcase() {
  const prefersReducedMotion = useReducedMotion();
  const [activeTab, setActiveTab] = useState<string>("studio");
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const activeClip =
    DEMO_CLIPS.find((c) => c.id === activeTab) ?? DEMO_CLIPS[0];

  useEffect(() => {
    const vid = videoRef.current;
    if (!vid) return;
    vid.load();
    if (!prefersReducedMotion) {
      const p = vid.play();
      if (p !== undefined) {
        p.then(() => setIsPlaying(true)).catch(() => setIsPlaying(false));
      }
    } else {
      vid.pause();
      setIsPlaying(false);
    }
  }, [activeTab, prefersReducedMotion]);

  const togglePlayback = () => {
    const vid = videoRef.current;
    if (!vid) return;
    if (vid.paused) {
      vid
        .play()
        .then(() => {
          setIsPlaying(true);
          trackEvent("demo_video_toggled", {
            clip: activeClip.id,
            action: "play",
          });
        })
        .catch(() => setIsPlaying(false));
    } else {
      vid.pause();
      setIsPlaying(false);
      trackEvent("demo_video_toggled", {
        clip: activeClip.id,
        action: "pause",
      });
    }
  };

  return (
    <section
      id="recorded-demos"
      aria-labelledby="recorded-demos-heading"
      className="border-t border-border-subtle bg-surface/30 py-16 sm:py-20"
    >
      <div className="mx-auto max-w-container px-4 sm:px-6">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div className="max-w-2xl">
            <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
              REAL PRODUCT CAPTURES · ZERO MOCKUPS
            </p>
            <h2
              id="recorded-demos-heading"
              className="mt-2 text-2xl font-bold tracking-tight text-fg sm:text-3xl"
            >
              See Keelway Running Live on Local Hardware
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-fg-muted">
              60fps captures from{" "}
              <code className="font-mono text-xs text-fg">
                keelway dev
              </code>{" "}
              showing human-approved changes and private on-device model
              streaming.
            </p>
          </div>
        </div>

        <Tabs.Root
          value={activeTab}
          onValueChange={(val) => {
            setActiveTab(val);
            trackEvent("demo_video_toggled", { clip: val, action: "switch" });
          }}
          className="mt-8"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Tabs.List
              aria-label="Recorded runtime demonstrations"
              className="inline-flex flex-wrap gap-2 rounded-md border border-border-strong bg-surface p-1.5"
            >
              {DEMO_CLIPS.map((clip) => (
                <Tabs.Trigger
                  key={clip.id}
                  value={clip.id}
                  className={cn(
                    "inline-flex min-h-[44px] items-center gap-2 rounded-sm px-3.5 py-2 font-mono text-xs font-semibold transition-colors duration-150",
                    activeTab === clip.id
                      ? "bg-teal-accent text-teal-ink"
                      : "text-fg-muted hover:text-fg"
                  )}
                >
                  {clip.id === "studio" ? (
                    <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                  ) : (
                    <Cpu className="h-3.5 w-3.5" aria-hidden="true" />
                  )}
                  <span>{clip.tabLabel}</span>
                </Tabs.Trigger>
              ))}
            </Tabs.List>

            <button
              type="button"
              onClick={togglePlayback}
              aria-label={isPlaying ? "Pause demo loop" : "Play demo loop"}
              className="kw-btn kw-btn-secondary font-mono text-xs"
            >
              {isPlaying ? (
                <>
                  <Pause
                    className="h-3.5 w-3.5 text-teal-accent"
                    aria-hidden="true"
                  />
                  <span>Pause 60fps Loop</span>
                </>
              ) : (
                <>
                  <Play
                    className="h-3.5 w-3.5 text-teal-accent"
                    aria-hidden="true"
                  />
                  <span>Play 60fps Loop</span>
                </>
              )}
            </button>
          </div>

          <div className="mt-5 grid grid-cols-1 items-stretch gap-6 lg:grid-cols-12">
            {/* Left Video Viewport */}
            <div className="lg:col-span-8">
              <div className="frame-crosshair overflow-hidden rounded-lg border border-border-strong bg-canvas shadow-2xl">
                <div className="flex items-center justify-between border-b border-border-subtle bg-surface-elevated/80 px-4 py-2.5 font-mono text-xs">
                  <div className="flex items-center gap-2 text-fg">
                    <Film
                      className="h-3.5 w-3.5 text-teal-accent"
                      aria-hidden="true"
                    />
                    <span className="truncate">{activeClip.command}</span>
                  </div>
                  <span className="chip-teal rounded-sm px-2 py-0.5 text-[10px]">
                    {activeClip.badge}
                  </span>
                </div>

                <video
                  ref={videoRef}
                  poster={activeClip.posterSrc}
                  muted
                  loop
                  playsInline
                  preload="metadata"
                  aria-label={activeClip.title}
                  className="aspect-video w-full bg-[#09090B] object-cover"
                >
                  <source src={activeClip.webmSrc} type="video/webm" />
                  <source src={activeClip.mp4Src} type="video/mp4" />
                  Your browser does not support embedded HTML5 video.
                </video>
              </div>
            </div>

            {/* Right Telemetry & Provenance Card */}
            <div className="flex flex-col justify-between rounded-lg border border-border-strong bg-surface p-6 lg:col-span-4">
              <div>
                <span className="chip-neutral rounded-sm px-2.5 py-1">
                  EMPIRICAL RUNTIME TRACE
                </span>
                <h3 className="mt-4 text-xl font-bold text-fg">
                  {activeClip.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-fg-muted">
                  {activeClip.subtitle}
                </p>
              </div>

              <dl className="mt-6 space-y-3 border-t border-border-subtle pt-5 font-mono text-xs">
                {activeClip.metrics.map((m) => (
                  <div
                    key={m.label}
                    className="flex items-center justify-between gap-2 rounded-sm border border-border-subtle bg-canvas px-3 py-2.5"
                  >
                    <dt className="text-fg-muted">{m.label}</dt>
                    <dd className="font-semibold text-teal-accent">{m.value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </Tabs.Root>
      </div>
    </section>
  );
}
