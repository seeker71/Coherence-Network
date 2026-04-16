"use client";

/**
 * /vision/immerse — The vision surrounding you.
 *
 * Multi-tile ambient viewer. On ultra-wide displays, shows 6+ images
 * simultaneously, each crossfading independently so the field feels alive
 * and non-rigid. On smaller displays, gracefully reduces to fewer tiles.
 *
 * Leave it running on a second monitor. The vision's frequency
 * surrounds you throughout the day.
 *
 * Controls:
 *   space   pause/resume all tiles
 *   ← →     advance all tiles one step
 *   f       toggle fullscreen
 *   c       cycle category
 *   h       hide/show UI
 *   1-9     set tile count (or auto)
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

type VisualSource = {
  file: string;
  title: string;
  category: string;
};

type ImageEntry = {
  path: string;
  title: string;
  category: string;
};

type Category = {
  id: string;
  label: string;
  filter: (img: VisualSource) => boolean;
};

const ALL_VISUALS: VisualSource[] = [
  { file: "01-the-pulse.png", title: "The Pulse", category: "concept" },
  { file: "02-sensing.png", title: "Sensing", category: "concept" },
  { file: "03-attunement.png", title: "Attunement", category: "concept" },
  { file: "04-vitality.png", title: "Vitality", category: "concept" },
  { file: "05-nourishing.png", title: "Nourishing", category: "concept" },
  { file: "06-resonating.png", title: "Resonating", category: "concept" },
  { file: "07-expressing.png", title: "Expressing", category: "concept" },
  { file: "08-spiraling.png", title: "Spiraling", category: "concept" },
  { file: "09-field-intelligence.png", title: "Field Intelligence", category: "concept" },
  { file: "10-living-space.png", title: "Living Space", category: "concept" },
  { file: "11-the-network.png", title: "The Network", category: "concept" },
  { file: "life-ceremony-fire.png", title: "Fire Ceremony", category: "ceremony" },
  { file: "life-morning-circle.png", title: "Morning Circle", category: "ceremony" },
  { file: "life-song-circle.png", title: "Song Circle", category: "ceremony" },
  { file: "life-storytelling.png", title: "Storytelling", category: "ceremony" },
  { file: "life-water-gathering.png", title: "Water Gathering", category: "ceremony" },
  { file: "practice-drum-circle.png", title: "Drum Circle", category: "ceremony" },
  { file: "practice-sound-healing.png", title: "Sound Journey", category: "ceremony" },
  { file: "practice-storytelling-elder.png", title: "Elder Storytelling", category: "ceremony" },
  { file: "practice-yoga-dawn.png", title: "Dawn Movement", category: "ceremony" },
  { file: "practice-tantra-circle.png", title: "Presence Circle", category: "ceremony" },
  { file: "life-breathwork.png", title: "Breathwork", category: "ceremony" },
  { file: "v-ceremony.png", title: "Ceremony", category: "ceremony" },
  { file: "joy-collective-build.png", title: "Collective Build", category: "joy" },
  { file: "joy-harvest-feast.png", title: "Harvest Feast", category: "joy" },
  { file: "joy-moonlight-swim.png", title: "Moonlight Swim", category: "joy" },
  { file: "joy-spring-awakening.png", title: "Spring Awakening", category: "joy" },
  { file: "joy-sunrise-yoga.png", title: "Sunrise Yoga", category: "joy" },
  { file: "joy-winter-hearth.png", title: "Winter Hearth", category: "joy" },
  { file: "life-children-play.png", title: "Children at Play", category: "joy" },
  { file: "life-contact-improv.png", title: "Contact & Movement", category: "joy" },
  { file: "v-play-expansion.png", title: "Play & Expansion", category: "joy" },
  { file: "v-comfort-joy.png", title: "Comfort & Joy", category: "joy" },
  { file: "v-freedom.png", title: "Freedom", category: "joy" },
  { file: "life-shared-meal.png", title: "Shared Meal", category: "nourishment" },
  { file: "life-garden-planting.png", title: "Hands in Soil", category: "nourishment" },
  { file: "nature-food-forest-walk.png", title: "Food Forest Walk", category: "nourishment" },
  { file: "nature-herb-spiral.png", title: "Herb Spiral", category: "nourishment" },
  { file: "nature-animals-integrated.png", title: "Animals in the Field", category: "nourishment" },
  { file: "nature-living-roof-close.png", title: "Living Roof", category: "nourishment" },
  { file: "nature-architecture-blend.png", title: "Architecture in Nature", category: "nourishment" },
  { file: "practice-fermentation.png", title: "Fermentation Alchemy", category: "nourishment" },
  { file: "resource-composting-cycle.png", title: "Composting Cycle", category: "nourishment" },
  { file: "resource-food-forest-layers.png", title: "Food Forest Layers", category: "nourishment" },
  { file: "resource-water-system.png", title: "Water System", category: "nourishment" },
  { file: "v-food-practice.png", title: "Food as Practice", category: "nourishment" },
  { file: "space-hearth-interior.png", title: "The Hearth", category: "space" },
  { file: "space-nest-ground.png", title: "Ground Nest", category: "space" },
  { file: "space-nest-tree.png", title: "Tree Nest", category: "space" },
  { file: "space-water-temple-interior.png", title: "Water Temple", category: "space" },
  { file: "space-stillness-sanctuary.png", title: "Stillness Sanctuary", category: "space" },
  { file: "space-gathering-bowl.png", title: "Gathering Bowl", category: "space" },
  { file: "space-creation-arc-overview.png", title: "Creation Arc", category: "space" },
  { file: "space-movement-ground.png", title: "Movement Ground", category: "space" },
  { file: "v-shelter-organism.png", title: "Shelter as Skin", category: "space" },
  { file: "transform-apartment.png", title: "Apartment Transformed", category: "space" },
  { file: "transform-neighborhood.png", title: "Neighborhood", category: "space" },
  { file: "transform-suburb.png", title: "Suburb", category: "space" },
  { file: "transform-village.png", title: "Village", category: "space" },
  { file: "community-auroville.png", title: "Auroville", category: "community" },
  { file: "community-damanhur.png", title: "Damanhur", category: "community" },
  { file: "community-earthship.png", title: "Earthship", category: "community" },
  { file: "community-findhorn.png", title: "Findhorn", category: "community" },
  { file: "community-gaviotas.png", title: "Gaviotas", category: "community" },
  { file: "community-tamera.png", title: "Tamera", category: "community" },
  { file: "network-knowledge-sharing.png", title: "Knowledge Sharing", category: "community" },
  { file: "network-midsummer-gathering.png", title: "Midsummer Gathering", category: "community" },
  { file: "network-traveling-musicians.png", title: "Traveling Musicians", category: "community" },
  { file: "life-nomad-arrival.png", title: "A Traveler Arrives", category: "community" },
  { file: "practice-shared-washing.png", title: "Shared Washing", category: "community" },
  { file: "life-creation-workshop.png", title: "Creation Workshop", category: "community" },
  { file: "scale-seed-8.png", title: "Seed (8 people)", category: "scale" },
  { file: "scale-sapling-40.png", title: "Sapling (40 people)", category: "scale" },
  { file: "scale-tree-120.png", title: "Tree (120 people)", category: "scale" },
  { file: "scale-grove-250.png", title: "Grove (250 people)", category: "scale" },
  { file: "scale-network-map.png", title: "Network Map", category: "scale" },
  { file: "v-harmonizing.png", title: "Harmonizing", category: "scale" },
  { file: "v-inclusion.png", title: "Inclusion", category: "scale" },
  { file: "resource-solar-array.png", title: "Solar Array", category: "scale" },
  { file: "resource-creation-arc-full.png", title: "Creation Arc Full", category: "scale" },
];

const CATEGORIES: Category[] = [
  { id: "all", label: "All", filter: () => true },
  { id: "ceremony", label: "Ceremony & Presence", filter: (i) => i.category === "ceremony" },
  { id: "joy", label: "Joy & Play", filter: (i) => i.category === "joy" },
  { id: "nourishment", label: "Nourishment & Land", filter: (i) => i.category === "nourishment" },
  { id: "space", label: "Spaces", filter: (i) => i.category === "space" },
  { id: "community", label: "Community", filter: (i) => i.category === "community" },
  { id: "concept", label: "Concepts", filter: (i) => i.category === "concept" },
  { id: "scale", label: "Scales", filter: (i) => i.category === "scale" },
];

const TILE_INTERVAL_MS = 10000;
const TRANSITION_MS = 2500;

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function autoTileCount(width: number): number {
  // Each tile wants ~800px of width to feel right
  if (width >= 4800) return 6;
  if (width >= 3600) return 5;
  if (width >= 2800) return 4;
  if (width >= 2000) return 3;
  if (width >= 1200) return 2;
  return 1;
}

function gridLayout(tileCount: number): { cols: number; rows: number } {
  // Grid dimensions for N tiles
  const layouts: Record<number, { cols: number; rows: number }> = {
    1: { cols: 1, rows: 1 },
    2: { cols: 2, rows: 1 },
    3: { cols: 3, rows: 1 },
    4: { cols: 4, rows: 1 },
    5: { cols: 5, rows: 1 },
    6: { cols: 6, rows: 1 },
    7: { cols: 4, rows: 2 },
    8: { cols: 4, rows: 2 },
    9: { cols: 3, rows: 3 },
  };
  return layouts[tileCount] || { cols: 6, rows: 1 };
}

export default function ImmersePage() {
  const [categoryId, setCategoryId] = useState<string>("all");
  const [paused, setPaused] = useState(false);
  const [hideUI, setHideUI] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [viewport, setViewport] = useState({ w: 1920, h: 1080 });
  const [tileOverride, setTileOverride] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const images = useMemo(() => {
    const cat = CATEGORIES.find((c) => c.id === categoryId) || CATEGORIES[0];
    const filtered = ALL_VISUALS.filter(cat.filter).map((v) => ({
      path: `/visuals/${v.file}`,
      title: v.title,
      category: v.category,
    }));
    return shuffle(filtered);
  }, [categoryId]);

  useEffect(() => {
    setMounted(true);
    const update = () => setViewport({ w: window.innerWidth, h: window.innerHeight });
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  const tileCount = tileOverride ?? autoTileCount(viewport.w);
  const { cols, rows } = gridLayout(tileCount);

  // Each tile tracks its own current image index into the shuffled list
  const [tileIndices, setTileIndices] = useState<number[]>(() =>
    Array.from({ length: 9 }, (_, i) => i)
  );

  // Initialize tile indices when category changes
  useEffect(() => {
    if (images.length === 0) return;
    setTileIndices(Array.from({ length: 9 }, (_, i) => i % images.length));
  }, [images.length, categoryId]);

  // Each tile advances independently with staggered offsets
  useEffect(() => {
    if (!mounted || paused || images.length <= 1) return;

    const timers = Array.from({ length: tileCount }, (_, tileIdx) => {
      // Stagger: tile 0 advances at full interval, tile N advances with offset
      const offset = (TILE_INTERVAL_MS / tileCount) * tileIdx;
      const startDelay = setTimeout(() => {
        const interval = setInterval(() => {
          setTileIndices((prev) => {
            const copy = [...prev];
            // Pick a new index that isn't currently shown in any tile
            const shown = new Set(copy.slice(0, tileCount));
            let candidate = (copy[tileIdx] + tileCount) % images.length;
            let attempts = 0;
            while (shown.has(candidate) && attempts < images.length) {
              candidate = (candidate + 1) % images.length;
              attempts++;
            }
            copy[tileIdx] = candidate;
            return copy;
          });
        }, TILE_INTERVAL_MS);
        (startDelay as any)._interval = interval;
      }, offset);
      return startDelay;
    });

    return () => {
      timers.forEach((t: any) => {
        clearTimeout(t);
        if (t._interval) clearInterval(t._interval);
      });
    };
  }, [paused, images.length, mounted, tileCount]);

  // Keyboard controls
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.code === "Space") {
        e.preventDefault();
        setPaused((p) => !p);
      } else if (e.code === "ArrowRight") {
        setTileIndices((prev) => prev.map((i) => (i + 1) % Math.max(images.length, 1)));
      } else if (e.code === "ArrowLeft") {
        setTileIndices((prev) => prev.map((i) => (i - 1 + Math.max(images.length, 1)) % Math.max(images.length, 1)));
      } else if (e.key === "f" || e.key === "F") {
        if (document.fullscreenElement) {
          document.exitFullscreen();
        } else {
          containerRef.current?.requestFullscreen?.();
        }
      } else if (e.key === "h" || e.key === "H") {
        setHideUI((h) => !h);
      } else if (e.key === "c" || e.key === "C") {
        const currentIdx = CATEGORIES.findIndex((c) => c.id === categoryId);
        const nextCat = CATEGORIES[(currentIdx + 1) % CATEGORIES.length];
        setCategoryId(nextCat.id);
      } else if (e.key >= "1" && e.key <= "9") {
        setTileOverride(parseInt(e.key, 10));
      } else if (e.key === "0") {
        setTileOverride(null); // back to auto
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [images.length, categoryId]);

  if (!mounted || images.length === 0) {
    return (
      <div className="fixed inset-0 bg-black flex items-center justify-center">
        <p className="text-white/30 text-sm animate-pulse">Gathering the field...</p>
      </div>
    );
  }

  const activeTileIndices = tileIndices.slice(0, tileCount);

  return (
    <div ref={containerRef} className="fixed inset-0 bg-black overflow-hidden">
      {/* Grid of tiles */}
      <div
        className="absolute inset-0 grid gap-0.5"
        style={{
          gridTemplateColumns: `repeat(${cols}, 1fr)`,
          gridTemplateRows: `repeat(${rows}, 1fr)`,
        }}
      >
        {activeTileIndices.map((imgIdx, tileIdx) => {
          const img = images[imgIdx];
          return (
            <ImmersionTile key={`tile-${tileIdx}`} image={img} />
          );
        })}
      </div>

      {/* Gentle vignette over everything */}
      <div
        className="absolute inset-0 bg-gradient-to-t from-black/50 via-transparent to-black/20 pointer-events-none"
        style={{ zIndex: 5 }}
      />

      {/* Controls */}
      <div
        className={`absolute top-4 right-4 flex gap-2 transition-opacity duration-700 ${
          hideUI ? "opacity-0 pointer-events-none" : "opacity-60 hover:opacity-100"
        }`}
        style={{ zIndex: 10 }}
      >
        <div className="px-3 py-1.5 rounded-full bg-white/5 backdrop-blur-md border border-white/10 text-white/60 text-xs font-mono">
          {tileCount}× tiles · {viewport.w}w
        </div>
        <button
          onClick={() => setPaused((p) => !p)}
          className="px-3 py-1.5 rounded-full bg-white/5 hover:bg-white/10 backdrop-blur-md border border-white/10 text-white/70 text-xs transition-colors"
          title="Pause (space)"
        >
          {paused ? "▶ Resume" : "❚❚ Pause"}
        </button>
        <button
          onClick={() => containerRef.current?.requestFullscreen?.()}
          className="px-3 py-1.5 rounded-full bg-white/5 hover:bg-white/10 backdrop-blur-md border border-white/10 text-white/70 text-xs transition-colors"
          title="Fullscreen (f)"
        >
          ⛶
        </button>
      </div>

      {/* Category picker */}
      <div
        className={`absolute top-4 left-4 transition-opacity duration-700 ${
          hideUI ? "opacity-0 pointer-events-none" : "opacity-60 hover:opacity-100"
        }`}
        style={{ zIndex: 10 }}
      >
        <select
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
          className="px-3 py-1.5 rounded-full bg-white/5 hover:bg-white/10 backdrop-blur-md border border-white/10 text-white/70 text-xs transition-colors appearance-none cursor-pointer"
        >
          {CATEGORIES.map((c) => (
            <option key={c.id} value={c.id} className="bg-black text-white">
              {c.label}
            </option>
          ))}
        </select>
      </div>

      {/* Keyboard hints */}
      <KeyboardHints hideUI={hideUI} />

      {/* Exit link */}
      <div
        className={`absolute bottom-4 right-4 transition-opacity duration-700 ${
          hideUI ? "opacity-0 pointer-events-none" : "opacity-30 hover:opacity-100"
        }`}
        style={{ zIndex: 10 }}
      >
        <Link
          href="/vision"
          className="text-white/50 text-xs hover:text-white/90 transition-colors"
        >
          ← Leave the field
        </Link>
      </div>
    </div>
  );
}

