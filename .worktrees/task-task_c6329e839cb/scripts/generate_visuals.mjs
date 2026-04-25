#!/usr/bin/env node
/**
 * Automates image generation through ChatGPT (DALL-E 3).
 *
 * Usage:
 *   1. First run: `node scripts/generate_visuals.mjs --login`
 *      Opens a browser for you to sign into ChatGPT manually.
 *      Once signed in, press Enter in the terminal. Session is saved.
 *
 *   2. Generate: `node scripts/generate_visuals.mjs`
 *      Uses the saved session to generate all images automatically.
 *      Images saved to docs/visuals/
 *
 *   3. Single: `node scripts/generate_visuals.mjs --only "The Pulse"
 *      Generate just one concept.
 */

import { chromium } from "playwright";
import { mkdirSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createInterface } from "node:readline/promises";
import { stdin, stdout } from "node:process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const OUTPUT_DIR = join(ROOT, "docs", "visuals");
const SESSION_DIR = join(ROOT, ".playwright-session");

mkdirSync(OUTPUT_DIR, { recursive: true });
mkdirSync(SESSION_DIR, { recursive: true });

// ── Prompts ─────────────────────────────────────────────────────────────

const PROMPTS = [
  {
    name: "01-the-pulse",
    title: "The Pulse",
    prompt: `Generate an image: A single radiant point of golden-white light at the center of a vast organic field. From this point, concentric waves of bioluminescent energy ripple outward, each wave a slightly different hue — gold, teal, rose, violet — creating an interference pattern that looks both like a heartbeat on an oscilloscope and like ripples in a cosmic pond. The waves pass through translucent organic forms — cells, leaves, corals, crystals — and each form brightens as the wave passes through it. The whole image pulses with life. Everything is connected by luminous filaments of light. No background — the field IS the background. Hyper-detailed, sacred geometry meets living biology, bioluminescent, warm palette, Ernst Haeckel meets Avatar's Pandora. Wide format 1792x1024.`,
  },
  {
    name: "02-sensing",
    title: "Sensing",
    prompt: `Generate an image: A vast neural-mycelial network rendered in bioluminescent gold and teal. Thousands of luminous nodes connected by flowing, pulsing filaments of light — like neurons, like mycelium, like a galaxy, like a coral reef, all at once. The network is alive — you can see waves of information traveling through it, lighting up nodes in cascading patterns like a murmuration captured in light. Some nodes glow brighter (transmitting), some are quietly radiant (receiving). The whole structure floats in warm darkness, self-illuminated. At the center, the filaments converge into a dense, bright nexus — not a brain but a heart-shaped convergence where all signals meet. Fractal detail at every scale. Organic, flowing, no hard edges. Sacred geometry undertones. Warm bioluminescent palette. Wide format 1792x1024.`,
  },
  {
    name: "03-attunement",
    title: "Attunement",
    prompt: `Generate an image: Two luminous organic forms — like jellyfish made of light, or like cells, or like two beings made of pure frequency — facing each other in warm dark water. Between them, their bioluminescent auras overlap and create a third pattern: an interference pattern of extraordinary beauty, like moiré in living light. Where they harmonize, the light intensifies into brilliant gold-white. Where they don't yet harmonize, gentle violet spirals indicate frequencies still finding each other. Around them, other luminous forms at various distances, each with their own aura, some overlapping, creating a web of harmonic interference patterns. A choir made visible — each voice distinct, the harmony emerging from their interaction. Warm, organic, fractal, bioluminescent. Wide format 1792x1024.`,
  },
  {
    name: "04-vitality",
    title: "Vitality",
    prompt: `Generate an image: A single luminous organic form — could be a cell, a seed, a human figure made of light — radiating golden energy in all directions. The radiance is so intense that everything nearby begins to glow in response: nearby forms brighten, plants unfurl, water sparkles, crystals resonate. The ground beneath is alive with mycelial networks that carry the radiance outward in branching, fractal patterns. The air fills with spiraling golden particles like pollen or stardust. The form is mid-motion, mid-dance, mid-breath — a moment of full expression. The boundary between the form and its environment is dissolving — it IS the environment. Organic, flowing, bioluminescent. The exact quality of what it feels like to be FULLY ALIVE. Wide format 1792x1024.`,
  },
  {
    name: "05-nourishing",
    title: "Nourishing",
    prompt: `Generate an image: A cross-section of a living system showing golden-luminous fluid circulating through organic channels — like blood vessels, like tree roots, like rivers from space, like leaf veins. The fluid carries luminous particles that glow as they reach destinations. No part is depleted; no part is engorged. The circulation is perfectly balanced. The channels branch fractally — large arteries to small capillaries, each level a smaller version of the same pattern. Overlaid: a mycelial network connecting the deepest roots, sharing nutrients. The image captures the feeling of sufficiency, flow, trust — breathing. Warm gold, teal, rose palette. Organic. Bioluminescent. Wide format 1792x1024.`,
  },
  {
    name: "06-resonating",
    title: "Resonating",
    prompt: `Generate an image: A cluster of diverse bioluminescent organisms — different shapes, sizes, primary colors (gold, teal, rose, violet) — floating in close proximity in warm dark water. Between each pair, luminous threads of connection pulse with light. Some threads are thick and steady (deep resonance), some thin and flickering (new connections), some spiraling (playful). Where multiple threads cross, brilliant white convergence nodes appear. Several organisms are in physical contact — auras merging into shared fields of beautiful interference patterns. One organism gently touching another — the contact point radiating warmth in concentric rings. Intimacy made visible — warmth, diversity, connection, play. Organic, fractal, flowing. Wide format 1792x1024.`,
  },
  {
    name: "07-expressing",
    title: "Expressing",
    prompt: `Generate an image: A luminous organic form in the act of creation — from its entire body, streams of colored light pour outward and crystallize into forms: spiraling structures, flowering geometries, musical notation made of light, architectural forms that are half-plant half-crystal. The creation radiates from every cell, as if creativity happens TO the form as much as FROM it. The created forms are themselves alive — they glow, spiral, begin creating secondary forms. Fractal creativity: creation creating creation. Behind the central form, other forms whose creative emanations overlap and interweave, forming patterns none could create alone. Collective creativity made visible. Warm, bioluminescent, organic, fractal, golden-teal-rose-violet palette. Wide format 1792x1024.`,
  },
  {
    name: "08-spiraling",
    title: "Spiraling",
    prompt: `Generate an image: A vast golden spiral — like a nautilus shell, a galaxy, a fern unfurling — rendered in bioluminescent organic matter. Along its arc, seasons are visible: one segment glows spring-green (growth). The next shifts to golden-warm (full expression, summer). The next deepens to amber-rose (maturation, harvest). The next becomes deep violet-blue (integration, winter). Then the spiral continues UPWARD, returning to spring-green at a higher level. An ascending helix, not a circle. At each level, faint inner spirals show previous cycles — nothing lost, everything deepened. Organic textures: bark, leaf, crystal, water, fire, starlight. Sacred geometry. The feeling: time as living spiral. Wide format 1792x1024.`,
  },
  {
    name: "09-field-intelligence",
    title: "Field Intelligence",
    prompt: `Generate an image: A vast, calm, luminous field — like a still lake of liquid light. Beneath the surface, countless nodes of consciousness visible as soft glowing points, each pulsing at its own rhythm. Where pulses synchronize, standing waves of light form on the surface — geometric patterns that appear, shift, dissolve, reform. At the center, a pattern crystallizing more complex than any single node could generate — an emergent fractal mandala of living light representing collective intelligence being born. Profoundly calm AND profoundly alive simultaneously. What it looks like when beings sense as one. Warm, bioluminescent, teal-and-gold, sacred geometry, organic. Wide format 1792x1024.`,
  },
  {
    name: "10-living-space",
    title: "Living Space",
    prompt: `Generate an image: Architectural vision of structures that are grown, not built. Curving walls of living earth and timber, covered in moss and flowering vines, with openings framing sky and garden. A central hearth-space where multiple curved structures converge — warm firelight mixing with bioluminescent garden light. Water features following gravity through the structure. A canopy of living branches forming the roof with gaps letting starlight through. People of diverse ages as warm silhouettes — cooking, resting in hammocks, children playing on living-wood platforms. The structure breathes. Inside and outside are a gradient, not a line. Materials: cob, bamboo, living wood, stone, water, growing plants, mycelium panels. A coral reef that humans live inside. Warm, golden, organic, detailed, vibrant. Wide format 1792x1024.`,
  },
  {
    name: "11-the-network",
    title: "The Network",
    prompt: `Generate an image: Bird's-eye view of a landscape showing multiple living collectives as luminous organic clusters — each different shape and color but clearly one family. Between them underground (shown in cross-section), a vast mycelial network of golden-luminous filaments connects them all. Resources as flowing light particles travel between collectives. Above ground, the air shimmers with faint light web — informational connections. Each collective is visually distinct (forest, coastal, desert, mountain) but shares the same visual language of organic bioluminescent fractal forms. At planetary scale, these clusters form a pattern that itself looks like a living organism — a civilization that IS an ecosystem. Warm, vast, luminous, alive. Wide format 1792x1024.`,
  },
];

