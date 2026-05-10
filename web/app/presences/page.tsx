import type { Metadata } from "next";
import PeopleIndexPage, { generateMetadata as peopleGenerateMetadata } from "../people/page";

/**
 * /presences — the directory of every presence the network holds.
 *
 * The same body the /people directory renders, addressed by the more
 * accurate word: presences. Per Urs's directive — *"/people does not
 * sound right for all the things it has underneath, we need a better
 * word"* — the directory holds humans, communities, places,
 * gatherings, practices, and works. "People" is too narrow for that
 * span; "presences" carries each of them honestly.
 *
 * Implementation: thin async wrapper that delegates to PeopleIndexPage
 * so both URLs render the same body without code duplication. /people
 * stays canonical for slug routes (/people/urs etc.); /presences is
 * the preferred URL for the directory itself going forward.
 */

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  return peopleGenerateMetadata();
}

export default async function PresencesIndexPage(props: {
  searchParams: Promise<{
    kind?: string;
    sort?: string;
    with?: string;
    find?: string;
  }>;
}) {
  return PeopleIndexPage(props);
}
