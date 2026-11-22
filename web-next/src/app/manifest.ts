import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Keelway — Sovereign Agent Platform",
    short_name: "Keelway",
    description:
      "Agents that answer to you. Local inference, governed cloud routing, and a signed receipt for every action.",
    start_url: "/",
    display: "standalone",
    background_color: "#08090A",
    theme_color: "#08090A",
    icons: [
      {
        src: "/favicon.svg",
        sizes: "any",
        type: "image/svg+xml",
      },
    ],
  };
}
