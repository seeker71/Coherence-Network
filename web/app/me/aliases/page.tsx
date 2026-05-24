// /me/aliases — your cross-instance identity, as your own sovereign claim.
//
// The contributor holds an ed25519 keypair. The private key is generated
// in the browser, shown ONCE, and never leaves the device. The instance
// only ever sees the public half and the signature proving possession.
// Aliases on peer instances appear here as recognitions THIS instance
// records when peers share the same pubkey — not as anything the
// instance grants or controls.

import type { Metadata } from "next";
import { cookies } from "next/headers";

import { createTranslator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import { MeAliasesClient } from "./MeAliasesClient";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Your aliases — Coherence Network",
  description:
    "Your pubkey, your aliases across peer instances. Cryptographic possession, never granted by anyone.",
};

export default async function MeAliasesPage({
  searchParams,
}: {
  searchParams: Promise<{ contributor_id?: string }>;
}) {
  const params = await searchParams;
  const cookieLocale = (await cookies()).get("NEXT_LOCALE")?.value;
  const lang: LocaleCode = isSupportedLocale(cookieLocale) ? cookieLocale : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  const initialContributorId = params.contributor_id?.trim() || "";

  return (
    <main className="max-w-2xl mx-auto px-4 py-8">
      <header className="mb-6 space-y-2">
        <h1 className="text-2xl md:text-3xl font-light text-foreground">
          {t("identity.heading")}
        </h1>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {t("identity.lede")}
        </p>
      </header>
      <MeAliasesClient
        initialContributorId={initialContributorId}
        labels={{
          contributorIdLabel: t("identity.contributorIdLabel"),
          contributorIdPlaceholder: t("identity.contributorIdPlaceholder"),
          contributorIdHelp: t("identity.contributorIdHelp"),
          loading: t("identity.loading"),
          noPubkey: t("identity.noPubkey"),
          yourPubkey: t("identity.yourPubkey"),
          generateClaim: t("identity.generateClaim"),
          generating: t("identity.generating"),
          claimSuccess: t("identity.claimSuccess"),
          privateKeyOnce: t("identity.privateKeyOnce"),
          privateKeyWarning: t("identity.privateKeyWarning"),
          privateKeyAcknowledge: t("identity.privateKeyAcknowledge"),
          aliasesHeading: t("identity.aliasesHeading"),
          aliasesEmpty: t("identity.aliasesEmpty"),
          aliasPeer: t("identity.aliasPeer"),
          aliasAs: t("identity.aliasAs"),
          aliasRecognizedAt: t("identity.aliasRecognizedAt"),
          rotateHeading: t("identity.rotateHeading"),
          rotateLede: t("identity.rotateLede"),
          rotateWarning: t("identity.rotateWarning"),
          rotateOldKeyLabel: t("identity.rotateOldKeyLabel"),
          rotateOldKeyPlaceholder: t("identity.rotateOldKeyPlaceholder"),
          rotateAction: t("identity.rotateAction"),
          rotateInProgress: t("identity.rotateInProgress"),
          rotateSuccess: t("identity.rotateSuccess"),
          errorPrefix: t("identity.errorPrefix"),
          sovereigntyNote: t("identity.sovereigntyNote"),
        }}
      />
    </main>
  );
}
