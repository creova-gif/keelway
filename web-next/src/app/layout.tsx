import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

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

export const metadata: Metadata = {
  title: "Keelway",
  description: "The sovereign AI developer platform.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jbMono.variable}`}>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
