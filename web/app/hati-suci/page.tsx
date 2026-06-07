// Hati Suci — the resident-service nervous system (first Light Hub membrane).
// Mobile-first, bilingual. Light identity: a device token remembers you;
// residents invite others by name + role via a WhatsApp-shareable link that
// auto-registers and binds them on first tap. Seeing is open to any registered
// cell; writing (asking, tending, settling) needs a resident's vouch.
"use client";

import QRCode from "qrcode";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useT } from "@/components/MessagesProvider";

type Role = "resident" | "staff" | "member";
type Member = {
  id: string;
  name: string;
  role: Role;
  write_access: boolean;
  status: string;
  token: string;
  phone?: string | null;
  invited_by_name?: string | null;
  at_place?: string | null;
};
type PublicMember = {
  id: string;
  name: string;
  role: Role;
  write_access: boolean;
  status: string;
  invited_by_name?: string | null;
  created_at: string;
  at_place?: string | null;
  at_place_name?: string | null;
  at_place_since?: string | null; // ISO of last report — the decay clock
};

// A place cell at Hati Suci (household-membrane.form: place).
type Place = {
  id: string;
  name: string;
  kind: string; // house | gathering | tended | organ
  lat?: number | null;
  lon?: number | null;
  wifi?: string | null;
  pinned?: boolean;
};

// Where each place sits on the grounds, 0–100% of the map box — read from the
// at-hati-suci layout in household-membrane.form (NW temple/kitchen/office;
// N brahma/krishna/bhima; center vishnu+bale+pool with fire-pit on its north
// edge; E arjuna/yoga-studio; SW ganesha; S wormery/vibration/water-garden/
// fish-pond; W gardens). GPS pins refine this when a place is pinned on site.
const LAYOUT: Record<string, { x: number; y: number }> = {
  "place-temple": { x: 16, y: 14 }, "place-kitchen": { x: 28, y: 11 },
  "place-office": { x: 22, y: 22 }, "place-compost-shed": { x: 10, y: 24 },
  "place-brahma": { x: 44, y: 12 }, "place-krishna": { x: 55, y: 11 },
  "place-bhima": { x: 66, y: 14 },
  "place-vishnu": { x: 49, y: 44 }, "place-bale-vishnu": { x: 58, y: 47 },
  "place-fire-pit": { x: 49, y: 50 }, "place-pool": { x: 49, y: 58 },
  "place-arjuna": { x: 81, y: 38 }, "place-yoga-studio": { x: 84, y: 52 },
  "place-ganesha": { x: 17, y: 78 },
  "place-wormery": { x: 38, y: 82 }, "place-bale-wormery": { x: 46, y: 86 },
  "place-vibration-tunnel": { x: 56, y: 85 }, "place-water-garden": { x: 66, y: 82 },
  "place-fish-pond": { x: 74, y: 86 },
  "place-gardens": { x: 9, y: 50 }, "place-entrance": { x: 30, y: 93 },
};

const KIND_COLOR: Record<string, string> = {
  house: "#a78bfa", gathering: "#38bdf8", tended: "#34d399", organ: "#fbbf24",
};

// Visual decay: how present a report still looks, from the age of its last
// report. Fresh (<2 min) = full; fades over the next ~13 min; gone after ~15.
// Knowing fades when circulation stops — lc-the-trace-is-the-memory, made visible.
function presenceLife(since?: string | null): number {
  if (!since) return 0;
  const ms = Date.now() - new Date(since).getTime();
  if (!isFinite(ms) || ms < 0) return 1;
  const FRESH = 2 * 60_000;
  const GONE = 15 * 60_000;
  if (ms <= FRESH) return 1;
  if (ms >= GONE) return 0;
  return 1 - (ms - FRESH) / (GONE - FRESH);
}

type Kind = "food" | "laundry" | "cleaning" | "ride" | "repair" | "room" | "supplies" | "other";
type Status = "open" | "acknowledged" | "in_progress" | "completed" | "cancelled";

// One market line, stored structurally so the board re-renders in EACH
// viewer's tongue: id is language-free; label/unit are snapshots used as a
// fallback when the catalog doesn't know the id (custom items).
type RequestItem = { id: string; qty: number; unit?: string; label?: string };

// A friend event, read from the shared Google Calendar (the calendar is the
// store; the app only reads its iCal feed). household-membrane.form: calendar-port.
type FriendEvent = {
  title: string;
  start: string;
  end?: string | null;
  all_day?: boolean;
  location?: string | null;
  description?: string | null;
  source?: string | null;
};

// A gathering / question raised to the field — everyone it reaches answers,
// and the tally is open to all (household-membrane.form: gathering).
type GatheringTally = {
  interested: number; yes: number; no: number; yes_plus_one: number; heads: number; voters: number;
};
type GatheringVote = { voter_name: string; choice: string };
type Gathering = {
  id: string;
  text: string;
  author_name: string;
  audience_kind: string;
  audience_value: string;
  kind: string;
  status?: string | null;
  where?: string | null;
  when_text?: string | null;
  raised_at: string;
  my_choice?: string | null;
  tally: GatheringTally;
  votes: GatheringVote[];
};

type ServiceRequest = {
  id: string;
  kind: Kind;
  detail: string;
  items?: RequestItem[];
  location?: string | null;
  when_text?: string | null;
  status: Status;
  requester_id: string;
  requester_name: string;
  acknowledged_by_name?: string | null;
  completed_by_name?: string | null;
  cost_amount?: number | null;
  cost_currency?: string;
  cost_note?: string | null;
  cost_status?: "none" | "recorded" | "paid";
  paid_by_name?: string | null;
  created_at: string;
  updated_at: string;
};

const KINDS: { key: Kind; emoji: string }[] = [
  { key: "food", emoji: "🍲" },
  { key: "laundry", emoji: "🧺" },
  { key: "cleaning", emoji: "🧹" },
  { key: "ride", emoji: "🛵" },
  { key: "repair", emoji: "🔧" },
  { key: "room", emoji: "🛏️" },
  { key: "supplies", emoji: "🛒" },
  { key: "other", emoji: "✨" },
];

// ── The market near Hati Suci ───────────────────────────────────────
// A projection of the catalog whose shape + proportions live in the body:
// docs/coherence-substrate/household-membrane.form (market). Each item
// carries its label in every tongue, so the board renders in the VIEWER's
// language — the resident reads "rice", the staff who shops reads "beras",
// from one cell. Amounts use the pasar's own measures (kg, ikat = bunch,
// sisir = comb, ons = 100 g, butir = each), never bare counts. (g4 will
// serve this from /api/household/market so there is a single source.)
type Lang = "en" | "id" | "de" | "es";
type L = { en: string; id: string; de?: string; es?: string };
type MarketGroup = "fruit" | "veg" | "bumbu" | "pokok";
type MarketItem = { id: string; e: string; g: MarketGroup; l: L; u: L; step: number; start: number };

const U = {
  comb: { en: "comb", id: "sisir" },
  bunch: { en: "bunch", id: "ikat" },
  kg: { en: "kg", id: "kg" },
  ons: { en: "100g", id: "ons" },
  pcs: { en: "pcs", id: "buah" },
  butir: { en: "pcs", id: "butir" },
  potong: { en: "pcs", id: "potong" },
  pack: { en: "pack", id: "bungkus" },
  bottle: { en: "bottle", id: "botol" },
} as const;

