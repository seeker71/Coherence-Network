/** Bounded reader and link rewriter for the repository's public stewardship corpus. */
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { basename, dirname, join, posix } from "node:path";

export type StewardshipDocument = {
  body: string;
  sourcePath: string;
  title: string;
};

export type StewardshipDirectoryEntry = {
  href: string;
  title: string;
};

export type StewardshipPage =
  | ({ kind: "document" } & StewardshipDocument)
  | { entries: StewardshipDirectoryEntry[]; kind: "directory"; title: string };

const SAFE_SEGMENT = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;

function rootDirectory(): string | null {
  const candidates = [
    join(process.cwd(), "docs", "stewardship"),
    join(process.cwd(), "..", "docs", "stewardship"),
  ];
  return candidates.find((candidate) => existsSync(candidate)) ?? null;
}

function safeSegments(segments: string[]): boolean {
  return segments.every(
    (segment) =>
      segment !== "." && segment !== ".." && SAFE_SEGMENT.test(segment),
  );
}

function stripFrontmatter(markdown: string): string {
  if (!markdown.startsWith("---\n")) return markdown;
  const end = markdown.indexOf("\n---\n", 4);
  return end === -1 ? markdown : markdown.slice(end + 5);
}

function titleFromMarkdown(markdown: string, fallback: string): string {
  return /^#\s+(.+)$/m.exec(markdown)?.[1]?.trim() || fallback;
}

function titleFromPath(path: string): string {
  const leaf = basename(path).replace(/\.md$/i, "");
  return leaf
    .split("-")
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

export function stewardshipHrefForSource(sourcePath: string): string {
  const withoutReadme = sourcePath.replace(/(?:^|\/)README\.md$/i, "");
  const withoutExtension = withoutReadme.replace(/\.md$/i, "").replace(/\/+$/, "");
  const suffix = withoutExtension ? `/${withoutExtension}` : "";
  return `/stewardship${suffix}`;
}

export function rewriteStewardshipLinks(
  markdown: string,
  sourcePath: string,
): string {
  return markdown.replace(/\]\(([^)]+)\)/g, (whole, href: string) => {
    if (
      href.startsWith("/") ||
      href.startsWith("#") ||
      /^[a-z][a-z0-9+.-]*:/i.test(href)
    ) {
      return whole;
    }

    const hashAt = href.indexOf("#");
    const pathPart = hashAt === -1 ? href : href.slice(0, hashAt);
    const hash = hashAt === -1 ? "" : href.slice(hashAt);
    const resolved = posix.normalize(posix.join(dirname(sourcePath), pathPart));
    if (resolved === ".." || resolved.startsWith("../")) return whole;
    return `](${stewardshipHrefForSource(resolved)}${hash})`;
  });
}

function documentAt(root: string, sourcePath: string): StewardshipDocument | null {
  const fullPath = join(
    /*turbopackIgnore: true*/ root,
    ...sourcePath.split("/"),
  );
  if (!existsSync(fullPath) || !statSync(fullPath).isFile()) return null;
  const markdown = stripFrontmatter(readFileSync(fullPath, "utf8")).trim();
  const title = titleFromMarkdown(markdown, titleFromPath(sourcePath));
  const body = markdown.replace(/^#\s+.+\n?/, "").trim();
  return {
    body: rewriteStewardshipLinks(body, sourcePath),
    sourcePath,
    title,
  };
}

export function loadStewardshipPage(segments: string[]): StewardshipPage | null {
  if (!safeSegments(segments)) return null;
  const root = rootDirectory();
  if (!root) return null;
  const relativePath = segments.join("/");
  const candidates = relativePath
    ? [`${relativePath}.md`, `${relativePath}/README.md`]
    : ["README.md"];
  for (const sourcePath of candidates) {
    const document = documentAt(root, sourcePath);
    if (document) return { kind: "document", ...document };
  }

  const directory = join(/*turbopackIgnore: true*/ root, ...segments);
  if (!existsSync(directory) || !statSync(directory).isDirectory()) return null;
  const entries = readdirSync(directory)
    .flatMap((name): StewardshipDirectoryEntry[] => {
      const child = join(/*turbopackIgnore: true*/ directory, name);
      if (statSync(child).isDirectory()) {
        return [
          {
            href: stewardshipHrefForSource([...segments, name].join("/")),
            title: titleFromPath(name),
          },
        ];
      }
      if (!name.endsWith(".md") || name === "README.md") return [];
      const sourcePath = [...segments, name].join("/");
      const markdown = stripFrontmatter(readFileSync(child, "utf8"));
      return [
        {
          href: stewardshipHrefForSource(sourcePath),
          title: titleFromMarkdown(markdown, titleFromPath(name)),
        },
      ];
    })
    .sort((left, right) => left.title.localeCompare(right.title));

  return {
    entries,
    kind: "directory",
    title: segments.length
      ? titleFromPath(segments.at(-1) || "stewardship")
      : "Stewardship",
  };
}
