import type { Metadata } from "next";
import "./globals.css";
import RuntimeBeacon from "@/components/runtime-beacon";
import PageLineageBanner from "@/components/page-lineage-banner";

export const metadata: Metadata = {
  title: "Coherence Network",
  description: "Open Source Contribution Intelligence",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <RuntimeBeacon />
        <PageLineageBanner />
        {children}
      </body>
    </html>
  );
}
