import type { Metadata } from "next";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "The Gathering — The Living Collective",
  description: "People who feel the field forming. A consent-based community directory — everyone here has chosen to be visible.",
};

export const dynamic = "force-dynamic";

type CommunityMember = {
  id: string;
  name: string;
  location?: string;
  skills?: string;
  offering?: string;
  resonant_roles: string[];
};

type InterestStats = {
  total_interested: number;
  findable_count: number;
  role_interest: Record<string, number>;
  location_regions: Record<string, number>;
};

const ROLE_LABELS: Record<string, string> = {
  "living-structure-weaver": "Living-structure weaver",
  "nourishment-alchemist": "Nourishment alchemist",
  "frequency-holder": "Frequency holder",
  "vitality-keeper": "Vitality keeper",
  "transmission-source": "Transmission source",
  "form-grower": "Form-grower",
};

const ROLE_COLORS: Record<string, string> = {
  "living-structure-weaver": "bg-amber-500/10 text-amber-400/80 border-amber-500/20",
  "nourishment-alchemist": "bg-emerald-500/10 text-emerald-400/80 border-emerald-500/20",
  "frequency-holder": "bg-violet-500/10 text-violet-400/80 border-violet-500/20",
  "vitality-keeper": "bg-rose-500/10 text-rose-400/80 border-rose-500/20",
  "transmission-source": "bg-sky-500/10 text-sky-400/80 border-sky-500/20",
  "form-grower": "bg-orange-500/10 text-orange-400/80 border-orange-500/20",
};

export default async function CommunityPage() {
  const base = getApiBase();

  const [membersRes, statsRes] = await Promise.all([
    fetch(`${base}/api/interest/community?limit=200`, { next: { revalidate: 30 } }).then((r) => r.json()).catch(() => []),
    fetch(`${base}/api/interest/stats`, { next: { revalidate: 30 } }).then((r) => r.json()).catch(() => ({ total_interested: 0, findable_count: 0, role_interest: {}, location_regions: {} })),
  ]);

  const members: CommunityMember[] = Array.isArray(membersRes) ? membersRes : [];
  const stats: InterestStats = statsRes;

  return (
    <main className="max-w-5xl mx-auto px-6 py-20 space-y-20">
      {/* Hero */}
      <section className="text-center space-y-8">
        <h1 className="text-4xl md:text-6xl font-extralight tracking-tight text-white">
          The{" "}
          <span className="bg-gradient-to-r from-amber-300 via-teal-300 to-violet-300 bg-clip-text text-transparent">
            gathering
          </span>
        </h1>
        <p className="text-xl text-stone-400 font-light leading-relaxed max-w-2xl mx-auto">
          People who feel the field forming. Everyone here has chosen to be
          visible. Consent first, always.
        </p>
      </section>

      {/* Stats */}
      {stats.total_interested > 0 && (
        <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-6 rounded-2xl border border-stone-800/30 bg-stone-900/20 text-center space-y-2">
            <div className="text-3xl font-light text-amber-300/80">{stats.total_interested}</div>
            <div className="text-xs text-stone-600 uppercase tracking-wider">souls resonating</div>
          </div>
          <div className="p-6 rounded-2xl border border-stone-800/30 bg-stone-900/20 text-center space-y-2">
            <div className="text-3xl font-light text-teal-300/80">{stats.findable_count}</div>
            <div className="text-xs text-stone-600 uppercase tracking-wider">publicly visible</div>
          </div>
          <div className="p-6 rounded-2xl border border-stone-800/30 bg-stone-900/20 text-center space-y-2">
            <div className="text-3xl font-light text-violet-300/80">
              {Object.keys(stats.location_regions).length}
            </div>
            <div className="text-xs text-stone-600 uppercase tracking-wider">regions</div>
          </div>
          <div className="p-6 rounded-2xl border border-stone-800/30 bg-stone-900/20 text-center space-y-2">
            <div className="text-3xl font-light text-rose-300/80">
              {Object.values(stats.role_interest).reduce((a, b) => a + b, 0)}
            </div>
            <div className="text-xs text-stone-600 uppercase tracking-wider">role resonances</div>
          </div>
        </section>
      )}

      {/* Members */}
      {members.length > 0 ? (
        <section className="space-y-8">
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {members.map((member) => (
              <div
                key={member.id}
                className="p-6 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-3 hover:border-stone-700/40 transition-all"
              >
                <h3 className="text-lg font-light text-stone-200">{member.name}</h3>
                {member.location && (
                  <p className="text-sm text-stone-500">{member.location}</p>
                )}
                {member.skills && (
                  <p className="text-sm text-stone-400 leading-relaxed">{member.skills}</p>
                )}
                {member.offering && (
                  <p className="text-sm text-stone-500 italic leading-relaxed">{member.offering}</p>
                )}
                {member.resonant_roles.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {member.resonant_roles.map((role) => (
                      <span
                        key={role}
                        className={`text-xs px-2 py-0.5 rounded-full border ${
                          ROLE_COLORS[role] || "bg-stone-800/30 text-stone-500 border-stone-700/30"
                        }`}
                      >
                        {ROLE_LABELS[role] || role}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      ) : (
        <section className="text-center space-y-6 py-12">
          <div className="text-5xl opacity-30">◉</div>
          <p className="text-stone-500 text-lg">
            The directory is forming. Be among the first to make yourself
            visible.
          </p>
        </section>
      )}

      {/* CTA */}
      <section className="text-center space-y-6 py-8 border-t border-stone-800/20">
        <p className="text-stone-500">
          Want to be part of this? Express your interest and choose what to
          share.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/vision/join#register"
            className="px-8 py-3 rounded-xl bg-gradient-to-r from-amber-500/10 via-teal-500/10 to-violet-500/10 border border-amber-500/20 text-amber-300/90 hover:from-amber-500/20 hover:via-teal-500/20 hover:to-violet-500/20 transition-all font-medium"
          >
            Join the field
          </Link>
          <Link
            href="/vision"
            className="px-8 py-3 rounded-xl bg-stone-900/40 border border-stone-800/40 text-stone-400 hover:text-stone-300 hover:border-stone-700/40 transition-all font-medium"
          >
            Explore the vision
          </Link>
        </div>
      </section>
    </main>
  );
}
