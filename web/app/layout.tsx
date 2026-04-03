import type { Metadata } from "next";
import "./globals.css";
import RuntimeBeacon from "@/components/runtime-beacon";

import SiteHeader from "@/components/site_header";
import LiveUpdatesController from "@/components/live_updates_controller";
import { ThemeProvider } from "@/components/theme-provider";
import { ExpertModeProvider } from "@/components/expert-mode-context";
import { MobileBottomNav } from "@/components/mobile-bottom-nav";
import { loadPublicWebConfig } from "@/lib/app-config";
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
  const publicConfig = loadPublicWebConfig();
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/*
          Anti-flash script — Spec 165.
          Runs synchronously before paint to apply saved theme class.
          Must be inline (not deferred) to avoid FOUC.
        */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('coherence-theme');var d=document.documentElement;if(t==='light'){d.classList.add('light');d.style.colorScheme='light';}else if(t==='dark'||!t||t==='system'){var sys=window.matchMedia('(prefers-color-scheme: light)').matches;if(t==='light'||(t!=='dark'&&sys)){d.classList.add('light');d.style.colorScheme='light';}else{d.classList.add('dark');d.style.colorScheme='dark';}}}catch(e){}})();`,
          }}
        />
        <script
          dangerouslySetInnerHTML={{
            __html: `window.__COHERENCE_PUBLIC_CONFIG__=${JSON.stringify(publicConfig)};`,
          }}
        />
      </head>
      <body className={`${spaceGrotesk.variable} ${plexMono.variable} antialiased font-sans`}>
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:rounded focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
        >
          Skip to main content
        </a>
        <RuntimeBeacon />
        <ThemeProvider>
          <ExpertModeProvider>
            <SiteHeader />
            <LiveUpdatesController />
            <main id="main-content" className="pb-16 md:pb-0">
              {children}
            </main>
            <MobileBottomNav />
          </ExpertModeProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
