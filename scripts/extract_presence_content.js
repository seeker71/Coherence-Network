#!/usr/bin/env node
/**
 * Extract a static `web/content/people/{slug}/{locale}.tsx`
 * PersonProfileContent object into the structured PresenceContent
 * JSON shape that `docs/presence-content/{slug}.json` carries.
 *
 * The converter parses the TSX via the TypeScript compiler API,
 * locates the `const content: PersonProfileContent = { ... }` literal,
 * and walks each prose slot — turning JSX into markdown so the dynamic
 * route renders the same visual chrome through PersonProfileTemplate.
 *
 * Inline JSX → markdown:
 *   <p>text</p>                         → text (block paragraph)
 *   <Link href="/path">Label</Link>     → [Label](/path)
 *   <a href="https://x">Label</a>       → [Label](https://x)
 *   <em>x</em>                          → *x*
 *   <strong>x</strong>                  → **x**
 *   <code>x</code>                      → `x`
 *   <ul><li>...</li></ul>               → "- item\n- item"
 *   <ol><li>...</li></ol>               → "1. item\n2. item"
 *   <>...</> (fragment)                 → concat children
 *   {" "}                               → space (preserved between JSX runs)
 *
 * Field-by-field flattening:
 *   hero.welcome:                       block markdown (paragraphs)
 *   facts[].value:                      inline markdown (one line)
 *   noteFromBody.body:                  block markdown
 *   articles[].body:                    block markdown
 *   footer:                             block markdown
 *
 * Usage:
 *   node scripts/extract_presence_content.js {slug}
 *   node scripts/extract_presence_content.js {slug} --locale de
 *   node scripts/extract_presence_content.js {slug} --write   # write to docs/presence-content/{slug}.json
 */

const fs = require("fs");
const path = require("path");
const ts = require(path.join(__dirname, "..", "web", "node_modules", "typescript"));

const REPO_ROOT = path.resolve(__dirname, "..");

function usage() {
  console.error("Usage: node scripts/extract_presence_content.js <slug> [--locale en] [--write]");
  process.exit(1);
}

const args = process.argv.slice(2);
if (args.length === 0) usage();
const slug = args[0];
let locale = "en";
let write = false;
for (let i = 1; i < args.length; i++) {
  if (args[i] === "--locale") locale = args[++i];
  else if (args[i] === "--write") write = true;
  else usage();
}

const inputPath = path.join(
  REPO_ROOT,
  "web",
  "content",
  "people",
  slug,
  `${locale}.tsx`,
);
if (!fs.existsSync(inputPath)) {
  console.error(`No file at ${inputPath}`);
  process.exit(2);
}

const source = fs.readFileSync(inputPath, "utf8");
// Re-export shorthand: `export { default } from './en';` — recurse to the real source
const reexport = source.match(/export\s*\{\s*default\s*\}\s*from\s*['"]([^'"]+)['"]/);
let sourceFile;
let actualSource = source;
if (reexport) {
  const target = path.resolve(path.dirname(inputPath), reexport[1] + ".tsx");
  if (fs.existsSync(target)) {
    actualSource = fs.readFileSync(target, "utf8");
  }
}
sourceFile = ts.createSourceFile(
  path.basename(inputPath),
  actualSource,
  ts.ScriptTarget.ES2020,
  true,
  ts.ScriptKind.TSX,
);

/* ── JSX → markdown ─────────────────────────────────────────────── */

function getJsxAttr(node, name) {
  if (!node.attributes) return undefined;
  const attr = node.attributes.properties.find(
    (p) => p.name && p.name.escapedText === name,
  );
  if (!attr) return undefined;
  if (!attr.initializer) return true;
  if (ts.isStringLiteral(attr.initializer)) return attr.initializer.text;
  if (ts.isJsxExpression(attr.initializer) && attr.initializer.expression) {
    const e = attr.initializer.expression;
    if (ts.isStringLiteral(e)) return e.text;
    if (ts.isTemplateExpression(e) || ts.isNoSubstitutionTemplateLiteral(e)) {
      // Approximate template-string concatenation
      return e.getText(sourceFile).slice(1, -1);
    }
    return e.getText(sourceFile);
  }
  return undefined;
}

function getJsxTagName(node) {
  const tag = node.tagName;
  if (ts.isIdentifier(tag)) return tag.text;
  if (ts.isPropertyAccessExpression(tag)) return tag.getText(sourceFile);
  return tag.getText(sourceFile);
}

function inlineFromChildren(children) {
  // Returns inline-markdown string from JSX children
  let out = "";
  for (const child of children) {
    out += inlineFromNode(child);
  }
  // Trim a stray space that often appears between a closing tag and the
  // next punctuation when the source wrote `<Link>X</Link>{" "}, more` —
  // markdown doesn't need the space before the comma.
  return out.replace(/\s+([,.;:!?])/g, "$1");
}

