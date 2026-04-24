import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { resolveRequestLocale } from "@/lib/request-locale";

import { getPresenceWalkIndexCopy } from "./data";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const copy = getPresenceWalkIndexCopy(await resolveRequestLocale());
  return {
    title: copy.metadataTitle,
    description: copy.metadataDescription,
  };
}

export default async function PresenceWalkIndexPage() {
  const copy = getPresenceWalkIndexCopy(await resolveRequestLocale());
  redirect(`/presence-walk/${copy.redirectKind}`);
}
