import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { Analytics } from "@vercel/analytics/react";
import "./globals.css";
import { ThemeProvider } from "@/components/layout/ThemeProvider";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { SITE_URL } from "@/lib/utils";

const inter = localFont({
  src: "../fonts/inter-latin-wght.woff2",
  variable: "--font-inter",
  display: "swap",
  weight: "100 900",
});

const jetbrainsMono = localFont({
  src: "../fonts/jetbrains-mono-latin-wght.woff2",
  variable: "--font-jetbrains-mono",
  display: "swap",
  weight: "100 800",
});

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#09090B" },
    { media: "(prefers-color-scheme: light)", color: "#FAFAFA" },
  ],
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Keelway — Sovereign Hybrid AI & Agent Control Plane",
    template: "%s · Keelway",
  },
  description:
    "Run open-weight OpenCore models locally alongside governed commercial Frontier APIs under one unified API. Deterministic 4D routing, human approval gates, and hash-chained execution proofs.",
  alternates: {
    canonical: "/",
    types: {
      "application/rss+xml": "/feed.xml",
    },
  },
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/favicon.svg",
  },
  openGraph: {
    title: "Keelway — Sovereign Hybrid AI & Agent Control Plane",
    description:
      "OpenCore open-weight models + Frontier commercial APIs + approval-gated agents under one verifiable control plane.",
    url: SITE_URL,
    siteName: "Keelway",
    images: [
      {
        url: "/og-image.jpg",
        width: 1200,
        height: 630,
        alt: "Keelway Hybrid AI Platform — OpenCore Weights, 4D Routing, and Hash-Chained Agent Governance",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Keelway — Sovereign Hybrid AI & Agent Control Plane",
    description:
      "Run OpenCore weights locally and route to Frontier APIs only under your own cryptographic governance rules.",
    images: ["/og-image.jpg"],
  },
};

const jsonLdSchema = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      name: "Keelway",
      url: SITE_URL,
      logo: `${SITE_URL}/favicon.svg`,
    },
    {
      "@type": "SoftwareApplication",
      name: "Keelway Hybrid AI Platform",
      applicationCategory: "DeveloperApplication",
      operatingSystem: "macOS, Linux, Windows, Docker",
      license: "https://www.apache.org/licenses/LICENSE-2.0",
      offers: {
        "@type": "Offer",
        price: "0",
        priceCurrency: "USD",
      },
      description:
        "Model-agnostic Hybrid AI Platform unifying local OpenCore open-weight models, commercial Frontier APIs, deterministic 4D routing, and hash-chained agent governance.",
    },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      data-theme="dark"
      data-scroll-behavior="smooth"
      suppressHydrationWarning
      className={`${inter.variable} ${jetbrainsMono.variable}`}
    >
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLdSchema) }}
        />
      </head>
      <body className="min-h-screen flex flex-col font-sans bg-canvas text-fg antialiased">
        <a href="#main-content" className="skip-link">
          Skip to main content
        </a>
        <ThemeProvider>
          <Header />
          <CommandPalette />
          <main id="main-content" className="flex-1">
            {children}
          </main>
          <Footer />
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  );
}