function inlineFromNode(node) {
  if (!node) return "";
  if (ts.isJsxText(node)) {
    // Normalize whitespace: collapse runs, trim leading/trailing spaces
    // around but preserve at least one space between words across lines.
    return node.text.replace(/\s+/g, " ");
  }
  if (ts.isJsxExpression(node)) {
    if (!node.expression) return "";
    return inlineFromExpression(node.expression);
  }
  if (ts.isJsxElement(node)) {
    return inlineFromElement(node);
  }
  if (ts.isJsxSelfClosingElement(node)) {
    return inlineFromSelfClosing(node);
  }
  if (ts.isJsxFragment(node)) {
    return inlineFromChildren(node.children);
  }
  return "";
}

function inlineFromElement(el) {
  const opening = el.openingElement;
  const tag = getJsxTagName(opening);
  const inner = inlineFromChildren(el.children);
  switch (tag) {
    case "p":
      return inner;
    case "Link":
    case "a": {
      const href = getJsxAttr(opening, "href") || "#";
      return `[${inner.trim()}](${href})`;
    }
    case "em":
    case "i":
      return `*${inner.trim()}*`;
    case "strong":
    case "b":
      return `**${inner.trim()}**`;
    case "code":
      return `\`${inner.trim()}\``;
    case "span":
      return inner;
    case "br":
      return "\n";
    case "ul":
    case "ol":
      // Inline rendering: should be rare; defer to block path
      return inner;
    case "li":
      return inner;
    default:
      return inner;
  }
}

function inlineFromSelfClosing(el) {
  const tag = getJsxTagName(el);
  if (tag === "br") return "\n";
  return "";
}

function inlineFromExpression(expr) {
  if (ts.isStringLiteral(expr)) return expr.text;
  if (ts.isNoSubstitutionTemplateLiteral(expr)) return expr.text;
  // Common idiom: {" "} or {"\n"} for spacing
  return "";
}

function blockFromJsx(node) {
  // For block-level content (welcome, article body, note body, footer):
  // produces newline-separated paragraphs / list / blockquote markdown.
  if (!node) return "";
  if (ts.isParenthesizedExpression(node)) {
    return blockFromJsx(node.expression);
  }
  if (ts.isJsxFragment(node)) {
    return blockFromChildren(node.children);
  }
  if (ts.isJsxElement(node)) {
    return blockFromElement(node);
  }
  if (ts.isJsxSelfClosingElement(node)) {
    return "";
  }
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
    return node.text;
  }
  if (ts.isJsxText(node)) {
    return node.text.replace(/\s+/g, " ").trim();
  }
  return "";
}

function blockFromChildren(children) {
  const blocks = [];
  for (const child of children) {
    if (ts.isJsxText(child)) {
      const t = child.text.replace(/\s+/g, " ");
      if (t.trim()) blocks.push(t.trim());
      continue;
    }
    if (ts.isJsxElement(child)) {
      blocks.push(blockFromElement(child));
      continue;
    }
    if (ts.isJsxExpression(child)) {
      // skip whitespace-only expressions like {" "}
      const r = inlineFromExpression(child.expression);
      if (r.trim()) blocks.push(r.trim());
      continue;
    }
  }
  // Filter empty
  return blocks.filter(Boolean).join("\n\n");
}

function getClassName(el) {
  return getJsxAttr(el.openingElement, "className") || "";
}

function blockFromElement(el) {
  const tag = getJsxTagName(el.openingElement);
  switch (tag) {
    case "p": {
      const cls = getClassName(el);
      const text = inlineFromChildren(el.children).replace(/\s+/g, " ").trim();
      // `<p className="italic ...">` carries the same semantic as <em>
      // (a stylistic note). Preserve it as italic-wrapped markdown so the
      // dynamic renderer's renderInlineMarkdown produces <em>, which
      // looks the same as the static template's italic paragraph (since
      // PersonProfileTemplate's prose wrapper already gives all <p> the
      // same color/leading; only "italic" was the visual difference).
      if (typeof cls === "string" && /\bitalic\b/.test(cls) && text) {
        // Don't double-wrap if already italic
        return text.startsWith("*") && text.endsWith("*") ? text : `*${text}*`;
      }
      return text;
    }
    case "ul": {
      return el.children
        .filter((c) => ts.isJsxElement(c) && getJsxTagName(c.openingElement) === "li")
        .map((li) => `- ${inlineFromChildren(li.children).replace(/\s+/g, " ").trim()}`)
        .join("\n");
    }
    case "ol": {
      return el.children
        .filter((c) => ts.isJsxElement(c) && getJsxTagName(c.openingElement) === "li")
        .map(
          (li, i) =>
            `${i + 1}. ${inlineFromChildren(li.children).replace(/\s+/g, " ").trim()}`,
        )
        .join("\n");
    }
    case "h2":
      return `## ${inlineFromChildren(el.children).replace(/\s+/g, " ").trim()}`;
    case "h3":
      return `### ${inlineFromChildren(el.children).replace(/\s+/g, " ").trim()}`;
    case "blockquote":
      return `> ${inlineFromChildren(el.children).replace(/\s+/g, " ").trim()}`;
    case "pre":
      // Multiline code; preserve text content verbatim
      return "```\n" + el.children.map((c) => (ts.isJsxText(c) ? c.text : c.getText(sourceFile))).join("") + "\n```";
    default:
      // Fallback: treat as paragraph-shaped inline
      return inlineFromChildren(el.children).replace(/\s+/g, " ").trim();
  }
}

