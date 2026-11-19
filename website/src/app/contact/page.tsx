import type { Metadata } from "next";
import { ContactForm } from "@/components/site/ContactForm";

export const metadata: Metadata = {
  title: "Contact",
  description: "Talk to a human — Enterprise Sovereign VPC, BYOM rollouts, or a hard question about the tape.",
};

export default function ContactPage() {
  return (
    <div className="mx-auto max-w-md px-5 py-16 sm:px-8 sm:py-24">
      <h1 className="kw-h1">Talk to a human.</h1>
      <p className="kw-body mt-4">
        Enterprise, Sovereign VPC, or a hard question about the tape.
      </p>
      <ContactForm />
    </div>
  );
}
