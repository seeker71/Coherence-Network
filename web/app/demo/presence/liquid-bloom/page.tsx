import type { Metadata } from "next";
import { PresencePage, type PresenceIdentity } from "@/components/presence/PresencePage";

/**
 * /demo/presence/liquid-bloom — hardcoded example to evaluate the
 * presence template against a real identity we all know.
 *
 * Shape matches what the resolver would produce against
 * https://liquidbloom.bandcamp.com — same fields, same types, so
 * what we tune here tunes the live rendering too. The demo lets us
 * iterate on layout / tone / brand-tokens without depending on the
 * live network or external fetches.
 */

export const metadata: Metadata = {
  title: "Liquid Bloom — Coherence Network",
  description: "Downtempo, world bass, and ceremonial electronica.",
};

const LIQUID_BLOOM: PresenceIdentity = {
  id: "contributor:liquid-bloom",
  name: "Liquid Bloom",
  category: "Artist",
  tagline: "Downtempo ceremony — bass as a carrier wave for the sacred.",
  canonical_url: "https://liquidbloom.bandcamp.com",
  provider: "bandcamp",
  image_url: null, // hero falls back to the bandcamp-teal radial
  claimed: false,
  presences: [
    { provider: "bandcamp", url: "https://liquidbloom.bandcamp.com" },
    { provider: "spotify", url: "https://open.spotify.com/artist/liquidbloom" },
    { provider: "youtube", url: "https://www.youtube.com/@liquidbloom" },
    { provider: "soundcloud", url: "https://soundcloud.com/liquidbloom" },
    { provider: "instagram", url: "https://www.instagram.com/liquidbloom/" },
    { provider: "apple-music", url: "https://music.apple.com/artist/liquid-bloom" },
  ],
  creations: [
    {
      kind: "album",
      name: "Deep Roots of the Unknown",
      url: "https://liquidbloom.bandcamp.com/album/deep-roots-of-the-unknown",
    },
    {
      kind: "album",
      name: "Elixir: Sonic Alchemy",
      url: "https://liquidbloom.bandcamp.com/album/elixir-sonic-alchemy",
    },
    {
      kind: "album",
      name: "Return to the Center",
      url: "https://liquidbloom.bandcamp.com/album/return-to-the-center",
    },
    {
      kind: "album",
      name: "Shapeshifter",
      url: "https://liquidbloom.bandcamp.com/album/shapeshifter",
    },
  ],
  inspired_by: [
    { id: "contributor:amani-friend", name: "Amani Friend" },
    { id: "network-org:bloomurian", name: "Bloomurian" },
  ],
};

export default function LiquidBloomDemoPage() {
  return <PresencePage identity={LIQUID_BLOOM} />;
}