/* ── Locate `const content = { ... }` ───────────────────────────── */

let contentObject = null;
sourceFile.forEachChild((node) => {
  if (ts.isVariableStatement(node)) {
    for (const decl of node.declarationList.declarations) {
      if (
        ts.isIdentifier(decl.name) &&
        decl.name.text === "content" &&
        decl.initializer &&
        ts.isObjectLiteralExpression(decl.initializer)
      ) {
        contentObject = decl.initializer;
      }
    }
  }
});

if (!contentObject) {
  console.error(`Could not find "const content = {...}" in ${inputPath}`);
  process.exit(3);
}

/* ── Extract fields from the content object ─────────────────────── */

function getProperty(obj, name) {
  for (const prop of obj.properties) {
    if (
      ts.isPropertyAssignment(prop) &&
      prop.name &&
      ((ts.isIdentifier(prop.name) && prop.name.text === name) ||
        (ts.isStringLiteral(prop.name) && prop.name.text === name))
    ) {
      return prop.initializer;
    }
  }
  return null;
}

function getStringProperty(obj, name) {
  const v = getProperty(obj, name);
  if (!v) return undefined;
  if (ts.isStringLiteral(v) || ts.isNoSubstitutionTemplateLiteral(v)) return v.text;
  if (ts.isTemplateExpression(v) || ts.isBinaryExpression(v)) {
    // Best-effort: get the literal text without the surrounding quotes
    return v.getText(sourceFile).replace(/^['"`]|['"`]$/g, "");
  }
  if (ts.isParenthesizedExpression(v)) {
    return v.expression.getText(sourceFile);
  }
  return v.getText(sourceFile);
}

function unwrapStringValue(node) {
  if (!node) return undefined;
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node))
    return node.text;
  if (ts.isParenthesizedExpression(node)) return unwrapStringValue(node.expression);
  if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
    // Concatenated strings: "a" + "b" + "c"
    const left = unwrapStringValue(node.left);
    const right = unwrapStringValue(node.right);
    if (left !== undefined && right !== undefined) return left + right;
  }
  return undefined;
}

function inlineOrString(node) {
  if (!node) return undefined;
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node))
    return node.text;
  if (ts.isParenthesizedExpression(node)) return inlineOrString(node.expression);
  if (ts.isJsxFragment(node)) return inlineFromChildren(node.children).replace(/\s+/g, " ").trim();
  if (ts.isJsxElement(node)) return inlineFromElement(node).replace(/\s+/g, " ").trim();
  if (ts.isJsxSelfClosingElement(node)) return inlineFromSelfClosing(node);
  // Fallback: stringify
  return node.getText(sourceFile);
}

function blockOrString(node) {
  if (!node) return undefined;
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node))
    return node.text;
  if (ts.isParenthesizedExpression(node)) return blockOrString(node.expression);
  if (ts.isJsxFragment(node)) return blockFromChildren(node.children);
  if (ts.isJsxElement(node)) return blockFromElement(node);
  return undefined;
}

const result = { en: {} };
const out = result[locale] = {};

// metadata: keep verbatim object via JSON.stringify of its property values
const metadataNode = getProperty(contentObject, "metadata");
if (metadataNode && ts.isObjectLiteralExpression(metadataNode)) {
  const md = {};
  for (const prop of metadataNode.properties) {
    if (ts.isPropertyAssignment(prop) && ts.isIdentifier(prop.name)) {
      const v = unwrapStringValue(prop.initializer);
      if (v !== undefined) md[prop.name.text] = v;
    }
  }
  if (Object.keys(md).length) out.metadata = md;
}

const breadcrumb = unwrapStringValue(getProperty(contentObject, "breadcrumbName"));
if (breadcrumb) out.breadcrumb_name = breadcrumb;

