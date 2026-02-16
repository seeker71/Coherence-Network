import type { Metadata } from "next";
import "./globals.css";
import RuntimeBeacon from "@/components/runtime-beacon";
import SiteHeader from "@/components/site_header";
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
      <body className={`${spaceGrotesk.variable} ${plexMono.variable} antialiased font-sans`}>
        <RuntimeBeacon />
        <SiteHeader />
        {children}
      </body>
    </html>
  );
}
