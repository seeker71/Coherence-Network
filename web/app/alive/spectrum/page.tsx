"use client";

/**
 * /alive/spectrum — Frequency spectrum visualization.
 *
 * Every concept, contributor, and community has a unique frequency
 * signature shaped by content, connections, and attention. This page
 * renders them all in one view — a heatmap where each row is an entity
 * and each column is a frequency band.
 *
 * Concepts are colored by their text frequency (how alive the language).
 * Contributors are colored by which concepts they gave attention to.
 * The community is the superposition of all contributors.
 */

import React, { useEffect, useState } from "react";

const HZ_LABELS: Record<number, string> = {
  174: "174", 285: "285", 396: "396", 417: "417", 432: "432",
  528: "528", 639: "639", 741: "741", 852: "852", 963: "963",
};

const HZ_COLORS: Record<number, string> = {
  174: "#ef4444", 285: "#f97316", 396: "#eab308", 417: "#84cc16", 432: "#22c55e",
  528: "#06b6d4", 639: "#3b82f6", 741: "#8b5cf6", 852: "#a855f7", 963: "#ec4899",
};

type SpectrumEntity = {
  id: string;
  name?: string;
  primary_hz?: number;
  text_freq?: number;
  spectrum: Record<string, number>;
};

type SpectrumData = {
  hz_bands: number[];
  concepts: SpectrumEntity[];
  contributors: SpectrumEntity[];
  community: SpectrumEntity;
};

