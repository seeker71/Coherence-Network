import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";

import { resolveRequestLocale } from "@/lib/request-locale";

import {
  formatPresenceCopy,
  getPresenceWalk,
  getPresenceWalkPageCopy,
  getPresenceWalkSupportingSections,
  getPresenceWalks,
  SUPPORTING_ICONS,
} from "../data";
import { getPresenceNodesByKind } from "../nodes";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ kind: string }>;
}): Promise<Metadata> {
  const { kind } = await params;
  const lang = await resolveRequestLocale();
  const copy = getPresenceWalkPageCopy(lang);
  const walk = getPresenceWalk(kind, lang);
  if (!walk) return { title: copy.metadataFallbackTitle };
  return {
    title: formatPresenceCopy(copy.metadataTitleTemplate, {
      label: walk.label,
    }),
    description: walk.voice,
  };
}

export default async function PresenceWalkKindPage({
  params,
}: {
  params: Promise<{ kind: string }>;
}) {
  const { kind } = await params;
  const lang = await resolveRequestLocale();
  const copy = getPresenceWalkPageCopy(lang);
  const walk = getPresenceWalk(kind, lang);
  if (!walk) notFound();

  const Icon = walk.Icon;
  const nodes = getPresenceNodesByKind(walk.kind, lang);
  const walks = getPresenceWalks(lang);
  const supportingSections = getPresenceWalkSupportingSections(lang);

  return (
    <main className="min-h-screen bg-stone-950 text-stone-50">
      <section className="relative min-h-[calc(100vh-5.5rem)] overflow-hidden">
        <Image
          src={walk.image}
          alt=""
          fill
          priority
          sizes="100vw"
          className="object-cover"
        />
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(10,10,9,0.94)_0%,rgba(10,10,9,0.72)_42%,rgba(10,10,9,0.24)_100%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(0deg,rgba(10,10,9,0.96)_0%,rgba(10,10,9,0.1)_42%,rgba(10,10,9,0.52)_100%)]" />

        <div className="relative z-10 mx-auto flex min-h-[calc(100vh-5.5rem)] max-w-6xl flex-col px-4 py-8 sm:px-6 lg:px-8">
          <nav
            className="flex flex-wrap items-center gap-2 text-xs"
            aria-label={copy.navAriaLabel}
          >
            {walks.map((item) => (
              <Link
                key={item.kind}
                href={`/presence-walk/${item.kind}`}
                className={`rounded-full border px-3 py-1.5 transition-colors ${
                  item.kind === walk.kind
                    ? "border-white/40 bg-white/15 text-white"
                    : "border-white/15 bg-stone-950/25 text-stone-300 hover:border-white/35 hover:bg-white/10"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="grid flex-1 items-center gap-8 py-8 lg:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
            <div className="max-w-3xl space-y-5">
              <div className="flex items-center gap-3">
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-white/20 bg-stone-950/40">
                  <Icon className={`h-5 w-5 ${walk.accent}`} />
                </span>
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${walk.accent}`}>
                    {formatPresenceCopy(copy.presenceEyebrowTemplate, {
                      label: walk.label,
                    })}
                  </p>
                  <p className="text-xs text-stone-400">
                    {formatPresenceCopy(copy.nodeTypeTemplate, {
                      nodeType: walk.nodeType,
                    })}
                  </p>
                </div>
              </div>

              <h1 className="max-w-4xl text-4xl font-light leading-tight tracking-tight text-white sm:text-5xl lg:text-6xl">
                {walk.title}
              </h1>
              <p className="max-w-2xl text-lg leading-relaxed text-stone-200 sm:text-xl">
                {walk.voice}
              </p>

              <div className="flex flex-wrap gap-3 pt-2">
                <Link
                  href={walk.directoryHref}
                  className="rounded-md bg-white px-4 py-2 text-sm font-medium text-stone-950 transition-opacity hover:opacity-90"
                >
                  {copy.directoryCta}
                </Link>
                <Link
                  href={walk.conceptHref}
                  className="rounded-md border border-white/25 bg-stone-950/30 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-white/10"
                >
                  {copy.conceptCta}
                </Link>
              </div>
            </div>

            <div className="space-y-4 border-l border-white/15 pl-0 lg:pl-7">
              {supportingSections.map((item) => {
                const SupportingIcon = SUPPORTING_ICONS[item.icon];
                const color = presenceWalkSectionColor(item.color, walk);
                return (
                <section key={item.label} className="space-y-2">
                  <div className="flex items-center gap-2">
                    <SupportingIcon className={`h-4 w-4 ${color}`} />
                    <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-300">
                      {item.label}
                    </h2>
                  </div>
                  <p className="max-w-xl text-sm leading-relaxed text-stone-300">
                    {walk[item.field]}
                  </p>
                </section>
                );
              })}

              <section className="pt-4">
                <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-400">
                  {copy.visualWhyLabel}
                </h2>
                <p className="mt-2 max-w-xl text-sm leading-relaxed text-stone-200">
                  {walk.visualWhy}
                </p>
              </section>
            </div>
          </div>
        </div>
      </section>

      <section className="border-t border-white/10 bg-stone-950 px-4 py-12 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${walk.accent}`}>
                {formatPresenceCopy(copy.namedPresencesLabelTemplate, {
                  labelLower: walk.label.toLowerCase(),
                })}
              </p>
              <h2 className="mt-2 text-2xl font-light text-white sm:text-3xl">
                {copy.namedPresencesHeading}
              </h2>
            </div>
            <p className="max-w-xl text-sm leading-relaxed text-stone-400">
              {copy.namedPresencesDescription}
            </p>
          </div>

          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {nodes.map((node) => (
              <Link
                key={node.slug}
                href={`/presence-walk/node/${node.slug}`}
                className="group min-h-56 overflow-hidden rounded-md border border-white/10 bg-stone-900/70 transition-colors hover:border-white/30"
              >
                <div className="relative h-full min-h-56">
                  <Image
                    src={node.image}
                    alt=""
                    fill
                    sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
                    className="object-cover opacity-45 transition-opacity group-hover:opacity-60"
                  />
                  <div className="absolute inset-0 bg-[linear-gradient(0deg,rgba(12,10,9,0.96)_0%,rgba(12,10,9,0.48)_58%,rgba(12,10,9,0.22)_100%)]" />
                  <div className="relative z-10 flex min-h-56 flex-col justify-end p-5">
                    <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${walk.accent}`}>
                      {formatPresenceCopy(copy.nodeCardMetaTemplate, {
                        nodeType: node.nodeType,
                        role: node.role,
                      })}
                    </p>
                    <h3 className="mt-2 text-xl font-medium text-white">{node.name}</h3>
                    <p className="mt-3 line-clamp-3 text-sm leading-relaxed text-stone-300">
                      {node.lens}
                    </p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

function presenceWalkSectionColor(
  color: ReturnType<typeof getPresenceWalkSupportingSections>[number]["color"],
  walk: NonNullable<ReturnType<typeof getPresenceWalk>>,
): string {
  switch (color) {
    case "accent":
      return walk.accent;
    case "secondary":
      return walk.secondary;
    case "neutral":
    default:
      return "text-stone-200";
  }
}
