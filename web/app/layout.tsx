import type { Metadata } from "next";
import "./globals.css";
import RuntimeBeacon from "@/components/runtime-beacon";

import SiteHeader from "@/components/site_header";
import LiveUpdatesController from "@/components/live_updates_controller";
import { IBM_Plex_Mono, Space_Grotesk } from "next/font/google";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Coherence Network",
    template: "%s | Coherence Network",
  },
  description: "Ideas deserve to become real. Share what you see, build what matters, and trace every contribution from thought to impact.",
  openGraph: {
    type: "website",
    siteName: "Coherence Network",
    title: "Coherence Network",
    description: "Ideas deserve to become real. Share what you see, build what matters, and trace every contribution from thought to impact.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${spaceGrotesk.variable} ${plexMono.variable} antialiased font-sans`}>
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:rounded focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
        >
          Skip to main content
        </a>
        <RuntimeBeacon />
        <SiteHeader />
        <LiveUpdatesController />
        <main id="main-content">
          {children}
        </main>
      </body>
    </html>
  );
}
