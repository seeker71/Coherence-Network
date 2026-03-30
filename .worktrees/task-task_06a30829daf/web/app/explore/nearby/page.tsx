"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

type NearbyContributor = {
  contributor_id: string;
  name: string;
  city: string;
  country: string;
  distance_km: number;
  coherence_score?: number;
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

export default function NearbyExplorerPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<NearbyResult | null>(null);
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [radius, setRadius] = useState(100);

  useEffect(() => {
    if (!navigator.geolocation) {
      setError("Geolocation is not supported by your browser.");
      setLoading(false);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setCoords({
          lat: position.coords.latitude,
          lon: position.coords.longitude,
        });
      },
      (err) => {
        setError(`Failed to get location: ${err.message}`);
        setLoading(false);
      }
    );
  }, []);

  useEffect(() => {
    if (!coords) return;

    async function fetchNearby() {
      setLoading(true);
      try {
        const base = getApiBase();
        const res = await fetch(
          `${base}/api/nearby?lat=${coords!.lat}&lon=${coords!.lon}&radius_km=${radius}`
        );
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const data = await res.json();
        setResults(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    fetchNearby();
  }, [coords, radius]);

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">Nearby Network</h1>

      {error && (
        <div className="bg-destructive/10 text-destructive p-4 rounded-md mb-6">
          {error}
        </div>
      )}

      <div className="flex flex-col md:flex-row gap-8">
        <aside className="w-full md:w-64">
          <div className="bg-card border rounded-lg p-4 sticky top-4">
            <h2 className="font-semibold mb-4">Filters</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">
                  Radius: {radius} km
                </label>
                <input
                  type="range"
                  min="5"
                  max="1000"
                  step="5"
                  value={radius}
                  onChange={(e) => setRadius(parseInt(e.target.value))}
                  className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer"
                />
              </div>
              {coords && (
                <div className="text-xs text-muted-foreground">
                  Querying near: {coords.lat.toFixed(2)}, {coords.lon.toFixed(2)}
                </div>
              )}
            </div>
          </div>
        </aside>

        <main className="flex-1">
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-12">
              <section>
                <h2 className="text-xl font-semibold mb-4">
                  Nearby Contributors ({results?.total_contributors || 0})
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {results?.contributors.map((c) => (
                    <div key={c.contributor_id} className="bg-card border rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow">
                      <Link href={`/contributors/${c.contributor_id}/portfolio`}>
                        <h3 className="font-bold text-lg hover:text-primary transition-colors">
                          {c.name}
                        </h3>
                      </Link>
                      <div className="text-sm text-muted-foreground">
                        {c.city}, {c.country}
                      </div>
                      <div className="mt-2 text-sm font-medium">
                        {c.distance_km} km away
                      </div>
                      {c.coherence_score !== undefined && (
                        <div className="mt-1 text-xs">
                          Coherence: {(c.coherence_score * 100).toFixed(0)}%
                        </div>
                      )}
                    </div>
                  ))}
                  {!results?.contributors.length && (
                    <p className="text-muted-foreground col-span-full py-4 italic">
                      No contributors found in this radius.
                    </p>
                  )}
                </div>
              </section>

              <section>
                <h2 className="text-xl font-semibold mb-4">
                  Nearby Ideas ({results?.total_ideas || 0})
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {results?.ideas.map((i) => (
                    <div key={i.idea_id} className="bg-card border rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow flex flex-col justify-between">
                      <div>
                        <Link href={`/contributors/${i.contributor_id}/portfolio/ideas/${i.idea_id}`}>
                          <h3 className="font-bold text-lg hover:text-primary transition-colors line-clamp-2">
                            {i.title}
                          </h3>
                        </Link>
                        <div className="text-xs text-muted-foreground mt-1">
                          by {i.contributor_name} ({i.city})
                        </div>
                      </div>
                      <div className="mt-4 text-sm font-medium border-t pt-2">
                        {i.distance_km} km away
                      </div>
                    </div>
                  ))}
                  {!results?.ideas.length && (
                    <p className="text-muted-foreground col-span-full py-4 italic">
                      No ideas found in this radius.
                    </p>
                  )}
                </div>
              </section>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
