import type { Metadata } from "next";
import "./globals.css";
import RuntimeBeacon from "@/components/runtime-beacon";

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
        {children}
      </body>
    </html>
  );
}
