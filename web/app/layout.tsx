import type { Metadata } from "next";
import "./globals.css";

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
      <body className="antialiased">{children}</body>
    </html>
  );
}
