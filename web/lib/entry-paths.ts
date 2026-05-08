export type EntryPathSurface =
  | "home-ground"
  | "come-in-explore"
  | "come-in-doors";

export type EntryPathKind =
  | "land-design-draft"
  | "community-living-example"
  | "care-institution"
  | "hospital";

export type EntryPathAudience =
  | "agent"
  | "developer"
  | "land-steward"
  | "visitor";

export type EntryPathTone = "amber" | "emerald";

export interface EntrySurfaceCopy {
  eyebrow: string;
  title: string;
  body: string;
  cta?: string;
  eyebrowKey?: string;
  titleKey?: string;
  bodyKey?: string;
}

export interface EntryPath {
  id: string;
  href: string;
  kind: EntryPathKind;
  audiences: EntryPathAudience[];
  excludedKinds: EntryPathKind[];
  surfaces: Partial<Record<EntryPathSurface, EntrySurfaceCopy>>;
  tone: EntryPathTone;
}

export const ENTRY_PATHS: EntryPath[] = [
  {
    id: "bali-living-compound",
    href: "/silence/built",
    kind: "land-design-draft",
    audiences: ["land-steward", "developer", "agent", "visitor"],
    excludedKinds: ["hospital", "care-institution"],
    tone: "emerald",
    surfaces: {
      "home-ground": {
        eyebrow: "Bali living compound",
        title: "Brahmavihara Living Compound",
        body:
          "A direct doorway for land stewards into the Bali compound proposal: source sketch, climate logic, shared rooms, private nests, materials, and the next buildable packet.",
        cta: "Walk through /silence/built ->",
      },
      "come-in-explore": {
        eyebrow: "Meet the land draft",
        title: "Walk straight into the Bali living compound proposal.",
        body:
          "This is the path for land stewards: the Brahmavihara sketch, central council garden, corner nests, shared rooms, climate care, and the next buildable packet.",
      },
      "come-in-doors": {
        eyebrow: "Where this touches land",
        title: "/silence/built - the Bali living compound draft",
        body:
          "A direct path for land stewards into the compound proposal: source sketch, council garden, corner nests, shared rooms, climate logic, materials, and next buildable packet.",
        eyebrowKey: "comeIn.doorBuiltEyebrow",
        titleKey: "comeIn.doorBuiltLabel",
        bodyKey: "comeIn.doorBuiltBody",
      },
    },
  },
];

export function getEntryPathsForSurface(surface: EntryPathSurface): EntryPath[] {
  return ENTRY_PATHS.filter((entry) => entry.surfaces[surface]);
}

export function getEntryPathForSurface(
  id: string,
  surface: EntryPathSurface,
): { entry: EntryPath; copy: EntrySurfaceCopy } | undefined {
  const entry = ENTRY_PATHS.find((candidate) => candidate.id === id);
  const copy = entry?.surfaces[surface];
  return entry && copy ? { entry, copy } : undefined;
}
