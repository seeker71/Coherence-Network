import type { Metadata } from "next";
import Link from "next/link";
import { cookies } from "next/headers";

import { getApiBase } from "@/lib/api";
import { createTranslator, type Translator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";

// Portfolio page renders all positions held by the current contributor with
// gain/loss and ROI %. Server-rendered. The contributor id comes from the
// NEXT_CONTRIBUTOR cookie (set during onboarding); without it we render an
// invitation to sign in rather than a 500.

export const metadata: Metadata = {
  title: "My investments",
  description: "Positions you hold across ideas. CC put in, CC standing now, ROI alive.",
};

type Position = {
  idea_id: string;
  idea_name: string;
  invested_cc: number;
  current_value_cc: number;
  gain_loss_cc: number;
  roi_pct: number;
  stage: string;
  unlock_pct: number;
  staked_at: string | null;
};

type Portfolio = {
  contributor_id: string;
  summary: {
    total_invested_cc: number;
    total_current_value_cc: number;
    total_gain_loss_cc: number;
    total_positions: number;
    active_positions: number;
  };
  positions: Position[];
};

async function loadPortfolio(contributorId: string): Promise<Portfolio | null> {
  try {
    const API = getApiBase();
    const res = await fetch(
      `${API}/api/contributors/${encodeURIComponent(contributorId)}/investments`,
      { cache: "no-store" },
    );
    if (!res.ok) return null;
    return (await res.json()) as Portfolio;
  } catch {
    return null;
  }
}

function formatCc(amount: number): string {
  return `${amount.toFixed(2)} CC`;
}

function gainTone(amount: number): string {
  if (amount > 0) return "text-emerald-600 dark:text-emerald-400";
  if (amount < 0) return "text-rose-600 dark:text-rose-400";
  return "text-muted-foreground";
}

function SummaryCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1">
      <p className="text-xs uppercase tracking-wider text-muted-foreground/80">{label}</p>
      <p className={`text-lg font-medium ${tone ?? ""}`}>{value}</p>
    </div>
  );
}

function PositionRow({ position, t }: { position: Position; t: Translator }) {
  return (
    <article className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 md:p-5 space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link
          href={`/ideas/${encodeURIComponent(position.idea_id)}`}
          className="font-medium hover:text-primary transition-colors"
        >
          {position.idea_name}
        </Link>
        <span className="text-xs rounded-full border border-border/40 px-2.5 py-0.5 bg-muted/30 text-muted-foreground">
          {position.stage} · {position.unlock_pct}% {t("portfolioInvestments.unlocked")}
        </span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div>
          <p className="text-xs text-muted-foreground/80">
            {t("portfolioInvestments.invested")}
          </p>
          <p className="font-medium">{formatCc(position.invested_cc)}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground/80">
            {t("portfolioInvestments.currentValue")}
          </p>
          <p className="font-medium">{formatCc(position.current_value_cc)}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground/80">
            {t("portfolioInvestments.gainLoss")}
          </p>
          <p className={`font-medium ${gainTone(position.gain_loss_cc)}`}>
            {position.gain_loss_cc >= 0 ? "+" : ""}
            {formatCc(position.gain_loss_cc)}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground/80">
            {t("portfolioInvestments.roi")}
          </p>
          <p className={`font-medium ${gainTone(position.roi_pct)}`}>
            {position.roi_pct >= 0 ? "+" : ""}
            {position.roi_pct.toFixed(1)}%
          </p>
        </div>
      </div>
    </article>
  );
}

export default async function PortfolioInvestmentsPage({
  searchParams,
}: {
  searchParams: Promise<{ contributor?: string }>;
}) {
  const cookieStore = await cookies();
  const cookieLang = cookieStore.get("NEXT_LOCALE")?.value;
  const lang: LocaleCode = isSupportedLocale(cookieLang) ? cookieLang : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  // Contributor id comes from query string (?contributor=alice) or a
  // cookie set during onboarding (cc-contributor-id mirrored server-side).
  const resolved = await searchParams;
  const contributorId =
    resolved.contributor || cookieStore.get("cc-contributor-id")?.value || null;

  if (!contributorId) {
    return (
      <main className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <header>
          <h1 className="text-2xl font-semibold">{t("portfolioInvestments.title")}</h1>
          <p className="text-muted-foreground">{t("portfolioInvestments.signInNeeded")}</p>
        </header>
        <Link
          href="/invest"
          className="inline-block rounded-full bg-primary/10 px-4 py-1.5 text-sm text-primary hover:bg-primary/20"
        >
          {t("portfolioInvestments.gardenLink")}
        </Link>
      </main>
    );
  }

  const portfolio = await loadPortfolio(contributorId);

  if (!portfolio) {
    return (
      <main className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <header>
          <h1 className="text-2xl font-semibold">{t("portfolioInvestments.title")}</h1>
          <p className="text-muted-foreground">{t("portfolioInvestments.loadError")}</p>
        </header>
      </main>
    );
  }

  const { summary, positions } = portfolio;

  return (
    <main className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">{t("portfolioInvestments.title")}</h1>
        <p className="text-sm text-muted-foreground">
          {t("portfolioInvestments.subtitle", { id: contributorId })}
        </p>
      </header>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SummaryCard
          label={t("portfolioInvestments.summaryInvested")}
          value={formatCc(summary.total_invested_cc)}
        />
        <SummaryCard
          label={t("portfolioInvestments.summaryValue")}
          value={formatCc(summary.total_current_value_cc)}
        />
        <SummaryCard
          label={t("portfolioInvestments.summaryGainLoss")}
          value={`${summary.total_gain_loss_cc >= 0 ? "+" : ""}${formatCc(summary.total_gain_loss_cc)}`}
          tone={gainTone(summary.total_gain_loss_cc)}
        />
        <SummaryCard
          label={t("portfolioInvestments.summaryPositions")}
          value={`${summary.active_positions} / ${summary.total_positions}`}
        />
      </section>

      {positions.length === 0 ? (
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-8 text-center space-y-3">
          <p className="text-muted-foreground">{t("portfolioInvestments.emptyState")}</p>
          <Link
            href="/ideas"
            className="inline-block text-primary hover:text-foreground transition-colors underline underline-offset-4"
          >
            {t("portfolioInvestments.browseIdeas")}
          </Link>
        </div>
      ) : (
        <section className="space-y-3">
          {positions.map((p) => (
            <PositionRow key={p.idea_id} position={p} t={t} />
          ))}
        </section>
      )}

      <nav className="py-6 text-center" aria-label="related">
        <Link
          href="/invest"
          className="text-sm text-amber-600 dark:text-amber-400 hover:underline"
        >
          {t("portfolioInvestments.gardenLink")}
        </Link>
      </nav>
    </main>
  );
}