// ─── Single tile: crossfades between current and next image ────────────────
function ImmersionTile({ image }: { image: ImageEntry }) {
  const [currentSrc, setCurrentSrc] = useState(image.path);
  const [prevSrc, setPrevSrc] = useState<string | null>(null);
  const [currentTitle, setCurrentTitle] = useState(image.title);
  const [fadeIn, setFadeIn] = useState(true);

  useEffect(() => {
    if (image.path === currentSrc) return;
    // New image arrived — crossfade it in
    setPrevSrc(currentSrc);
    setCurrentSrc(image.path);
    setCurrentTitle(image.title);
    setFadeIn(false);
    // Force reflow, then fade in
    requestAnimationFrame(() => {
      requestAnimationFrame(() => setFadeIn(true));
    });
    // Clear prevSrc after transition completes
    const t = setTimeout(() => setPrevSrc(null), TRANSITION_MS + 100);
    return () => clearTimeout(t);
  }, [image.path, image.title, currentSrc]);

  return (
    <div className="relative overflow-hidden bg-black group">
      {/* Previous image (fades out) */}
      {prevSrc && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={prevSrc}
          alt=""
          className="absolute inset-0 w-full h-full object-cover transition-opacity ease-in-out"
          style={{
            opacity: fadeIn ? 0 : 1,
            transitionDuration: `${TRANSITION_MS}ms`,
          }}
          aria-hidden="true"
        />
      )}
      {/* Current image (fades in) */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={currentSrc}
        alt={currentTitle}
        className="absolute inset-0 w-full h-full object-cover transition-opacity ease-in-out"
        style={{
          opacity: fadeIn ? 1 : 0,
          transitionDuration: `${TRANSITION_MS}ms`,
        }}
      />
      {/* Title — only visible on hover */}
      <div className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-black/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500">
        <p className="text-white/90 text-sm font-light">{currentTitle}</p>
      </div>
    </div>
  );
}

function KeyboardHints({ hideUI }: { hideUI: boolean }) {
  const [show, setShow] = useState(true);
  useEffect(() => {
    const t = setTimeout(() => setShow(false), 7000);
    return () => clearTimeout(t);
  }, []);
  if (!show || hideUI) return null;
  return (
    <div className="absolute bottom-8 left-1/2 -translate-x-1/2 pointer-events-none transition-opacity duration-1000" style={{ zIndex: 10 }}>
      <div className="flex gap-4 text-[10px] text-white/25 font-mono tracking-wider">
        <span>SPACE pause</span>
        <span>← → step</span>
        <span>F fullscreen</span>
        <span>C category</span>
        <span>1-9 tiles</span>
        <span>0 auto</span>
        <span>H hide UI</span>
      </div>
    </div>
  );
}
