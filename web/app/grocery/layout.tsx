// The ledger's own identity when it is added to a phone's home screen.
//
// The site manifest opens /feed under the name "Coherence". A manager who
// added this ledger to her home screen would tap a Coherence icon and land in
// the network's feed instead of the book she keeps — so the route names itself,
// in the language it is used in, and starts where it is used.
import type { Metadata } from "next";

export const metadata: Metadata = {
  // Absolute: the site template would append "| Coherence Network" to the
  // window title of a ledger that is only ever this one thing.
  title: { absolute: "Hati · Belanja" },
  description: "Buku belanja Hati Suci — satu angka, satu ketuk.",
  manifest: "/belanja.webmanifest",
  applicationName: "Hati · Belanja",
  appleWebApp: {
    capable: true,
    title: "Belanja",
    statusBarStyle: "black-translucent",
  },
};

export default function GroceryLayout({ children }: { children: React.ReactNode }) {
  return children;
}