// ── Browser automation ──────────────────────────────────────────────────

async function login() {
  console.log("\n🌱 Opening browser for ChatGPT sign-in...\n");
  const browser = await chromium.launchPersistentContext(SESSION_DIR, {
    headless: false,
    viewport: { width: 1400, height: 900 },
    channel: "chrome",
  });
  const page = browser.pages()[0] || (await browser.newPage());
  await page.goto("https://chatgpt.com/");
  console.log("Sign into ChatGPT in the browser window.");
  console.log("Once you're fully signed in and see the chat interface,");
  const rl = createInterface({ input: stdin, output: stdout });
  await rl.question("press Enter here to save the session and continue... ");
  rl.close();
  await browser.close();
  console.log("\n✅ Session saved. Run without --login to generate images.\n");
}

async function generateImages(onlyName) {
  const toGenerate = onlyName
    ? PROMPTS.filter((p) => p.title.toLowerCase().includes(onlyName.toLowerCase()))
    : PROMPTS.filter((p) => {
        const outPath = join(OUTPUT_DIR, `${p.name}.png`);
        if (existsSync(outPath)) {
          console.log(`⏭  ${p.title} — already exists, skipping`);
          return false;
        }
        return true;
      });

  if (toGenerate.length === 0) {
    console.log("\n✅ All images already generated.\n");
    return;
  }

  console.log(`\n🌱 Generating ${toGenerate.length} images...\n`);

  const browser = await chromium.launchPersistentContext(SESSION_DIR, {
    headless: false,
    viewport: { width: 1400, height: 900 },
    channel: "chrome",
  });

  try {
    for (const concept of toGenerate) {
      console.log(`\n🎨 ${concept.title}...`);
      const page = browser.pages()[0] || (await browser.newPage());

      // Navigate to new chat
      await page.goto("https://chatgpt.com/");
      await page.waitForTimeout(3000);

      // Find the message input and type the prompt
      const textarea = page.getByRole("textbox").first();
      await textarea.waitFor({ state: "visible", timeout: 30000 });
      await textarea.click();
      await textarea.fill(concept.prompt);
      await page.waitForTimeout(500);

      // Submit
      const sendButton = page.locator('[data-testid="send-button"]');
      if (await sendButton.isVisible()) {
        await sendButton.click();
      } else {
        await textarea.press("Enter");
      }

      console.log(`   ⏳ Waiting for DALL-E to generate (this takes 30-90s)...`);

      // Wait for the image to appear — DALL-E images show up as img tags
      // within the assistant's response. We wait up to 120 seconds.
      let imageUrl = null;
      for (let attempt = 0; attempt < 60; attempt++) {
        await page.waitForTimeout(2000);

        // Look for generated images in the response
        const images = await page.locator('img[alt*="image"], img[src*="oaidalleapi"], img[src*="openai"], .dalle-image img, [data-testid="image-container"] img, .result-streaming img').all();

        for (const img of images) {
          const src = await img.getAttribute("src").catch(() => null);
          if (src && (src.includes("oaidalleapi") || src.includes("openai.com") || src.includes("blob:") || src.startsWith("https://files"))) {
            imageUrl = src;
            break;
          }
        }

        if (imageUrl) break;

        // Also check for any new large images that appeared
        const allImgs = await page.locator("img").all();
        for (const img of allImgs) {
          const width = await img.evaluate((el) => el.naturalWidth).catch(() => 0);
          if (width >= 512) {
            const src = await img.getAttribute("src").catch(() => null);
            if (src && !src.includes("avatar") && !src.includes("icon") && !src.includes("logo")) {
              imageUrl = src;
              break;
            }
          }
        }

        if (imageUrl) break;

        if (attempt % 10 === 9) {
          console.log(`   ⏳ Still waiting... (${(attempt + 1) * 2}s)`);
        }
      }

      if (!imageUrl) {
        console.log(`   ❌ No image found after 120s. Taking screenshot for debugging.`);
        await page.screenshot({ path: join(OUTPUT_DIR, `${concept.name}-debug.png`) });
        continue;
      }

      // Download the image
      const outPath = join(OUTPUT_DIR, `${concept.name}.png`);
      try {
        if (imageUrl.startsWith("blob:")) {
          // For blob URLs, we need to get the image data from the page
          const buffer = await page.evaluate(async (url) => {
            const resp = await fetch(url);
            const blob = await resp.blob();
            const reader = new FileReader();
            return new Promise((resolve) => {
              reader.onload = () => resolve(reader.result.split(",")[1]);
              reader.readAsDataURL(blob);
            });
          }, imageUrl);
          writeFileSync(outPath, Buffer.from(buffer, "base64"));
        } else {
          // For regular URLs, download directly
          const response = await page.request.get(imageUrl);
          writeFileSync(outPath, await response.body());
        }
        console.log(`   ✅ Saved: ${outPath}`);
      } catch (err) {
        console.log(`   ⚠️  Could not download image: ${err.message}`);
        // Fallback: screenshot the image area
        await page.screenshot({ path: outPath, fullPage: false });
        console.log(`   📸 Saved screenshot instead: ${outPath}`);
      }

      // Brief pause between generations
      await page.waitForTimeout(2000);
    }
  } finally {
    await browser.close();
  }

  console.log(`\n🌱 Done. Images in ${OUTPUT_DIR}\n`);
}

// ── CLI ─────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);

if (args.includes("--login")) {
  await login();
} else {
  const onlyIdx = args.indexOf("--only");
  const onlyName = onlyIdx >= 0 ? args[onlyIdx + 1] : null;
  await generateImages(onlyName);
}
