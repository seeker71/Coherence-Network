"use client";

import { useState } from "react";
import { getApiBase } from "@/lib/api";

type NearbyContributor = {
  contributor_id: string;
  name: string;
  city: string;
  country: string;
  distance_km: number;
  coherence_score: number | null;
};

type NearbyIdea = {
  idea_id: string;
  title: string;
  contributor_id: string;
  contributor_name: string;
  city: string;
  country: string;
  distance_km: number;
};

type NearbyResult = {
  contributors: NearbyContributor[];
  ideas: NearbyIdea[];
  query_lat: number;
  query_lon: number;
  radius_km: number;
  total_contributors: number;
  total_ideas: number;
};

export default function NearbyPage() {
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [radius, setRadius] = useState("100");
  const [result, setResult] = useState<NearbyResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function useMyLocation() {
    if (!navigator.geolocation) {
      setError("Geolocation not supported by this browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude.toFixed(4));
        setLon(pos.coords.longitude.toFixed(4));
      },
      () => setError("Could not get your location. Please enter coordinates manually."),
    );
  }

  async function search(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    const parsedLat = parseFloat(lat);
    const parsedLon = parseFloat(lon);
    const parsedRadius = parseFloat(radius);

    if (isNaN(parsedLat) || isNaN(parsedLon)) {
      setError("Please enter valid latitude and longitude.");
      return;
    }

    setLoading(true);
    try {
      const params = new URLSearchParams({
        lat: parsedLat.toString(),
        lon: parsedLon.toString(),
        radius_km: parsedRadius.toString(),
      });
      const res = await fetch(`${getApiBase()}/api/nearby?${params}`);
      if (!res.ok) {
        const text = await res.text();
        setError(`API error ${res.status}: ${text}`);
        return;
      }
      const data: NearbyResult = await res.json();
      setResult(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="max-w-3xl mx-auto px-4 py-8 space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Nearby Contributors &amp; Ideas</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Find contributors and ideas close to a location. Only city-level coordinates are stored —
          exact addresses are never shared.
        </p>
      </div>

      <form onSubmit={search} className="space-y-4 border rounded-lg p-4">
        <div className="flex gap-2">
          <div className="flex-1 space-y-1">
            <label className="text-sm font-medium" htmlFor="lat">
              Latitude
            </label>
            <input
              id="lat"
              type="number"
              step="any"
              min="-90"
              max="90"
              value={lat}
              onChange={(e) => setLat(e.target.value)}
              placeholder="-23.5505"
              className="w-full border rounded px-3 py-2 text-sm"
              required
            />
          </div>
          <div className="flex-1 space-y-1">
            <label className="text-sm font-medium" htmlFor="lon">
              Longitude
            </label>
            <input
              id="lon"
              type="number"
              step="any"
              min="-180"
              max="180"
              value={lon}
              onChange={(e) => setLon(e.target.value)}
              placeholder="-46.6333"
              className="w-full border rounded px-3 py-2 text-sm"
              required
            />
          </div>
          <div className="w-28 space-y-1">
            <label className="text-sm font-medium" htmlFor="radius">
              Radius (km)
            </label>
            <input
              id="radius"
              type="number"
              min="1"
              max="20000"
              value={radius}
              onChange={(e) => setRadius(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={useMyLocation}
            className="text-sm border rounded px-3 py-2 hover:bg-muted transition-colors"
          >
            Use my location
          </button>
          <button
            type="submit"
            disabled={loading}
            className="text-sm bg-primary text-primary-foreground rounded px-4 py-2 hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {loading ? "Searching…" : "Search nearby"}
          </button>
        </div>

        {error && (
          <p className="text-sm text-destructive border border-destructive/30 rounded px-3 py-2">
            {error}
          </p>
        )}
      </form>

      {result && (
        <div className="space-y-6">
          <p className="text-sm text-muted-foreground">
            Found <strong>{result.total_contributors}</strong> contributor
            {result.total_contributors !== 1 ? "s" : ""} and{" "}
            <strong>{result.total_ideas}</strong> idea{result.total_ideas !== 1 ? "s" : ""} within{" "}
            {result.radius_km} km.
          </p>

          {/* Contributors */}
          {result.contributors.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-2">Contributors</h2>
              <div className="space-y-2">
                {result.contributors.map((c) => (
                  <div
                    key={c.contributor_id}
                    className="border rounded-lg px-4 py-3 flex items-center justify-between"
                  >
                    <div>
                      <span className="font-medium">{c.name}</span>
                      <span className="ml-2 text-sm text-muted-foreground">
                        {c.city}, {c.country}
                      </span>
                    </div>
                    <div className="text-right text-sm text-muted-foreground">
                      <div>{c.distance_km} km away</div>
                      {c.coherence_score != null && (
                        <div>Score: {c.coherence_score.toFixed(2)}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Ideas */}
          {result.ideas.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-2">Ideas from this area</h2>
              <div className="space-y-2">
                {result.ideas.map((idea) => (
                  <div key={idea.idea_id} className="border rounded-lg px-4 py-3">
                    <div className="font-medium">{idea.title || idea.idea_id}</div>
                    <div className="text-sm text-muted-foreground mt-0.5">
                      by {idea.contributor_name} · {idea.city}, {idea.country} ·{" "}
                      {idea.distance_km} km
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {result.contributors.length === 0 && result.ideas.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No contributors have shared their location in this area yet.
            </p>
          )}
        </div>
      )}
    </main>
  );
}