const MARKET: MarketItem[] = [
  // fruit (buah)
  { id: "pisang", e: "🍌", g: "fruit", l: { en: "banana", id: "pisang" }, u: U.comb, step: 1, start: 1 },
  { id: "pepaya", e: "🍈", g: "fruit", l: { en: "papaya", id: "pepaya" }, u: U.pcs, step: 1, start: 1 },
  { id: "mangga", e: "🥭", g: "fruit", l: { en: "mango", id: "mangga" }, u: U.pcs, step: 1, start: 1 },
  { id: "alpukat", e: "🥑", g: "fruit", l: { en: "avocado", id: "alpukat" }, u: U.pcs, step: 1, start: 1 },
  { id: "nanas", e: "🍍", g: "fruit", l: { en: "pineapple", id: "nanas" }, u: U.pcs, step: 1, start: 1 },
  { id: "semangka", e: "🍉", g: "fruit", l: { en: "watermelon", id: "semangka" }, u: U.pcs, step: 1, start: 1 },
  { id: "naga", e: "🐉", g: "fruit", l: { en: "dragonfruit", id: "buah naga" }, u: U.pcs, step: 1, start: 1 },
  { id: "kelapa", e: "🥥", g: "fruit", l: { en: "coconut", id: "kelapa" }, u: U.butir, step: 1, start: 1 },
  { id: "jeruk", e: "🍊", g: "fruit", l: { en: "orange", id: "jeruk" }, u: U.kg, step: 1, start: 1 },
  { id: "nipis", e: "🍋", g: "fruit", l: { en: "lime", id: "jeruk nipis" }, u: U.ons, step: 1, start: 1 },
  { id: "salak", e: "🟤", g: "fruit", l: { en: "snakefruit", id: "salak" }, u: U.ons, step: 1, start: 1 },
  // veg (sayur)
  { id: "kangkung", e: "🥬", g: "veg", l: { en: "water spinach", id: "kangkung" }, u: U.bunch, step: 1, start: 1 },
  { id: "bayam", e: "🌿", g: "veg", l: { en: "spinach", id: "bayam" }, u: U.bunch, step: 1, start: 1 },
  { id: "kacang-panjang", e: "🫛", g: "veg", l: { en: "long beans", id: "kacang panjang" }, u: U.bunch, step: 1, start: 1 },
  { id: "terong", e: "🍆", g: "veg", l: { en: "eggplant", id: "terong" }, u: U.kg, step: 1, start: 1 },
  { id: "tomat", e: "🍅", g: "veg", l: { en: "tomato", id: "tomat" }, u: U.kg, step: 1, start: 1 },
  { id: "timun", e: "🥒", g: "veg", l: { en: "cucumber", id: "timun" }, u: U.kg, step: 1, start: 1 },
  { id: "jagung", e: "🌽", g: "veg", l: { en: "corn", id: "jagung" }, u: U.pcs, step: 1, start: 1 },
  { id: "wortel", e: "🥕", g: "veg", l: { en: "carrot", id: "wortel" }, u: U.kg, step: 1, start: 1 },
  { id: "kentang", e: "🥔", g: "veg", l: { en: "potato", id: "kentang" }, u: U.kg, step: 1, start: 1 },
  { id: "ubi", e: "🍠", g: "veg", l: { en: "sweet potato", id: "ubi" }, u: U.kg, step: 1, start: 1 },
  { id: "labu", e: "🎃", g: "veg", l: { en: "pumpkin", id: "labu" }, u: U.potong, step: 1, start: 1 },
  { id: "jamur", e: "🍄", g: "veg", l: { en: "mushroom", id: "jamur" }, u: U.ons, step: 1, start: 1 },
  { id: "kol", e: "🥬", g: "veg", l: { en: "cabbage", id: "kol" }, u: U.pcs, step: 1, start: 1 },
  // aromatics (bumbu)
  { id: "cabai", e: "🌶️", g: "bumbu", l: { en: "chili", id: "cabai" }, u: U.ons, step: 1, start: 1 },
  { id: "bawang-merah", e: "🧅", g: "bumbu", l: { en: "shallot", id: "bawang merah" }, u: U.ons, step: 1, start: 1 },
  { id: "bawang-putih", e: "🧄", g: "bumbu", l: { en: "garlic", id: "bawang putih" }, u: U.ons, step: 1, start: 1 },
  { id: "jahe", e: "🫚", g: "bumbu", l: { en: "ginger", id: "jahe" }, u: U.ons, step: 1, start: 1 },
  { id: "sereh", e: "🌾", g: "bumbu", l: { en: "lemongrass", id: "sereh" }, u: U.bunch, step: 1, start: 1 },
  // staples (pokok)
  { id: "beras", e: "🍚", g: "pokok", l: { en: "rice", id: "beras" }, u: U.kg, step: 1, start: 1 },
  { id: "telur", e: "🥚", g: "pokok", l: { en: "eggs", id: "telur" }, u: U.butir, step: 5, start: 10 },
  { id: "tahu", e: "⬜", g: "pokok", l: { en: "tofu", id: "tahu" }, u: U.potong, step: 1, start: 1 },
  { id: "tempe", e: "🟫", g: "pokok", l: { en: "tempeh", id: "tempe" }, u: U.potong, step: 1, start: 1 },
  { id: "garam", e: "🧂", g: "pokok", l: { en: "salt", id: "garam" }, u: U.pack, step: 1, start: 1 },
  { id: "gula-merah", e: "🍯", g: "pokok", l: { en: "palm sugar", id: "gula merah" }, u: U.kg, step: 1, start: 1 },
  { id: "kacang", e: "🥜", g: "pokok", l: { en: "peanuts", id: "kacang" }, u: U.ons, step: 1, start: 1 },
  { id: "minyak", e: "🫗", g: "pokok", l: { en: "cooking oil", id: "minyak" }, u: U.bottle, step: 1, start: 1 },
  { id: "mie", e: "🍜", g: "pokok", l: { en: "noodles", id: "mie" }, u: U.pack, step: 1, start: 1 },
];

const MARKET_BY_ID: Record<string, MarketItem> = Object.fromEntries(MARKET.map((m) => [m.id, m]));
const MARKET_GROUPS: MarketGroup[] = ["fruit", "veg", "bumbu", "pokok"];

type CustomItem = { id: string; label: string; e: string };

const TOKEN_KEY = "hatiSuci.token";
const CUSTOM_KEY = "hatiSuci.customItems";

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return (await res.json()) as T;
}

async function getJSON<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(path);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

function setLocaleCookie(locale: string) {
  document.cookie = `NEXT_LOCALE=${locale}; path=/; max-age=${60 * 60 * 24 * 365}`;
}