const heroNode = getProperty(contentObject, "hero");
if (heroNode && ts.isObjectLiteralExpression(heroNode)) {
  const hero = {};
  const imageNode = getProperty(heroNode, "image");
  if (imageNode && ts.isObjectLiteralExpression(imageNode)) {
    const src = unwrapStringValue(getProperty(imageNode, "src"));
    if (src) hero.image_url = src;
  }
  const background = unwrapStringValue(getProperty(heroNode, "background"));
  if (background) hero.background = background;
  const extraImage = getProperty(heroNode, "extraImage");
  if (extraImage && ts.isObjectLiteralExpression(extraImage)) {
    const src = unwrapStringValue(getProperty(extraImage, "src"));
    const opacityClass = unwrapStringValue(getProperty(extraImage, "opacityClass"));
    const mixBlendClass = unwrapStringValue(getProperty(extraImage, "mixBlendClass"));
    if (src) {
      hero.extra_image = { url: src };
      if (opacityClass) hero.extra_image.opacity_class = opacityClass;
      if (mixBlendClass) hero.extra_image.mix_blend_class = mixBlendClass;
    }
  }
  const overlayClass = unwrapStringValue(getProperty(heroNode, "overlayClass"));
  if (overlayClass) hero.overlay_class = overlayClass;
  const eyebrow = unwrapStringValue(getProperty(heroNode, "eyebrow"));
  if (eyebrow) hero.eyebrow = eyebrow;
  const eyebrowClass = unwrapStringValue(getProperty(heroNode, "eyebrowClass"));
  if (eyebrowClass) hero.eyebrow_class = eyebrowClass;
  const name = unwrapStringValue(getProperty(heroNode, "name"));
  if (name) hero.name = name;
  const welcomeNode = getProperty(heroNode, "welcome");
  const welcome = blockOrString(welcomeNode);
  if (welcome) hero.welcome_md = welcome;
  const lineageDoorwayNode = getProperty(heroNode, "lineageDoorway");
  if (lineageDoorwayNode && ts.isObjectLiteralExpression(lineageDoorwayNode)) {
    const href = unwrapStringValue(getProperty(lineageDoorwayNode, "href"));
    const labelNode = getProperty(lineageDoorwayNode, "label");
    const label = inlineOrString(labelNode);
    const summaryNode = getProperty(lineageDoorwayNode, "summary");
    const summary = inlineOrString(summaryNode);
    if (href && label) {
      hero.lineage_doorway = { href, label };
      if (summary) hero.lineage_doorway.summary = summary;
    }
  }
  out.hero = hero;
}

const factsNode = getProperty(contentObject, "facts");
if (factsNode && ts.isArrayLiteralExpression(factsNode)) {
  out.facts = [];
  for (const el of factsNode.elements) {
    if (!ts.isObjectLiteralExpression(el)) continue;
    const label = unwrapStringValue(getProperty(el, "label"));
    const valueNode = getProperty(el, "value");
    const value = inlineOrString(valueNode);
    if (label && value !== undefined) {
      out.facts.push({ label, value_md: value });
    }
  }
}

const noteFromBodyNode = getProperty(contentObject, "noteFromBody");
if (noteFromBodyNode && ts.isObjectLiteralExpression(noteFromBodyNode)) {
  const eyebrow = unwrapStringValue(getProperty(noteFromBodyNode, "eyebrow"));
  const body = blockOrString(getProperty(noteFromBodyNode, "body"));
  if (body) {
    out.note_from_body = { body_md: body };
    if (eyebrow) out.note_from_body.eyebrow = eyebrow;
  }
}

const articlesNode = getProperty(contentObject, "articles");
if (articlesNode && ts.isArrayLiteralExpression(articlesNode)) {
  out.articles = [];
  for (const el of articlesNode.elements) {
    if (!ts.isObjectLiteralExpression(el)) continue;
    const kind = unwrapStringValue(getProperty(el, "kind"));
    const heading = unwrapStringValue(getProperty(el, "heading"));
    const eyebrow = unwrapStringValue(getProperty(el, "eyebrow"));
    const variant = unwrapStringValue(getProperty(el, "variant"));
    const body = blockOrString(getProperty(el, "body"));
    if (body) {
      const article = { kind: kind || "narrative", body_md: body };
      if (heading) article.heading = heading;
      if (eyebrow) article.eyebrow = eyebrow;
      if (variant) article.variant = variant;
      out.articles.push(article);
    }
  }
}

const footerNode = getProperty(contentObject, "footer");
const footer = blockOrString(footerNode);
if (footer) out.footer_md = footer;

/* ── Output ─────────────────────────────────────────────────────── */

const json = JSON.stringify(result, null, 2) + "\n";
if (write) {
  const dest = path.join(REPO_ROOT, "docs", "presence-content", `${slug}.json`);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.writeFileSync(dest, json);
  console.error(`Wrote ${path.relative(REPO_ROOT, dest)}`);
} else {
  process.stdout.write(json);
}
