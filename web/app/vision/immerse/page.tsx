"use client";

/**
 * /vision/immerse — The vision surrounding you.
 *
 * Full-screen immersive viewer. Images crossfade slowly (12s each).
 * Leave it running on a second monitor, in a browser tab, on a tablet
 * on the kitchen counter. The vision's frequency held in your field
 * throughout the day.
 *
 * Controls:
 *   space   pause/resume
 *   ← →     previous/next
 *   f       toggle fullscreen
 *   c       cycle category
 *   h       hide/show UI
 *   esc     exit
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
  description: string;
  filter: (img: VisualSource) => boolean;
};

// All curated visuals — each carries a piece of the vision's frequency
const ALL_VISUALS: { file: string; title: string; category: string }[] = [
  // Concepts (primary vision illustrations)
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

  // Ceremony & Practice
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

  // Joy & Play
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

  // Nourishment & Land
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

  // Spaces & Shelter
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

  // Community & Network
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

  // Scales & Harmony
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
  { id: "all", label: "All", description: "Everything — let it wander", filter: () => true },
  { id: "ceremony", label: "Ceremony & Presence", description: "Fire circles, breath, song", filter: (i) => i.category === "ceremony" },
  { id: "joy", label: "Joy & Play", description: "Celebration, movement, children", filter: (i) => i.category === "joy" },
  { id: "nourishment", label: "Nourishment & Land", description: "Food forest, shared meals, soil", filter: (i) => i.category === "nourishment" },
  { id: "space", label: "Spaces", description: "Hearths, nests, temples, villages", filter: (i) => i.category === "space" },
  { id: "community", label: "Community", description: "Communities already living this", filter: (i) => i.category === "community" },
  { id: "concept", label: "Concepts", description: "Primary vision illustrations", filter: (i) => i.category === "concept" },
  { id: "scale", label: "Scales", description: "Seed to grove, individual to field", filter: (i) => i.category === "scale" },
];

const DEFAULT_INTERVAL_MS = 12000;
const TRANSITION_MS = 2500;

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export default function ImmersePage() {
  const [categoryId, setCategoryId] = useState<string>("all");
  const [paused, setPaused] = useState(false);
  const [hideUI, setHideUI] = useState(false);
  const [index, setIndex] = useState(0);
  const [mounted, setMounted] = useState(false);
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

  // Prevent hydration mismatch on shuffle
  useEffect(() => { setMounted(true); }, []);

  // Auto-advance
  useEffect(() => {
    if (!mounted || paused || images.length <= 1) return;
    const timer = setInterval(() => {
      setIndex((i) => (i + 1) % images.length);
    }, DEFAULT_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [paused, images.length, mounted]);

  // Reset index when category changes
  useEffect(() => { setIndex(0); }, [categoryId]);

  // Keyboard controls
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.code === "Space") {
        e.preventDefault();
        setPaused((p) => !p);
      } else if (e.code === "ArrowRight") {
        setIndex((i) => (i + 1) % Math.max(images.length, 1));
      } else if (e.code === "ArrowLeft") {
        setIndex((i) => (i - 1 + Math.max(images.length, 1)) % Math.max(images.length, 1));
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

  const current = images[index];
  const next = images[(index + 1) % images.length];

  return (
    <div ref={containerRef} className="fixed inset-0 bg-black overflow-hidden">
      {/* Stacked image layers — each image gets its own layer that crossfades */}
      {images.map((img, i) => {
        const isCurrent = i === index;
        return (
          <div
            key={img.path}
            className="absolute inset-0 transition-opacity ease-in-out"
            style={{
              opacity: isCurrent ? 1 : 0,
              transitionDuration: `${TRANSITION_MS}ms`,
              zIndex: isCurrent ? 2 : 1,
            }}
            aria-hidden={!isCurrent}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={img.path}
              alt={img.title}
              className="w-full h-full object-cover"
              loading={Math.abs(i - index) <= 2 ? "eager" : "lazy"}
            />
          </div>
        );
      })}

      {/* Gentle vignette over everything */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-black/30 pointer-events-none" style={{ zIndex: 3 }} />

      {/* Preload next image */}
      <div className="absolute opacity-0 pointer-events-none" aria-hidden="true">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={next.path} alt="" />
      </div>

      {/* Title (fades with UI) */}
      <div
        className={`absolute bottom-12 left-0 right-0 px-8 text-center transition-opacity duration-700 ${
          hideUI ? "opacity-0" : "opacity-100"
        }`}
        style={{ zIndex: 10 }}
      >
        <p className="text-white/90 text-2xl md:text-3xl font-light tracking-wide drop-shadow-lg">
          {current.title}
        </p>
        <p className="text-white/40 text-xs mt-2 tracking-widest uppercase">
          {current.category}
        </p>
      </div>

      {/* Controls (fades with UI) */}
      <div
        className={`absolute top-4 right-4 flex gap-2 transition-opacity duration-700 ${
          hideUI ? "opacity-0 pointer-events-none" : "opacity-70 hover:opacity-100"
        }`}
        style={{ zIndex: 10 }}
      >
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

      {/* Category picker (fades with UI) */}
      <div
        className={`absolute top-4 left-4 transition-opacity duration-700 ${
          hideUI ? "opacity-0 pointer-events-none" : "opacity-70 hover:opacity-100"
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

      {/* Keyboard hints (fades after 5s) */}
      <KeyboardHints hideUI={hideUI} />

      {/* Progress indicator */}
      <div
        className={`absolute bottom-0 left-0 right-0 h-0.5 bg-white/5 transition-opacity duration-700 ${
          hideUI ? "opacity-0" : "opacity-40"
        }`}
        style={{ zIndex: 10 }}
      >
        <div
          key={`progress-${index}-${paused}`}
          className={`h-full bg-white/40 ${paused ? "" : "animate-progress"}`}
          style={{
            animationDuration: `${DEFAULT_INTERVAL_MS}ms`,
            animationTimingFunction: "linear",
            animationFillMode: "forwards",
            animationPlayState: paused ? "paused" : "running",
          }}
        />
      </div>

      {/* Exit link */}
      <div
        className={`absolute bottom-4 right-4 transition-opacity duration-700 ${
          hideUI ? "opacity-0 pointer-events-none" : "opacity-40 hover:opacity-100"
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

      <style jsx>{`
        @keyframes progress {
          from { width: 0%; }
          to { width: 100%; }
        }
        .animate-progress {
          animation-name: progress;
        }
      `}</style>
    </div>
  );
}

function KeyboardHints({ hideUI }: { hideUI: boolean }) {
  const [show, setShow] = useState(true);
  useEffect(() => {
    const t = setTimeout(() => setShow(false), 6000);
    return () => clearTimeout(t);
  }, []);
  if (!show || hideUI) return null;
  return (
    <div className="absolute bottom-20 left-1/2 -translate-x-1/2 pointer-events-none transition-opacity duration-1000">
      <div className="flex gap-4 text-[10px] text-white/30 font-mono tracking-wider">
        <span>SPACE pause</span>
        <span>← → nav</span>
        <span>F fullscreen</span>
        <span>C category</span>
        <span>H hide UI</span>
      </div>
    </div>
  );
}