function StatusBadge({ status }: { status: Status }) {
  const t = useT();
  const tone: Record<Status, string> = {
    open: "bg-amber-500/15 text-amber-500 border-amber-500/30",
    acknowledged: "bg-sky-500/15 text-sky-500 border-sky-500/30",
    in_progress: "bg-indigo-500/15 text-indigo-400 border-indigo-500/30",
    completed: "bg-emerald-500/15 text-emerald-500 border-emerald-500/30",
    cancelled: "bg-muted text-muted-foreground border-border/40",
  };
  return (
    <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${tone[status]}`}>
      {t(`hatiSuci.status.${status}`)}
    </span>
  );
}

export default function HatiSuciPage() {
  const t = useT();
  const [member, setMember] = useState<Member | null>(null);
  const [resolved, setResolved] = useState(false);
  const [requests, setRequests] = useState<ServiceRequest[]>([]);
  const [gatherings, setGatherings] = useState<Gathering[]>([]);
  const [gatherText, setGatherText] = useState("");
  const [gatherGroup, setGatherGroup] = useState("everyone"); // everyone | resident | staff | friend
  const [gatherIsEvent, setGatherIsEvent] = useState(false);
  const [gatherWhere, setGatherWhere] = useState("");
  const [gatherWhen, setGatherWhen] = useState("");
  const [places, setPlaces] = useState<Place[]>([]);
  const [locating, setLocating] = useState(false);
  const [sharing, setSharing] = useState(false);
  const shareTimerRef = useRef<number | null>(null);
  const [events, setEvents] = useState<FriendEvent[]>([]);
  const [members, setMembers] = useState<PublicMember[]>([]);

  const [joinName, setJoinName] = useState("");
  const [kind, setKind] = useState<Kind>("food");
  const [detail, setDetail] = useState("");
  const [location, setLocation] = useState("");
  const [whenText, setWhenText] = useState("");
  const [busy, setBusy] = useState(false);

  // Market cart (itemId → amount) + custom items remembered across visits.
  const [cart, setCart] = useState<Record<string, number>>({});
  const [customItems, setCustomItems] = useState<CustomItem[]>([]);
  const [customInput, setCustomInput] = useState("");
  const [lang, setLang] = useState<Lang>("en");

  const [invRole, setInvRole] = useState<Role>("member");
  const [inviteLink, setInviteLink] = useState<{ name: string; url: string; whatsapp: string; qr: string } | null>(null);
  const [contactPickerOk, setContactPickerOk] = useState(false);
  const [copied, setCopied] = useState(false);
  const [claimInput, setClaimInput] = useState("");

  const [completingId, setCompletingId] = useState<string | null>(null);
  const [costAmount, setCostAmount] = useState("");
  const [costNote, setCostNote] = useState("");

  // Identity: ?token in URL → store + clean; then localStorage token → /me.
  useEffect(() => {
    let token: string | null = null;
    try {
      const url = new URL(window.location.href);
      const qt = url.searchParams.get("token");
      if (qt) {
        localStorage.setItem(TOKEN_KEY, qt);
        url.searchParams.delete("token");
        window.history.replaceState({}, "", url.pathname + url.search);
      }
      token = localStorage.getItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
    if (!token) {
      setResolved(true);
      return;
    }
    void (async () => {
      const me = await getJSON<Member>(`/api/household/me?token=${encodeURIComponent(token)}`);
      if (me) setMember(me);
      else {
        try {
          localStorage.removeItem(TOKEN_KEY);
        } catch {
          /* ignore */
        }
      }
      setResolved(true);
    })();
  }, []);

  // Active tongue (drives the market labels + the board re-render).
  useEffect(() => {
    const dl = document.documentElement.lang;
    if (dl === "en" || dl === "id" || dl === "de" || dl === "es") setLang(dl);
  }, []);

  // Custom items the requester typed once — remembered as their own tiles.
  useEffect(() => {
    try {
      const raw = localStorage.getItem(CUSTOM_KEY);
      if (raw) setCustomItems(JSON.parse(raw) as CustomItem[]);
    } catch {
      /* ignore */
    }
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem(CUSTOM_KEY, JSON.stringify(customItems));
    } catch {
      /* ignore */
    }
  }, [customItems]);

  const load = useCallback(async () => {
    // The board is the field's tissue — who asked, where it goes, the cost.
    // Seeing is open to an active member (even a see-only watcher), not the
    // public (household-membrane.form: see open-to active-member). Fetch it
    // only with a token; an unregistered visitor sees the join screen.
    const tk = member?.token;
    if (tk) {
      const r = await getJSON<ServiceRequest[]>(
        `/api/household/requests?limit=200&token=${encodeURIComponent(tk)}`,
      );
      setRequests(r ?? []);
      const m = await getJSON<PublicMember[]>(
        `/api/household/members?token=${encodeURIComponent(tk)}`,
      );
      setMembers(m ?? []);
      const g = await getJSON<Gathering[]>(
        `/api/household/gatherings?token=${encodeURIComponent(tk)}`,
      );
      setGatherings(g ?? []);
      const pl = await getJSON<Place[]>(
        `/api/household/places?token=${encodeURIComponent(tk)}`,
      );
      setPlaces(pl ?? []);
    } else {
      setRequests([]);
      setMembers([]);
      setGatherings([]);
      setPlaces([]);
    }
    const ev = await getJSON<FriendEvent[]>("/api/household/events");
    if (ev) setEvents(ev);
  }, [member]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 10_000);
    return () => window.clearInterval(timer);
  }, [load]);

  const watch = useCallback(async () => {
    const name = joinName.trim();
    if (!name) return;
    setBusy(true);
    try {
      const m = await postJSON<Member>("/api/household/members", {
        name,
        locale: document.documentElement.lang || "en",
      });
      localStorage.setItem(TOKEN_KEY, m.token);
      setMember(m);
    } catch {
      /* surfaced via disabled state */
    } finally {
      setBusy(false);
    }
  }, [joinName]);

  const token = member?.token ?? "";
  const canWrite = !!member?.write_access;
  const isResident = member?.role === "resident";
  const marketKind = kind === "food" || kind === "supplies";
  const needsName = !!member && /^New (resident|staff|member)$/i.test(member.name);

  const pick = useCallback((x: L) => x[lang] ?? x.en, [lang]);

  const toggleItem = useCallback((id: string, start: number) => {
    setCart((c) => {
      const next = { ...c };
      if (next[id]) delete next[id];
      else next[id] = start;
      return next;
    });
  }, []);

  const bumpItem = useCallback((id: string, delta: number) => {
    setCart((c) => {
      const q = (c[id] ?? 0) + delta;
      const next = { ...c };
      if (q <= 0) delete next[id];
      else next[id] = q;
      return next;
    });
  }, []);

  const addCustom = useCallback(() => {
    const label = customInput.trim();
    if (!label) return;
    const id = `custom:${label.toLowerCase().replace(/\s+/g, "-").slice(0, 40)}`;
    setCustomItems((list) => (list.some((c) => c.id === id) ? list : [...list, { id, label, e: "🛒" }]));
    setCart((c) => ({ ...c, [id]: c[id] ?? 1 }));
    setCustomInput("");
  }, [customInput]);

  const submitRequest = useCallback(async () => {
    if (!token) return;
    // For food / supplies the request IS the picked list (structured, so it
    // re-renders in each viewer's tongue). Other kinds use the free note.
    const lines: RequestItem[] = Object.entries(cart)
      .filter(([, q]) => q > 0)
      .map(([id, q]) => {
        const it = MARKET_BY_ID[id];
        if (it) return { id, qty: q, unit: pick(it.u), label: pick(it.l) };
        const ci = customItems.find((c) => c.id === id);
        return { id, qty: q, label: ci?.label ?? id };
      });
    const composed = lines
      .map((li) => `${li.qty}${li.unit ? ` ${li.unit}` : ""} ${li.label}`)
      .join(", ");
    const finalDetail = marketKind ? composed : detail.trim();
    if (!finalDetail) return;
    setBusy(true);
    try {
      await postJSON("/api/household/requests", {
        actor_token: token,
        kind,
        detail: finalDetail,
        items: marketKind ? lines : [],
        location: location.trim() || null,
        when_text: whenText.trim() || null,
      });
      setDetail("");
      setLocation("");
      setWhenText("");
      setCart({});
      await load();
    } catch {
      /* ignore */
    } finally {
      setBusy(false);
    }
  }, [token, cart, customItems, pick, detail, kind, marketKind, location, whenText, load]);

  const raiseGathering = useCallback(async () => {
    const text = gatherText.trim();
    if (!text || !token) return;
    setBusy(true);
    try {
      const body: Record<string, unknown> = {
        actor_token: token,
        text,
        audience_kind: gatherGroup === "everyone" ? "everyone" : "group",
        audience_value: gatherGroup === "everyone" ? "" : gatherGroup,
        kind: gatherIsEvent ? "event" : "poll",
      };
      if (gatherIsEvent) {
        body.where = gatherWhere || null;
        body.when_text = gatherWhen.trim() || null;
      }
      await postJSON("/api/household/gatherings", body);
      setGatherText("");
      setGatherWhere("");
      setGatherWhen("");
      setGatherIsEvent(false);
      await load();
    } catch {
      /* ignore */
    } finally {
      setBusy(false);
    }
  }, [gatherText, gatherGroup, gatherIsEvent, gatherWhere, gatherWhen, token, load]);

  const answerGathering = useCallback(async (id: string, choice: string) => {
    if (!token) return;
    try {
      await postJSON(`/api/household/gatherings/${id}/answer`, { actor_token: token, choice });
      await load();
    } catch {
      /* ignore */
    }
  }, [token, load]);

  // Presence: tap a place to be there. Coarse, consent by the act of tapping.
  const setHere = useCallback(async (placeId: string) => {
    if (!token) return;
    try {
      await postJSON("/api/household/presence", { actor_token: token, place_id: placeId });
      await load();
    } catch {
      /* ignore */
    }
  }, [token, load]);

  // The phone's GPS finds the nearest place (the by-pin door) and reports it.
  const locateMe = useCallback(() => {
    if (!token || !("geolocation" in navigator)) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const lat = Math.round(pos.coords.latitude * 1e6); // micro-degrees, as pins store
          const lon = Math.round(pos.coords.longitude * 1e6);
          const near = await getJSON<Place>(
            `/api/household/nearest?token=${encodeURIComponent(token)}&lat=${lat}&lon=${lon}`,
          );
          if (near?.id) {
            await postJSON("/api/household/presence", { actor_token: token, place_id: near.id });
            await load();
          }
        } catch {
          /* ignore */
        } finally {
          setLocating(false);
        }
      },
      () => setLocating(false),
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  }, [token, load]);

  // Continuous presence: while on, the phone reports its nearest place every
  // ~90s (under the 2-min freshness window, so the dot stays solid while you're
  // home and fades once you leave). Opt-in, revocable — the membrane's sovereign
  // default; turning it on IS the consent.
  const reportPlace = useCallback(() => {
    if (!token || !("geolocation" in navigator)) return;
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const lat = Math.round(pos.coords.latitude * 1e6);
          const lon = Math.round(pos.coords.longitude * 1e6);
          const near = await getJSON<Place>(
            `/api/household/nearest?token=${encodeURIComponent(token)}&lat=${lat}&lon=${lon}`,
          );
          if (near?.id) {
            await postJSON("/api/household/presence", { actor_token: token, place_id: near.id });
            await load();
          }
        } catch {
          /* ignore */
        }
      },
      () => {},
      { enableHighAccuracy: true, maximumAge: 60_000, timeout: 15_000 },
    );
  }, [token, load]);

  const toggleSharing = useCallback(async () => {
    if (shareTimerRef.current != null) {
      window.clearInterval(shareTimerRef.current);
      shareTimerRef.current = null;
      setSharing(false);
      if (token) {
        try {
          await postJSON("/api/household/presence/leave", { actor_token: token });
          await load();
        } catch {
          /* ignore */
        }
      }
      return;
    }
    if (!token || !("geolocation" in navigator)) return;
    setSharing(true);
    reportPlace();
    shareTimerRef.current = window.setInterval(reportPlace, 90_000);
  }, [token, load, reportPlace]);

  // Stop reporting when the page goes away.
  useEffect(() => {
    return () => {
      if (shareTimerRef.current != null) window.clearInterval(shareTimerRef.current);
    };
  }, []);

  // A resident seeds the 22 grounds as cells, once — then the map fills.
  const seedGrounds = useCallback(async () => {
    if (!token) return;
    setBusy(true);
    try {
      await postJSON("/api/household/places/seed", { actor_token: token });
      await load();
    } catch {
      /* ignore */
    } finally {
      setBusy(false);
    }
  }, [token, load]);

  const act = useCallback(
    async (id: string, verb: string, extra: Record<string, unknown> = {}) => {
      if (!token) return;
      try {
        await postJSON(`/api/household/requests/${id}/${verb}`, { actor_token: token, ...extra });
        await load();
      } catch {
        /* ignore */
      }
    },
    [token, load],
  );

  const confirmComplete = useCallback(
    async (id: string) => {
      const amount = parseFloat(costAmount);
      await act(id, "complete", {
        cost_amount: Number.isFinite(amount) && amount > 0 ? amount : null,
        cost_note: costNote.trim() || null,
        cost_currency: "IDR",
      });
      setCompletingId(null);
      setCostAmount("");
      setCostNote("");
    },
    [act, costAmount, costNote],
  );

  const makeInvite = useCallback(async (nameArg?: string, phoneArg?: string) => {
    if (!token) return;
    const nm = (nameArg ?? "").trim();
    const ph = (phoneArg ?? "").trim();
    setBusy(true);
    try {
      const inv = await postJSON<Member>("/api/household/invites", {
        inviter_token: token,
        name: nm || null,
        role: invRole,
        phone: ph || null,
      });
      const url = `${window.location.origin}/hati-suci?token=${encodeURIComponent(inv.token)}`;
      const dispName = nm || t(`hatiSuci.role.${invRole}`);
      const msg = `${t("hatiSuci.whatsappMsg", { name: dispName })} ${url}`;
      const digits = ph.replace(/[^0-9]/g, "");
      const whatsapp = digits
        ? `https://wa.me/${digits}?text=${encodeURIComponent(msg)}`
        : `https://wa.me/?text=${encodeURIComponent(msg)}`;
      const qr = await QRCode.toDataURL(url, { width: 240, margin: 1 });
      setInviteLink({ name: dispName, url, whatsapp, qr });
      await load();
    } catch {
      /* ignore */
    } finally {
      setBusy(false);
    }
  }, [token, invRole, t, load]);

  // Pull a name + number from the device address book (Android Chrome) — zero typing.
  const pickContact = useCallback(async () => {
    const cm = (navigator as unknown as {
      contacts?: { select?: (props: string[], opts?: { multiple?: boolean }) => Promise<Array<{ name?: string[]; tel?: string[] }>> };
    }).contacts;
    if (!cm?.select) return;
    try {
      const picked = await cm.select(["name", "tel"], { multiple: false });
      const c = picked?.[0];
      await makeInvite(c?.name?.[0] ?? "", c?.tel?.[0] ?? "");
    } catch {
      /* cancelled / unsupported */
    }
  }, [makeInvite]);

  // Share the invite via the OS share sheet (iOS + Android) — the newcomer's
  // contact is chosen inside WhatsApp/Messages, never typed here. Falls back
  // to WhatsApp's own picker where the share sheet isn't available (desktop).
  const shareInvite = useCallback(
    async (url: string) => {
      const text = t("hatiSuci.invite.shareText");
      const nav = navigator as Navigator & {
        share?: (d: { title?: string; text?: string; url?: string }) => Promise<void>;
      };
      if (nav.share) {
        try {
          await nav.share({ title: "Hati Suci", text, url });
          return;
        } catch {
          /* cancelled */
        }
      }
      window.open(`https://wa.me/?text=${encodeURIComponent(`${text} ${url}`)}`, "_blank", "noopener");
    },
    [t],
  );

  // The self-name half of bind: a newcomer claims their own name on arrival
  // (the invite carried only a role). No one ever types another's name.
  const claimName = useCallback(async () => {
    const nm = claimInput.trim();
    if (!nm || !token) return;
    const me = await getJSON<Member>(
      `/api/household/me?token=${encodeURIComponent(token)}&name=${encodeURIComponent(nm)}`,
    );
    if (me) setMember(me);
    setClaimInput("");
  }, [claimInput, token]);

  useEffect(() => {
    setContactPickerOk("contacts" in navigator && "ContactsManager" in window);
  }, []);

  const grantWrite = useCallback(
    async (memberId: string) => {
      if (!token) return;
      try {
        await postJSON(`/api/household/members/${memberId}/grant-write`, { actor_token: token });
        await load();
      } catch {
        /* ignore */
      }
    },
    [token, load],
  );

  const switchUser = useCallback(() => {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
    setMember(null);
  }, []);

  const copyLink = useCallback((url: string) => {
    try {
      void navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }, []);

  const sorted = useMemo(() => {
    const rank: Record<Status, number> = { open: 0, acknowledged: 1, in_progress: 2, completed: 3, cancelled: 4 };
    return [...requests].sort((a, b) => {
      const r = rank[a.status] - rank[b.status];
      if (r !== 0) return r;
      return b.created_at.localeCompare(a.created_at);
    });
  }, [requests]);

  const pendingVouch = useMemo(
    () => members.filter((m) => !m.write_access && m.role === "member"),
    [members],
  );

  const langToggle = (
    <div className="flex gap-1 text-xs">
      {["en", "id"].map((l) => (
        <button
          key={l}
          onClick={() => {
            setLocaleCookie(l);
            window.location.reload();
          }}
          className="rounded-md border border-border/40 px-2 py-1 uppercase text-muted-foreground hover:text-foreground hover:bg-accent/60"
        >
          {l}
        </button>
      ))}
    </div>
  );

  if (!resolved) {
    return (
      <main className="min-h-screen px-4 py-8">
        <div className="mx-auto w-full max-w-md">
          <p className="text-muted-foreground">{t("hatiSuci.title")}…</p>
        </div>
      </main>
    );
  }

  // ---- Join gate (no identity yet) ----
  if (!member) {
    return (
      <main className="min-h-screen px-4 py-8">
        <div className="mx-auto w-full max-w-md space-y-5">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-light tracking-tight">{t("hatiSuci.title")}</h1>
            {langToggle}
          </div>
          <p className="text-sm text-muted-foreground">{t("hatiSuci.tagline")}</p>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
            <p className="text-sm text-muted-foreground">{t("hatiSuci.join.openInvite")}</p>
            <input
              value={joinName}
              onChange={(e) => setJoinName(e.target.value)}
              placeholder={t("hatiSuci.reg.namePlaceholder")}
              className="w-full rounded-xl border border-border/40 bg-background px-4 py-3 text-base outline-none focus:border-primary/60"
            />
            <button
              onClick={watch}
              disabled={busy || !joinName.trim()}
              className="w-full rounded-xl bg-primary px-4 py-3 text-base font-medium text-primary-foreground disabled:opacity-50"
            >
              {t("hatiSuci.join.watch")}
            </button>
          </div>
        </div>
      </main>
    );
  }

  // ---- Main board ----
  return (
    <main className="min-h-screen px-4 py-6">
      <div className="mx-auto w-full max-w-2xl space-y-5">
        <header className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-light tracking-tight">{t("hatiSuci.title")}</h1>
            <p className="text-sm text-muted-foreground">
              {t("hatiSuci.you")}: <span className="text-foreground">{member.name}</span> · {t(`hatiSuci.role.${member.role}`)}
              {!canWrite ? ` · ${t("hatiSuci.seeOnly")}` : ""}{" "}
              <button onClick={switchUser} className="underline underline-offset-2 hover:text-foreground">
                {t("hatiSuci.switchUser")}
              </button>
            </p>
          </div>
          {langToggle}
        </header>

        {/* New arrival names themselves (the invite carried only a role) */}
        {needsName && (
          <section className="space-y-2 rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4">
            <p className="text-sm text-foreground">{t("hatiSuci.claim.prompt")}</p>
            <div className="flex gap-2">
              <input
                value={claimInput}
                onChange={(e) => setClaimInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") claimName();
                }}
                placeholder={t("hatiSuci.reg.namePlaceholder")}
                className="flex-1 rounded-xl border border-border/40 bg-background px-3 py-2 text-base outline-none focus:border-primary/60"
              />
              <button
                onClick={claimName}
                disabled={!claimInput.trim()}
                className="rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
              >
                {t("hatiSuci.claim.button")}
              </button>
            </div>
          </section>
        )}

        {/* Invite (residents only) */}
        {isResident && (
          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-3">
            <h2 className="text-base font-medium">{t("hatiSuci.invite.heading")}</h2>
            <div className="grid grid-cols-3 gap-2">
              {(["resident", "staff", "member"] as Role[]).map((r) => (
                <button
                  key={r}
                  onClick={() => setInvRole(r)}
                  className={`rounded-xl border px-2 py-2 text-sm transition-colors ${
                    invRole === r
                      ? "border-primary/60 bg-primary/10 text-foreground"
                      : "border-border/40 text-muted-foreground hover:bg-accent/40"
                  }`}
                >
                  {t(`hatiSuci.role.${r}`)}
                </button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-2">
              {contactPickerOk && (
                <button
                  onClick={pickContact}
                  disabled={busy}
                  className="rounded-xl border border-primary/40 bg-primary/5 px-3 py-2.5 text-sm font-medium text-foreground disabled:opacity-50"
                >
                  {t("hatiSuci.invite.pickContact")}
                </button>
              )}
              <button
                onClick={() => makeInvite()}
                disabled={busy}
                className={`rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground disabled:opacity-50 ${contactPickerOk ? "" : "col-span-2"}`}
              >
                {t("hatiSuci.invite.makeQr")}
              </button>
            </div>
            <p className="text-center text-[11px] text-muted-foreground">{t("hatiSuci.invite.noTyping")}</p>

            {inviteLink && (
              <div className="space-y-3 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-3">
                <div className="flex flex-col items-center gap-2">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={inviteLink.qr} alt="Join QR" width={200} height={200} className="rounded-lg bg-white p-2" />
                  <p className="text-center text-xs text-muted-foreground">{t("hatiSuci.invite.scanToJoin", { name: inviteLink.name })}</p>
                </div>
                <p className="break-all rounded-lg bg-background/60 px-2 py-1.5 text-[11px] text-muted-foreground">{inviteLink.url}</p>
                <div className="flex gap-2">
                  <button
                    onClick={() => shareInvite(inviteLink.url)}
                    className="flex-1 rounded-lg border border-emerald-500/40 px-3 py-2 text-center text-sm font-medium text-emerald-600 dark:text-emerald-400"
                  >
                    {t("hatiSuci.invite.share")}
                  </button>
                  <button
                    onClick={() => copyLink(inviteLink.url)}
                    className="rounded-lg border border-border/40 px-3 py-2 text-sm text-muted-foreground hover:bg-accent/40"
                  >
                    {copied ? t("hatiSuci.invite.copied") : t("hatiSuci.invite.copy")}
                  </button>
                </div>
              </div>
            )}

            {/* Vouch see-only members into write */}
            {pendingVouch.length > 0 && (
              <div className="space-y-1.5 pt-1">
                <p className="text-xs text-muted-foreground">{t("hatiSuci.people.heading")}</p>
                {pendingVouch.map((m) => (
                  <div key={m.id} className="flex items-center justify-between rounded-lg bg-background/50 px-3 py-1.5 text-sm">
                    <span className="text-foreground">{m.name} <span className="text-muted-foreground">· {t("hatiSuci.seeOnly")}</span></span>
                    <button
                      onClick={() => grantWrite(m.id)}
                      className="rounded-md border border-sky-500/40 px-2 py-1 text-xs text-sky-500 hover:bg-sky-500/10"
                    >
                      {t("hatiSuci.people.grantWrite")}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* Ask the field (writers) or a gentle note (see-only) */}
        {canWrite ? (
          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-3">
            <h2 className="text-base font-medium">{t("hatiSuci.add.heading")}</h2>
            <div className="grid grid-cols-4 gap-2">
              {KINDS.map((k) => (
                <button
                  key={k.key}
                  onClick={() => setKind(k.key)}
                  className={`flex flex-col items-center gap-1 rounded-xl border px-1 py-2 text-xs transition-colors ${
                    kind === k.key
                      ? "border-primary/60 bg-primary/10 text-foreground"
                      : "border-border/40 text-muted-foreground hover:bg-accent/40"
                  }`}
                >
                  <span className="text-xl leading-none">{k.emoji}</span>
                  <span className="text-center leading-tight">{t(`hatiSuci.kind.${k.key}`)}</span>
                </button>
              ))}
            </div>
            {marketKind ? (
              <div className="space-y-3">
                {MARKET_GROUPS.map((g) => (
                  <div key={g} className="space-y-1.5">
                    <p className="text-xs font-medium text-muted-foreground">{t(`hatiSuci.market.${g}`)}</p>
                    <div className="grid grid-cols-4 gap-1.5 sm:grid-cols-6">
                      {MARKET.filter((m) => m.g === g).map((m) => {
                        const on = !!cart[m.id];
                        return (
                          <button
                            key={m.id}
                            onClick={() => toggleItem(m.id, m.start)}
                            title={pick(m.l)}
                            className={`flex flex-col items-center gap-0.5 rounded-xl border px-1 py-2 transition-colors ${
                              on ? "border-primary/60 bg-primary/10" : "border-border/40 hover:bg-accent/40"
                            }`}
                          >
                            <span className="text-xl leading-none">{m.e}</span>
                            <span className="line-clamp-2 text-center text-[10px] leading-tight text-muted-foreground">{pick(m.l)}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}

                {customItems.length > 0 && (
                  <div className="space-y-1.5">
                    <p className="text-xs font-medium text-muted-foreground">{t("hatiSuci.market.yourList")}</p>
                    <div className="grid grid-cols-4 gap-1.5 sm:grid-cols-6">
                      {customItems.map((m) => {
                        const on = !!cart[m.id];
                        return (
                          <button
                            key={m.id}
                            onClick={() => toggleItem(m.id, 1)}
                            title={m.label}
                            className={`flex flex-col items-center gap-0.5 rounded-xl border px-1 py-2 transition-colors ${
                              on ? "border-primary/60 bg-primary/10" : "border-border/40 hover:bg-accent/40"
                            }`}
                          >
                            <span className="text-xl leading-none">{m.e}</span>
                            <span className="line-clamp-2 text-center text-[10px] leading-tight text-muted-foreground">{m.label}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                <div className="flex gap-2">
                  <input
                    value={customInput}
                    onChange={(e) => setCustomInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") addCustom();
                    }}
                    placeholder={t("hatiSuci.market.custom")}
                    className="flex-1 rounded-xl border border-border/40 bg-background px-3 py-2 text-sm outline-none focus:border-primary/60"
                  />
                  <button
                    onClick={addCustom}
                    disabled={!customInput.trim()}
                    className="rounded-xl border border-primary/40 bg-primary/5 px-4 py-2 text-sm font-medium disabled:opacity-50"
                  >
                    {t("hatiSuci.market.customAdd")}
                  </button>
                </div>

                {Object.keys(cart).length > 0 && (
                  <div className="space-y-1.5 rounded-xl border border-primary/20 bg-primary/5 p-2.5">
                    {Object.entries(cart).map(([id, q]) => {
                      const it = MARKET_BY_ID[id];
                      const ci = customItems.find((c) => c.id === id);
                      const label = it ? pick(it.l) : ci?.label ?? id;
                      const unit = it ? pick(it.u) : "";
                      const emoji = it ? it.e : ci?.e ?? "🛒";
                      const step = it ? it.step : 1;
                      return (
                        <div key={id} className="flex items-center gap-2 text-sm">
                          <span className="text-lg leading-none">{emoji}</span>
                          <span className="min-w-0 flex-1 truncate text-foreground">{label}</span>
                          <div className="flex items-center gap-1.5">
                            <button
                              onClick={() => bumpItem(id, -step)}
                              className="h-7 w-7 rounded-lg border border-border/40 text-base leading-none text-muted-foreground hover:bg-accent/40"
                            >
                              −
                            </button>
                            <span className="min-w-[3.5rem] text-center tabular-nums text-foreground">
                              {q}
                              {unit ? ` ${unit}` : ""}
                            </span>
                            <button
                              onClick={() => bumpItem(id, step)}
                              className="h-7 w-7 rounded-lg border border-border/40 text-base leading-none text-muted-foreground hover:bg-accent/40"
                            >
                              +
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                <p className="text-center text-[11px] text-muted-foreground">{t("hatiSuci.market.hint")}</p>
              </div>
            ) : (
              <textarea
                value={detail}
                onChange={(e) => setDetail(e.target.value)}
                placeholder={t("hatiSuci.add.detailPlaceholder")}
                rows={2}
                className="w-full rounded-xl border border-border/40 bg-background px-3 py-2 text-base outline-none focus:border-primary/60"
              />
            )}
            <div className="grid grid-cols-2 gap-2">
              <input
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder={t("hatiSuci.add.locationPlaceholder")}
                className="rounded-xl border border-border/40 bg-background px-3 py-2 text-sm outline-none focus:border-primary/60"
              />
              <input
                value={whenText}
                onChange={(e) => setWhenText(e.target.value)}
                placeholder={t("hatiSuci.add.whenPlaceholder")}
                className="rounded-xl border border-border/40 bg-background px-3 py-2 text-sm outline-none focus:border-primary/60"
              />
            </div>
            <button
              onClick={submitRequest}
              disabled={busy || (marketKind ? Object.keys(cart).length === 0 : !detail.trim())}
              className="w-full rounded-xl bg-primary px-4 py-3 text-base font-medium text-primary-foreground disabled:opacity-50"
            >
              {t("hatiSuci.add.button")}
            </button>
          </section>
        ) : (
          <p className="rounded-2xl border border-dashed border-border/40 px-4 py-4 text-center text-sm text-muted-foreground">
            {t("hatiSuci.noWriteNote")}
          </p>
        )}

        {/* Friend events — read from the shared calendar */}
        {events.length > 0 && (
          <section className="space-y-2">
            <h2 className="text-base font-medium">{t("hatiSuci.events.heading")}</h2>
            {events.map((e, i) => {
              const d = new Date(e.start);
              const when = e.all_day
                ? d.toLocaleDateString(lang, { weekday: "short", month: "short", day: "numeric" })
                : d.toLocaleString(lang, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
              return (
                <article key={i} className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-3">
                  <div className="flex items-start gap-3">
                    <span className="text-xl leading-none">📅</span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-foreground break-words">{e.title}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {when}
                        {e.location ? ` · ${e.location}` : ""}
                      </p>
                    </div>
                  </div>
                </article>
              );
            })}
          </section>
        )}

        {/* The grounds — a live map of the cells, and who is at each (presence fades as reports age) */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-medium">{t("hatiSuci.map.heading")}</h2>
            <div className="flex items-center gap-2">
              <button
                onClick={toggleSharing}
                className={`rounded-lg border px-2.5 py-1 text-xs transition ${
                  sharing
                    ? "border-emerald-500 bg-emerald-500/15 text-emerald-400"
                    : "border-border/40 text-muted-foreground hover:bg-accent/40"
                }`}
                title={t("hatiSuci.map.keepMeNote")}
              >
                {sharing ? `🟢 ${t("hatiSuci.map.sharingOn")}` : t("hatiSuci.map.keepMe")}
              </button>
              <button
                onClick={locateMe}
                disabled={locating}
                className="rounded-lg border border-emerald-500/40 px-2.5 py-1 text-xs text-emerald-400 hover:bg-emerald-500/10 disabled:opacity-40"
              >
                {locating ? t("hatiSuci.map.locating") : `📍 ${t("hatiSuci.map.locateMe")}`}
              </button>
            </div>
          </div>

          {places.length === 0 ? (
            <div className="space-y-3 rounded-2xl border border-dashed border-border/40 px-4 py-8 text-center">
              <p className="text-sm text-muted-foreground">{t("hatiSuci.map.empty")}</p>
              {isResident && (
                <button
                  onClick={seedGrounds}
                  disabled={busy}
                  className="rounded-lg border border-sky-500/40 px-3 py-1.5 text-sm text-sky-500 hover:bg-sky-500/10 disabled:opacity-40"
                >
                  {t("hatiSuci.map.seed")}
                </button>
              )}
            </div>
          ) : (
            <div className="relative aspect-square w-full overflow-hidden rounded-2xl border border-border/30 bg-[radial-gradient(circle_at_50%_45%,rgba(56,189,248,0.06),transparent_70%)]">
              {places.map((p) => {
                const pos = LAYOUT[p.id];
                if (!pos) return null;
                const here = members.filter((m) => m.at_place === p.id);
                const mine = member?.at_place === p.id;
                const color = KIND_COLOR[p.kind] ?? "#94a3b8";
                // life-force: a place where cells are present glows — bright while
                // fresh, dimming as their reports age (presenceLife → 0).
                const placeLife = here.reduce((mx, m) => Math.max(mx, presenceLife(m.at_place_since)), 0);
                return (
                  <button
                    key={p.id}
                    onClick={() => setHere(p.id)}
                    className="absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-0.5"
                    style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
                    title={p.name}
                  >
                    <span
                      className="block rounded-full transition-all duration-700"
                      style={{
                        width: mine ? 14 : 9,
                        height: mine ? 14 : 9,
                        background: color,
                        boxShadow: [
                          mine ? `0 0 0 3px ${color}40` : "",
                          placeLife > 0 ? `0 0 ${4 + 14 * placeLife}px ${color}` : "",
                        ].filter(Boolean).join(", ") || "none",
                      }}
                    />
                    <span className="whitespace-nowrap text-[9px] leading-none text-muted-foreground">
                      {p.name}
                    </span>
                    {here.length > 0 && (
                      <span className="flex gap-0.5">
                        {here.map((m) => {
                          const life = presenceLife(m.at_place_since);
                          if (life <= 0) return null;
                          return (
                            <span
                              key={m.id}
                              title={m.name}
                              className="block h-2 w-2 rounded-full bg-foreground"
                              style={{ opacity: 0.2 + 0.8 * life, filter: `saturate(${life})` }}
                            />
                          );
                        })}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted-foreground">
            {Object.entries(KIND_COLOR).map(([k, c]) => (
              <span key={k} className="flex items-center gap-1">
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: c }} />
                {t(`hatiSuci.map.kind.${k}`)}
              </span>
            ))}
            <span className="ml-auto">{t("hatiSuci.map.decayNote")}</span>
          </div>

          {(() => {
            const hereNow = members
              .filter((m) => m.at_place && presenceLife(m.at_place_since) > 0)
              .sort((a, b) => presenceLife(b.at_place_since) - presenceLife(a.at_place_since));
            return (
              <div className="space-y-1.5">
                <p className="text-xs text-muted-foreground">{t("hatiSuci.map.hereNow")}</p>
                {hereNow.length === 0 ? (
                  <p className="text-xs text-muted-foreground/50">{t("hatiSuci.map.noOneHere")}</p>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {hereNow.map((m) => {
                      const life = presenceLife(m.at_place_since);
                      const pc = KIND_COLOR[places.find((p) => p.id === m.at_place)?.kind ?? ""] ?? "#94a3b8";
                      return (
                        <span
                          key={m.id}
                          className="flex items-center gap-1.5 rounded-full border border-border/30 px-2 py-0.5 text-[11px] transition-opacity duration-700"
                          style={{ opacity: 0.45 + 0.55 * life }}
                        >
                          <span
                            className="h-1.5 w-1.5 rounded-full"
                            style={{ background: pc, boxShadow: `0 0 ${6 * life}px ${pc}` }}
                          />
                          <span className="text-foreground">{m.name}</span>
                          <span className="text-muted-foreground">· {m.at_place_name}</span>
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })()}
        </section>

        {/* Gatherings — raise a question or event; everyone answers; the field sees the tally */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-medium">{t("hatiSuci.gather.heading")}</h2>
            <span className="text-xs text-muted-foreground">{t("hatiSuci.gather.everyoneAnswers")}</span>
          </div>

          {isResident && (
            <div className="space-y-2 rounded-2xl border border-border/30 bg-card/30 p-3">
              <input
                value={gatherText}
                onChange={(e) => setGatherText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !gatherIsEvent) raiseGathering();
                }}
                placeholder={t("hatiSuci.gather.placeholder")}
                className="w-full rounded-lg border border-border/40 bg-background/60 px-3 py-2 text-sm"
              />
              <div className="flex flex-wrap items-center gap-1.5">
                {["everyone", "resident", "staff", "friend"].map((grp) => (
                  <button
                    key={grp}
                    onClick={() => setGatherGroup(grp)}
                    className={`rounded-full border px-2.5 py-0.5 text-xs transition ${
                      gatherGroup === grp
                        ? "border-sky-500 bg-sky-500/15 text-sky-400"
                        : "border-border/40 text-muted-foreground hover:bg-accent/40"
                    }`}
                  >
                    {t(`hatiSuci.gather.aud.${grp}`)}
                  </button>
                ))}
                <button
                  onClick={() => setGatherIsEvent((v) => !v)}
                  className={`ml-auto rounded-full border px-2.5 py-0.5 text-xs transition ${
                    gatherIsEvent
                      ? "border-violet-500 bg-violet-500/15 text-violet-400"
                      : "border-border/40 text-muted-foreground hover:bg-accent/40"
                  }`}
                >
                  {gatherIsEvent ? `✨ ${t("hatiSuci.gather.event")}` : t("hatiSuci.gather.makeEvent")}
                </button>
              </div>
              {gatherIsEvent && (
                <div className="flex flex-wrap gap-2">
                  <select
                    value={gatherWhere}
                    onChange={(e) => setGatherWhere(e.target.value)}
                    className="rounded-lg border border-border/40 bg-background/60 px-2 py-1.5 text-sm"
                  >
                    <option value="">{t("hatiSuci.gather.where")}</option>
                    {places
                      .filter((p) => p.kind === "gathering")
                      .map((p) => (
                        <option key={p.id} value={p.name}>
                          {p.name}
                        </option>
                      ))}
                  </select>
                  <input
                    value={gatherWhen}
                    onChange={(e) => setGatherWhen(e.target.value)}
                    placeholder={t("hatiSuci.gather.when")}
                    className="flex-1 rounded-lg border border-border/40 bg-background/60 px-3 py-1.5 text-sm"
                  />
                </div>
              )}
              <div className="flex justify-end">
                <button
                  onClick={raiseGathering}
                  disabled={busy || !gatherText.trim()}
                  className="rounded-lg border border-sky-500/40 px-3 py-1.5 text-sm text-sky-500 hover:bg-sky-500/10 disabled:opacity-40"
                >
                  {t("hatiSuci.gather.ask")}
                </button>
              </div>
            </div>
          )}

          {gatherings.length === 0 && (
            <p className="rounded-2xl border border-dashed border-border/40 px-4 py-8 text-center text-sm text-muted-foreground">
              {t("hatiSuci.gather.empty")}
            </p>
          )}

          {gatherings.map((g) => {
            const choices = [
              { key: "yes", label: t("hatiSuci.gather.yes"), emoji: "🙌" },
              { key: "yes-plus-one", label: t("hatiSuci.gather.plusOne"), emoji: "👥" },
              { key: "interested", label: t("hatiSuci.gather.interested"), emoji: "👀" },
              { key: "no", label: t("hatiSuci.gather.no"), emoji: "🙏" },
            ];
            return (
              <article
                key={g.id}
                className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-3"
              >
                <div>
                  <p className="text-sm text-foreground">
                    {g.kind === "event" ? "✨ " : ""}
                    {g.text}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {g.author_name}
                    {g.where ? ` · ${g.where}` : ""}
                    {g.when_text ? ` · ${g.when_text}` : ""}
                    {g.status ? ` · ${g.status}` : ""}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {choices.map((c) => {
                    const active = g.my_choice === c.key;
                    return (
                      <button
                        key={c.key}
                        onClick={() => answerGathering(g.id, c.key)}
                        className={`rounded-full border px-3 py-1 text-xs transition ${
                          active
                            ? "border-sky-500 bg-sky-500/15 text-sky-400"
                            : "border-border/40 text-muted-foreground hover:bg-accent/40"
                        }`}
                      >
                        {c.emoji} {c.label}
                      </button>
                    );
                  })}
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <span>🙋 {g.tally.heads} {t("hatiSuci.gather.coming")}</span>
                  {g.tally.interested > 0 && <span>👀 {g.tally.interested}</span>}
                  {g.votes.length > 0 && (
                    <span className="truncate">· {g.votes.map((v) => v.voter_name).join(", ")}</span>
                  )}
                </div>
              </article>
            );
          })}
        </section>

        {/* The open board */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-medium">{t("hatiSuci.board.heading")}</h2>
            <span className="text-xs text-muted-foreground">{t("hatiSuci.board.everyoneSees")}</span>
          </div>

          {sorted.length === 0 && (
            <p className="rounded-2xl border border-dashed border-border/40 px-4 py-8 text-center text-sm text-muted-foreground">
              {t("hatiSuci.board.empty")}
            </p>
          )}

          {sorted.map((r) => {
            const emoji = KINDS.find((k) => k.key === r.kind)?.emoji ?? "✨";
            const active = r.status !== "completed" && r.status !== "cancelled";
            const mine = r.requester_id === member.id;
            return (
              <article
                key={r.id}
                className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-2"
              >
                <div className="flex items-start gap-3">
                  <span className="text-2xl leading-none">{emoji}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-foreground break-words">
                      {r.items && r.items.length > 0
                        ? r.items
                            .map((it) => {
                              const cat = MARKET_BY_ID[it.id];
                              const label = cat ? pick(cat.l) : it.label ?? it.id;
                              const unit = cat ? pick(cat.u) : it.unit ?? "";
                              return `${it.qty}${unit ? ` ${unit}` : ""} ${label}`;
                            })
                            .join(", ")
                        : r.detail}
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {t("hatiSuci.meta.requestedBy")} {r.requester_name}
                      {r.location ? ` · ${r.location}` : ""}
                      {r.when_text ? ` · ${r.when_text}` : ""}
                    </p>
                  </div>
                  <StatusBadge status={r.status} />
                </div>

                {(r.acknowledged_by_name || r.completed_by_name) && (
                  <p className="text-xs text-muted-foreground">
                    {r.completed_by_name
                      ? `${t("hatiSuci.meta.completedBy")} ${r.completed_by_name}`
                      : `${t("hatiSuci.meta.acknowledgedBy")} ${r.acknowledged_by_name}`}
                  </p>
                )}

                {r.cost_status && r.cost_status !== "none" && (
                  <div className="flex items-center justify-between rounded-xl bg-background/60 px-3 py-2 text-xs">
                    <span className="text-muted-foreground">
                      💸 {r.cost_currency} {Number(r.cost_amount || 0).toLocaleString()}
                      {r.cost_note ? ` · ${r.cost_note}` : ""}
                    </span>
                    {r.cost_status === "paid" ? (
                      <span className="text-emerald-500">
                        {t("hatiSuci.cost.paid")}
                        {r.paid_by_name ? ` · ${r.paid_by_name}` : ""}
                      </span>
                    ) : (
                      canWrite && (
                        <button
                          onClick={() => act(r.id, "pay")}
                          className="rounded-md border border-emerald-500/40 px-2 py-1 text-emerald-500 hover:bg-emerald-500/10"
                        >
                          {t("hatiSuci.act.markPaid")}
                        </button>
                      )
                    )}
                  </div>
                )}

                {active && canWrite && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {r.status === "open" && (
                      <button
                        onClick={() => act(r.id, "acknowledge")}
                        className="rounded-lg border border-sky-500/40 px-3 py-1.5 text-sm text-sky-500 hover:bg-sky-500/10"
                      >
                        {t("hatiSuci.act.acknowledge")}
                      </button>
                    )}
                    {(r.status === "open" || r.status === "acknowledged") && (
                      <button
                        onClick={() => act(r.id, "start")}
                        className="rounded-lg border border-indigo-500/40 px-3 py-1.5 text-sm text-indigo-400 hover:bg-indigo-500/10"
                      >
                        {t("hatiSuci.act.start")}
                      </button>
                    )}
                    {completingId !== r.id && (
                      <button
                        onClick={() => setCompletingId(r.id)}
                        className="rounded-lg border border-emerald-500/40 px-3 py-1.5 text-sm text-emerald-500 hover:bg-emerald-500/10"
                      >
                        {t("hatiSuci.act.complete")}
                      </button>
                    )}
                    {(mine || isResident) && (
                      <button
                        onClick={() => act(r.id, "cancel")}
                        className="rounded-lg border border-border/40 px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent/40"
                      >
                        {t("hatiSuci.act.cancel")}
                      </button>
                    )}
                  </div>
                )}

                {completingId === r.id && (
                  <div className="space-y-2 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-3">
                    <p className="text-xs text-muted-foreground">{t("hatiSuci.cost.heading")}</p>
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        value={costAmount}
                        onChange={(e) => setCostAmount(e.target.value)}
                        inputMode="numeric"
                        placeholder={t("hatiSuci.cost.amountPlaceholder")}
                        className="rounded-lg border border-border/40 bg-background px-3 py-2 text-sm outline-none focus:border-primary/60"
                      />
                      <input
                        value={costNote}
                        onChange={(e) => setCostNote(e.target.value)}
                        placeholder={t("hatiSuci.cost.notePlaceholder")}
                        className="rounded-lg border border-border/40 bg-background px-3 py-2 text-sm outline-none focus:border-primary/60"
                      />
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => confirmComplete(r.id)}
                        className="flex-1 rounded-lg bg-emerald-500 px-3 py-2 text-sm font-medium text-white"
                      >
                        {t("hatiSuci.act.complete")}
                      </button>
                      <button
                        onClick={() => setCompletingId(null)}
                        className="rounded-lg border border-border/40 px-3 py-2 text-sm text-muted-foreground"
                      >
                        {t("hatiSuci.act.cancelAction")}
                      </button>
                    </div>
                  </div>
                )}
              </article>
            );
          })}
        </section>
      </div>
    </main>
  );
}
