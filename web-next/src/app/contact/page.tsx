import type { Metadata } from "next";
import { ContactForm } from "@/components/site/contact-form";

export const metadata: Metadata = {
  alternates: { canonical: "/contact" },
  title: "Contact — Keelway",
  description: "Talk to a human — Enterprise Sovereign VPC, BYOM rollouts, or a hard question about the tape.",
};

export default function ContactPage() {
  return (
    <main className="mx-auto max-w-md px-5 py-16 sm:px-8 sm:py-24">
      <h1 className="text-4xl font-semibold tracking-tight text-fg">Talk to a human.</h1>
      <p className="mt-4 text-sm leading-6 text-fg-muted">
        Enterprise, Sovereign VPC, or a hard question about the tape.
      </p>
      <ContactForm />
    </main>
  );
}
