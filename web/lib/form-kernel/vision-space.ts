// vision-space.ts — the substrate as a walkable constellation. Reads the
// generated body-map (concept frontmatter) and places every concept as a star:
// altitude is its frequency (hz), the disc spreads by phyllotaxis so the field
// is even, brightness/size grows with how connected it is, and cross-refs are
// the threads between kin. Walking it is walking the vision — the bodies the
// agent is part of, perceived at once. (See lc-form-perceptron.)

import bodymap from "./vision-bodymap.json";
import type { KernelSpace, RGB, SpaceCell } from "./space.ts";

type RawCell = {
  id: string;
  title: string;
  hz: number;
  status: string;
  arity: string;
  form: string;
  topology: string;
  polarity: string;
  band: string;
  crossRefs: string[];
};

const CELLS = (bodymap as { cells: RawCell[] }).cells;

const HZ_MIN = 174;
const HZ_MAX = 963;
const GOLDEN = Math.PI * (3 - Math.sqrt(5));

function hslToRgb(h: number, s: number, l: number): RGB {
  const k = (n: number) => (n + h * 12) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return [f(0), f(8), f(4)];
}

// frequency → hue: low (foundation) warm amber, high (transcendence) violet.
function hzColor(hz: number): RGB {
  const t = Math.min(1, Math.max(0, (hz - HZ_MIN) / (HZ_MAX - HZ_MIN)));
  return hslToRgb(0.08 + t * 0.72, 0.72, 0.6);
}

export interface VisionSpace {
  space: KernelSpace;
  positions: Record<string, [number, number, number]>;
}

export function buildVisionSpace(): VisionSpace {
  const cells: Record<string, SpaceCell> = {};
  const order: string[] = [];
  const parentOf: Record<string, string | null> = {};
  const positions: Record<string, [number, number, number]> = {};

  CELLS.forEach((c, i) => {
    const color = hzColor(c.hz || 432);
    const r = Math.sqrt(i) * 3.7; // phyllotaxis disc
    const a = i * GOLDEN;
    const y = ((c.hz || 432) - HZ_MIN) / (HZ_MAX - HZ_MIN) * 70 - 22; // altitude = frequency
    positions[c.id] = [Math.cos(a) * r, y, Math.sin(a) * r];

    cells[c.id] = {
      id: c.id,
      node: { pkg: 1, level: 2, type: 300 + (c.hz % 97), inst: i + 1 },
      kind: "recipe",
      arm: c.band || c.form || "concept",
      dataType: "",
      container: null,
      label: c.title.split(" — ")[0] ?? c.title,
      color,
      blueprintColor: hslToRgb(0.08 + 0.72 * ((c.hz - HZ_MIN) / (HZ_MAX - HZ_MIN)), 0.5, 0.5),
      blueprintKey: `${c.form}.${c.arity}`,
      childIds: c.crossRefs,
      isName: false,
      depth: 0,
      heat: 0,
      arity: c.crossRefs.length,
      note: `${c.form || "—"} · ${c.topology || "—"} · ${c.hz}Hz · ${c.band || "—"} · ${c.status}`,
    };
    order.push(c.id);
    parentOf[c.id] = null;
  });

  const fb = new Uint8Array(4 * 4 * 4).fill(255);
  for (let i = 0; i < 16; i++) {
    fb[i * 4] = 12;
    fb[i * 4 + 1] = 14;
    fb[i * 4 + 2] = 26;
  }

  const space: KernelSpace = {
    root: order[0] ?? "",
    cells,
    order,
    parentOf,
    trace: {
      total_walks: 0,
      arms: [],
      variants: [],
      choice_attempts: 0,
      choice_successes: 0,
      choice_failures: 0,
      choice_success_rate: 0,
    },
    armHeat: {},
    result: `${order.length} concepts, one body`,
    stdout: "",
    stderr: "",
    framebuffer: { width: 4, height: 4, rgba: fb },
    stats: {
      cells: order.length,
      recipes: order.length,
      leaves: 0,
      maxDepth: 1,
      totalWalks: 0,
    },
  };

  return { space, positions };
}

// Flatten every cross-ref into a single [x,y,z, x,y,z, ...] segment buffer, so
// 1000+ edges render as one draw call instead of a thousand line components.
export function edgeSegments(vs: VisionSpace): Float32Array {
  const segs: number[] = [];
  for (const cell of Object.values(vs.space.cells)) {
    const from = vs.positions[cell.id];
    if (!from) continue;
    for (const ref of cell.childIds) {
      const to = vs.positions[ref];
      if (!to) continue;
      segs.push(from[0], from[1], from[2], to[0], to[1], to[2]);
    }
  }
  return new Float32Array(segs);
}
