// Contributions route layout — owns server-side metadata for the list page so
// shares to Slack/Twitter/Discord/iMessage produce a real card with hero
// image, title and lede instead of the generic site card.

import type { Metadata } from "next";
import { createTranslator } from "@/lib/i18n";
import { DEFAULT_LOCALE } from "@/lib/locales";
import { loadPublicWebConfig } from "@/lib/app-config";

const t = createTranslator(DEFAULT_LOCALE);
const WEB_UI = loadPublicWebConfig().webUiBaseUrl;
const HERO = "/visuals/04-vitality.png";
const TITLE = `${t("contributions.title")} — Coherence Network`;
const DESCRIPTION = t("contributions.lede");

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    url: `${WEB_UI}/contributions`,
    images: [{ url: HERO }],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
    images: [HERO],
  },
};

export default function ContributionsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