export default function SpectrumPage() {
  const [data, setData] = useState<SpectrumData | null>(null);
  const [hoveredEntity, setHoveredEntity] = useState<SpectrumEntity | null>(null);
  const [hoveredHz, setHoveredHz] = useState<number | null>(null);

  useEffect(() => {
    fetch("/data/spectrum-simulation.json")
      .then((r) => r.json())
      .then(setData)
      .catch(() => {});
  }, []);

  if (!data) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <p className="text-sm text-white/30 animate-pulse">Loading spectrum...</p>
      </div>
    );
  }

  const { hz_bands, concepts, contributors, community } = data;

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white/80 p-4 sm:p-8">
      <header className="mb-8 max-w-7xl mx-auto">
        <h1 className="text-2xl font-light tracking-tight">Frequency Spectrum</h1>
        <p className="text-sm text-white/30 mt-1">
          Every concept, contributor, and community carries a unique frequency signature.
        </p>
      </header>

      <div className="max-w-7xl mx-auto space-y-8">
        {/* Hz band header */}
        <div className="sticky top-0 z-10 bg-[#0a0a0f]/95 backdrop-blur-sm pb-2">
          <div className="flex items-center">
            <div className="w-48 shrink-0" />
            <div className="flex-1 flex">
              {hz_bands.map((hz) => (
                <div
                  key={hz}
                  className={`flex-1 text-center text-xs font-mono transition-opacity ${
                    hoveredHz === hz ? "opacity-100" : "opacity-40"
                  }`}
                  onMouseEnter={() => setHoveredHz(hz)}
                  onMouseLeave={() => setHoveredHz(null)}
                >
                  <div
                    className="w-3 h-3 rounded-full mx-auto mb-1"
                    style={{ backgroundColor: HZ_COLORS[hz] }}
                  />
                  {hz}
                </div>
              ))}
            </div>
            <div className="w-12 shrink-0 text-center text-xs text-white/20">txt</div>
          </div>
        </div>

        {/* Community spectrum — the superposition */}
        <section>
          <h2 className="text-xs uppercase tracking-widest text-white/20 mb-2 ml-48">Community</h2>
          <SpectrumRow
            entity={community}
            label="Commintire"
            hzBands={hz_bands}
            hoveredHz={hoveredHz}
            onHoverEntity={setHoveredEntity}
            onHoverHz={setHoveredHz}
            isHighlighted={hoveredEntity?.id === community.id}
            size="lg"
          />
        </section>

        {/* Contributor spectra */}
        <section>
          <h2 className="text-xs uppercase tracking-widest text-white/20 mb-2 ml-48">Contributors</h2>
          <div className="space-y-px">
            {contributors.map((c) => (
              <SpectrumRow
                key={c.id}
                entity={c}
                label={c.id}
                hzBands={hz_bands}
                hoveredHz={hoveredHz}
                onHoverEntity={setHoveredEntity}
                onHoverHz={setHoveredHz}
                isHighlighted={hoveredEntity?.id === c.id}
                size="md"
              />
            ))}
          </div>
        </section>

        {/* Concept spectra */}
        <section>
          <h2 className="text-xs uppercase tracking-widest text-white/20 mb-2 ml-48">Concepts</h2>
          <div className="space-y-px">
            {concepts.map((c) => (
              <SpectrumRow
                key={c.id}
                entity={c}
                label={c.name || c.id}
                hzBands={hz_bands}
                hoveredHz={hoveredHz}
                onHoverEntity={setHoveredEntity}
                onHoverHz={setHoveredHz}
                isHighlighted={hoveredEntity?.id === c.id}
                textFreq={c.text_freq}
                primaryHz={c.primary_hz}
                size="sm"
              />
            ))}
          </div>
        </section>
      </div>

      {/* Hover detail */}
      {hoveredEntity && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 rounded-xl bg-black/80 backdrop-blur-xl border border-white/10 px-5 py-3 text-xs max-w-md">
          <span className="font-medium text-white">
            {hoveredEntity.name || hoveredEntity.id}
          </span>
          {hoveredEntity.primary_hz && (
            <span className="ml-2 text-white/40">
              Primary: {hoveredEntity.primary_hz} Hz
            </span>
          )}
          {hoveredEntity.text_freq != null && (
            <span className="ml-2 text-white/40">
              Text: {hoveredEntity.text_freq}
            </span>
          )}
          <div className="flex gap-1 mt-2">
            {hz_bands.map((hz) => {
              const val = hoveredEntity.spectrum[String(hz)] ?? 0;
              return (
                <div key={hz} className="flex-1 text-center">
                  <div
                    className="h-6 rounded-sm mx-auto"
                    style={{
                      width: "100%",
                      backgroundColor: HZ_COLORS[hz],
                      opacity: 0.15 + val * 0.85,
                    }}
                  />
                  <span className="text-white/30 text-[9px]">{val > 0 ? val.toFixed(1) : ""}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Legend */}
      <footer className="max-w-7xl mx-auto mt-12 pt-6 border-t border-white/5">
        <div className="flex flex-wrap gap-4 text-xs text-white/20">
          <span>Brightness = energy at that frequency</span>
          <span>·</span>
          <span>Community = superposition of all contributors</span>
          <span>·</span>
          <span>Contributor spectrum shaped by attention</span>
          <span>·</span>
          <span>Concept spectrum sensed from text + graph connections</span>
        </div>
        <div className="mt-4">
          <a href="/alive" className="text-xs text-white/20 hover:text-white/50 transition-colors">
            ← Pulse
          </a>
        </div>
      </footer>
    </div>
  );
}

function SpectrumRow({
  entity,
  label,
  hzBands,
  hoveredHz,
  onHoverEntity,
  onHoverHz,
  isHighlighted,
  textFreq,
  primaryHz,
  size = "sm",
}: {
  entity: SpectrumEntity;
  label: string;
  hzBands: number[];
  hoveredHz: number | null;
  onHoverEntity: (e: SpectrumEntity | null) => void;
  onHoverHz: (hz: number | null) => void;
  isHighlighted: boolean;
  textFreq?: number;
  primaryHz?: number;
  size?: "sm" | "md" | "lg";
}) {
  const height = size === "lg" ? "h-8" : size === "md" ? "h-6" : "h-4";

  return (
    <div
      className={`flex items-center group transition-opacity ${
        isHighlighted ? "opacity-100" : "opacity-80 hover:opacity-100"
      }`}
      onMouseEnter={() => onHoverEntity(entity)}
      onMouseLeave={() => onHoverEntity(null)}
    >
      {/* Label */}
      <div className="w-48 shrink-0 pr-3 text-right">
        <span className={`text-xs truncate block ${
          isHighlighted ? "text-white" : "text-white/40 group-hover:text-white/70"
        } transition-colors`}>
          {label}
        </span>
      </div>

      {/* Spectrum bars */}
      <div className="flex-1 flex gap-px">
        {hzBands.map((hz) => {
          const val = entity.spectrum[String(hz)] ?? 0;
          const isPrimary = primaryHz === hz;
          const isHovered = hoveredHz === hz;

          return (
            <div
              key={hz}
              className={`flex-1 ${height} rounded-sm relative transition-all ${
                isHovered ? "ring-1 ring-white/20" : ""
              }`}
              style={{
                backgroundColor: HZ_COLORS[hz],
                opacity: val < 0.05 ? 0.03 : 0.08 + val * 0.92,
              }}
              onMouseEnter={() => onHoverHz(hz)}
              onMouseLeave={() => onHoverHz(null)}
            >
              {isPrimary && (
                <div className="absolute inset-x-0 bottom-0 h-0.5 bg-white/60 rounded-full" />
              )}
            </div>
          );
        })}
      </div>

      {/* Text frequency indicator */}
      <div className="w-12 shrink-0 text-center">
        {textFreq != null && (
          <span className="text-[10px] text-white/20">{textFreq.toFixed(2)}</span>
        )}
      </div>
    </div>
  );
}
