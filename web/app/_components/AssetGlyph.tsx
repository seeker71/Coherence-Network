"use client";

// A small colored glyph that signals the kind of asset at a glance —
// audio, image, video, 3D, blueprint, spec, research, content. The
// asset list endpoint doesn't carry image_url for previews, so the
// glyph stands in until you click through.

type Tone = {
  bg: string;
  text: string;
  ring: string;
  // Solid stripe color for the left-edge tone strip on cards.
  stripe: string;
  // Tailwind class that toggles the --tone-glow CSS variable for hover lift.
  glowClass: string;
};

const TONES: Record<string, Tone> = {
  IMAGE:    { bg: "bg-rose-500/10",    text: "text-rose-300",    ring: "ring-rose-500/30",    stripe: "bg-rose-500/60",    glowClass: "tone-rose"    },
  AUDIO:    { bg: "bg-teal-500/10",    text: "text-teal-300",    ring: "ring-teal-500/30",    stripe: "bg-teal-500/60",    glowClass: "tone-teal"    },
  VIDEO:    { bg: "bg-coral-500/10",   text: "text-orange-300",  ring: "ring-orange-500/30",  stripe: "bg-orange-500/60",  glowClass: "tone-orange"  },
  MODEL_3D: { bg: "bg-emerald-500/10", text: "text-emerald-300", ring: "ring-emerald-500/30", stripe: "bg-emerald-500/60", glowClass: "tone-emerald" },
  BLUEPRINT:{ bg: "bg-sky-500/10",     text: "text-sky-300",     ring: "ring-sky-500/30",     stripe: "bg-sky-500/60",     glowClass: "tone-sky"     },
  SPEC:     { bg: "bg-slate-500/10",   text: "text-slate-300",   ring: "ring-slate-500/30",   stripe: "bg-slate-500/60",   glowClass: "tone-slate"   },
  RESEARCH: { bg: "bg-indigo-500/10",  text: "text-indigo-300",  ring: "ring-indigo-500/30",  stripe: "bg-indigo-500/60",  glowClass: "tone-indigo"  },
  REVIEW:   { bg: "bg-pink-500/10",    text: "text-pink-300",    ring: "ring-pink-500/30",    stripe: "bg-pink-500/60",    glowClass: "tone-pink"    },
  RENDERER: { bg: "bg-violet-500/10",  text: "text-violet-300",  ring: "ring-violet-500/30",  stripe: "bg-violet-500/60",  glowClass: "tone-violet"  },
  CONTENT:  { bg: "bg-amber-500/10",   text: "text-amber-300",   ring: "ring-amber-500/30",   stripe: "bg-amber-500/60",   glowClass: "tone-amber"   },
};

const DEFAULT_TONE: Tone = {
  bg: "bg-stone-500/10",
  text: "text-stone-300",
  ring: "ring-stone-500/30",
  stripe: "bg-stone-500/40",
  glowClass: "tone-stone",
};

function toneFor(type: string | undefined | null): Tone {
  if (!type) return DEFAULT_TONE;
  return TONES[type.toUpperCase()] ?? DEFAULT_TONE;
}

function Path({ d }: { d: string }) {
  return (
    <path
      d={d}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  );
}

function Glyph({ type }: { type: string }) {
  const t = (type || "").toUpperCase();
  // 24x24 svg, rendered inside a colored ring.
  switch (t) {
    case "IMAGE":
      return (
        <svg viewBox="0 0 24 24" className="w-5 h-5">
          <Path d="M4 6h16v12H4z" />
          <Path d="M4 16l4-5 4 4 3-3 5 4" />
          <circle cx="9" cy="10" r="1.4" fill="currentColor" />
        </svg>
      );
    case "AUDIO":
      return (
        <svg viewBox="0 0 24 24" className="w-5 h-5">
          <Path d="M4 12c2 0 2-3 4-3s2 6 4 6 2-9 4-9 2 6 4 6" />
        </svg>
      );
    case "VIDEO":
      return (
        <svg viewBox="0 0 24 24" className="w-5 h-5">
          <Path d="M4 6h12v12H4z" />
          <Path d="M16 9l4-2v10l-4-2" />
        </svg>
      );
    case "MODEL_3D":
      return (
        <svg viewBox="0 0 24 24" className="w-5 h-5">
          <Path d="M12 3l8 4.5v9L12 21 4 16.5v-9z" />
          <Path d="M12 3v18" />
          <Path d="M4 7.5l8 4.5 8-4.5" />
        </svg>
      );
    case "BLUEPRINT":
      return (
        <svg viewBox="0 0 24 24" className="w-5 h-5">
          <Path d="M4 5h16v14H4z" />
          <Path d="M8 5v14M16 5v14M4 12h16" />
        </svg>
      );
    case "SPEC":
      return (
        <svg viewBox="0 0 24 24" className="w-5 h-5">
          <Path d="M6 3h9l3 3v15H6z" />
          <Path d="M9 9h6M9 13h6M9 17h4" />
        </svg>
      );
    case "RESEARCH":
      return (
        <svg viewBox="0 0 24 24" className="w-5 h-5">
          <circle cx="11" cy="11" r="6" stroke="currentColor" strokeWidth="1.6" fill="none" />
          <Path d="M16 16l4 4" />
        </svg>
      );
    case "REVIEW":
      return (
        <svg viewBox="0 0 24 24" className="w-5 h-5">
          <Path d="M12 3l2.5 5.5 6 .8-4.4 4.2 1.1 6L12 16.8 6.8 19.5l1.1-6L3.5 9.3l6-.8z" />
        </svg>
      );
    case "RENDERER":
      return (
        <svg viewBox="0 0 24 24" className="w-5 h-5">
          <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.6" fill="none" />
          <Path d="M12 4v3M12 17v3M4 12h3M17 12h3M6.3 6.3l2.1 2.1M15.6 15.6l2.1 2.1M6.3 17.7l2.1-2.1M15.6 8.4l2.1-2.1" />
        </svg>
      );
    case "CONTENT":
    default:
      return (
        <svg viewBox="0 0 24 24" className="w-5 h-5">
          <Path d="M4 6c0-1 1-2 2-2h12c1 0 2 1 2 2v12c0 1-1 2-2 2H6c-1 0-2-1-2-2z" />
          <Path d="M8 9h8M8 13h8M8 17h5" />
        </svg>
      );
  }
}

export function AssetGlyph({ type, className = "" }: { type: string; className?: string }) {
  const tone = toneFor(type);
  return (
    <span
      className={[
        "inline-flex items-center justify-center w-10 h-10 rounded-xl ring-1",
        tone.bg,
        tone.text,
        tone.ring,
        className,
      ].join(" ")}
      aria-hidden="true"
    >
      <Glyph type={type} />
    </span>
  );
}

export function assetTypeTone(type: string | undefined | null): Tone {
  return toneFor(type);
}

