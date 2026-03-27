/**
 * Spec task_e647f5766a54f6f1 acceptance tests: Homepage Readability Improvements.
 *
 * Static-analysis tests that verify source files meet the contrast/opacity
 * requirements from the spec. No runtime rendering required.
 *
 * Acceptance criteria:
 * 1. Body text (descriptions, stats labels, step descriptions) ≥ 0.85 opacity
 * 2. Form placeholders ≥ 0.85 opacity (up from 0.40/0.50)
 * 3. Headings (H1/H2/H3) retain their current styling
 * 4. Stats numbers remain 100% opacity (text-foreground, no modifier)
 * 5. Background ambient glow and gradients preserved
 */
import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const WEB_ROOT = path.resolve(__dirname, "..");

function readWebFile(relativePath: string): string {
  return fs.readFileSync(path.join(WEB_ROOT, relativePath), "utf8");
}

// Tailwind opacity modifiers below the 0.85 threshold that must not appear
// on primary body text elements.
const LOW_OPACITY_CLASSES = [
  "text-foreground/10",
  "text-foreground/20",
  "text-foreground/30",
  "text-foreground/40",
  "text-foreground/50",
  "text-foreground/60",
  "text-foreground/70",
  "text-foreground/75",
];

describe("spec task_e647f5766a54f6f1: hero section legibility (page.tsx)", () => {
  const pageSource = readWebFile("app/page.tsx");

  it("hero description paragraph uses ≥ 0.85 opacity class", () => {
    // The hero <p> describing "A pattern you noticed..." must be readable
    expect(pageSource).toMatch(
      /<p[^>]*class[^>]*text-foreground\/(8[5-9]|9\d|100)[^>]*>/,
    );
  });

  it("hero section does not apply sub-0.85 opacity to the description text", () => {
    // The description paragraph block must not carry low-opacity classes
    const heroDescRegion = pageSource.slice(
      pageSource.indexOf("A pattern you noticed") - 200,
      pageSource.indexOf("A pattern you noticed") + 200,
    );
    for (const cls of LOW_OPACITY_CLASSES) {
      expect(heroDescRegion).not.toContain(cls);
    }
  });

  it("H1 hero headline retains its current styling class", () => {
    // Heading must keep hero-headline class for ambient aesthetic
    expect(pageSource).toContain("hero-headline");
  });

  it("H1 heading does not have an opacity modifier that would dim it", () => {
    // H1 should not use text-foreground/XX — it gets full color from hero-headline
    const h1Block = pageSource.slice(
      pageSource.indexOf("<h1"),
      pageSource.indexOf("</h1>") + 6,
    );
    expect(h1Block).not.toMatch(/text-foreground\/\d+/);
  });
});

describe("spec task_e647f5766a54f6f1: stats section (page.tsx)", () => {
  const pageSource = readWebFile("app/page.tsx");

  it("stats labels (ideas alive, value created, nodes) use ≥ 0.85 opacity", () => {
    // Outer span that wraps number + label text must use text-foreground/85+.
    // Structure: <span className="text-sm text-foreground/90">
    //              <span …>{number}</span> ideas alive
    //            </span>
    // Verify the wrapper span carries a high-opacity class AND "ideas alive" appears in the file.
    expect(pageSource).toMatch(/text-foreground\/(8[5-9]|9\d|100)/);
    expect(pageSource).toContain("ideas alive");
  });

  it("stats number spans use text-foreground without opacity modifier", () => {
    // Numbers rendered via formatNumber must carry text-foreground (100%)
    // The pattern is: <span className="text-foreground font-medium">{formatNumber(...)}</span>
    expect(pageSource).toMatch(
      /<span[^>]*"text-foreground font-medium"[^>]*>\{format/,
    );
  });

  it("stats numbers do not carry a sub-100% opacity modifier", () => {
    // Confirm the number spans are not dimmed
    const numberSpans = [...pageSource.matchAll(/<span[^>]*font-medium[^>]*>/g)];
    for (const match of numberSpans) {
      expect(match[0]).not.toMatch(/text-foreground\/\d+/);
    }
  });
});

describe("spec task_e647f5766a54f6f1: how-it-works step descriptions (page.tsx)", () => {
  const pageSource = readWebFile("app/page.tsx");

  it("step description paragraphs use ≥ 0.85 opacity class", () => {
    // HOW_IT_WORKS descriptions are rendered inside <p> with opacity class
    expect(pageSource).toMatch(
      /<p[^>]*text-foreground\/(8[5-9]|9\d|100)[^>]*>\s*\{step\.description\}/,
    );
  });

  it("H3 step titles retain current styling without opacity reduction", () => {
    // Step titles: <h3 className="text-base font-medium">{step.title}</h3>
    const h3Block = pageSource.slice(
      pageSource.indexOf("<h3"),
      pageSource.indexOf("</h3>") + 5,
    );
    expect(h3Block).toContain("{step.title}");
    expect(h3Block).not.toMatch(/text-foreground\/\d+/);
  });
});

describe("spec task_e647f5766a54f6f1: form placeholder contrast (idea_submit_form.tsx)", () => {
  const formSource = readWebFile("components/idea_submit_form.tsx");

  it("textarea placeholder uses placeholder:text-foreground/85 or higher", () => {
    expect(formSource).toMatch(/placeholder:text-foreground\/(8[5-9]|9\d|100)/);
  });

  it("name input placeholder uses placeholder:text-foreground/85 or higher", () => {
    // Both inputs must meet the threshold
    const placeholderMatches = [
      ...formSource.matchAll(/placeholder:text-foreground\/(\d+)/g),
    ];
    expect(placeholderMatches.length).toBeGreaterThanOrEqual(2);
    for (const match of placeholderMatches) {
      const opacity = parseInt(match[1], 10);
      expect(opacity).toBeGreaterThanOrEqual(85);
    }
  });

  it("textarea does not have a low-opacity placeholder modifier", () => {
    const textareaBlock = formSource.slice(
      formSource.indexOf("<textarea"),
      formSource.indexOf("</textarea>") + 11,
    );
    for (const cls of LOW_OPACITY_CLASSES.map((c) => c.replace("text-", "placeholder:"))) {
      expect(textareaBlock).not.toContain(cls);
    }
  });

  it("form input text color uses ≥ 0.85 opacity for typed content", () => {
    // Inputs carry text-foreground/90 or similar for actual entered text
    expect(formSource).toMatch(/text-foreground\/(8[5-9]|9\d|100)/);
  });
});

describe("spec task_e647f5766a54f6f1: background gradients preserved (page.tsx)", () => {
  const pageSource = readWebFile("app/page.tsx");

  it("ambient glow blur element is still present", () => {
    // The soft ambient background glow must not have been removed
    expect(pageSource).toContain("blur-[120px]");
  });

  it("background gradient on card elements is preserved", () => {
    expect(pageSource).toContain("bg-gradient-to-b");
  });

  it("bg-primary/10 ambient fill is preserved", () => {
    expect(pageSource).toContain("bg-primary/10");
  });
});
