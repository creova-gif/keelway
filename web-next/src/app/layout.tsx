import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { SITE_URL } from "@/lib/utils";
import { SiteHeader } from "@/components/site/header";
import { SiteFooter } from "@/components/site/footer";

const inter = localFont({
  src: "../fonts/inter-latin-wght.woff2",
  variable: "--font-inter",
  display: "swap",
});

const jbMono = localFont({
  src: "../fonts/jetbrains-mono-latin-wght.woff2",
  variable: "--font-jbmono",
  display: "swap",
});

export const viewport: Viewport = {
  themeColor: "#08090A",
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Keelway — Sovereign Agent Platform",
    template: "%s · Keelway",
  },
  description:
    "Agents that answer to you. Local inference, governed cloud routing, and a signed receipt for every action. Apache-2.0 open core from Sorvex Labs.",
  alternates: { types: { "application/rss+xml": "/feed.xml" } },
  manifest: "/manifest.webmanifest",
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: "Keelway — Sovereign Agent Platform",
    description:
      "Local inference. Governed cloud routing. A signed receipt for every action.",
    url: SITE_URL,
    siteName: "Keelway",
    images: [{ url: "/og-image.jpg", width: 1200, height: 630 }],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jbMono.variable}`}>
      <body className="flex min-h-screen flex-col bg-canvas font-sans antialiased">
        <SiteHeader />
        <div className="flex flex-1 flex-col">{children}</div>
        <SiteFooter />
      </body>
    </html>
  );
}
