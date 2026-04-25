/**
 * Geolocation commands: nearby, location
 *
 * coh nearby [--lat <lat>] [--lon <lon>] [--radius <km>]
 * coh location set <contributor-id> <city> <country> <lat> <lon>
 * coh location get <contributor-id>
 * coh location clear <contributor-id>
 */

import { get, patch, del } from "../api.mjs";

function parseFlag(args, flag) {
  const idx = args.indexOf(flag);
  if (idx !== -1 && args[idx + 1]) return args[idx + 1];
  return null;
}

function km(v) {
  return v != null ? `${Number(v).toFixed(1)} km` : "?";
}

export async function showNearby(args) {
  const lat = parseFloat(parseFlag(args, "--lat") ?? "");
  const lon = parseFloat(parseFlag(args, "--lon") ?? "");
  const radius = parseFloat(parseFlag(args, "--radius") ?? "100");

  if (isNaN(lat) || isNaN(lon)) {
    console.error("Usage: coh nearby --lat <lat> --lon <lon> [--radius <km>]");
    process.exit(1);
  }

  const params = new URLSearchParams({
    lat: lat.toString(),
    lon: lon.toString(),
    radius_km: radius.toString(),
  });

  const data = await get(`/api/nearby?${params}`);

  console.log();
  console.log(`\x1b[1m  NEARBY  \x1b[0m(lat=${lat}, lon=${lon}, radius=${radius} km)`);
  console.log(`  ${"─".repeat(70)}`);

  const contributors = data?.contributors ?? [];
  if (contributors.length === 0) {
    console.log("  No contributors nearby with public location.");
  } else {
    console.log(`\n  \x1b[1mContributors\x1b[0m (${contributors.length})\n`);
    for (const c of contributors) {
      const name = (c.name || c.contributor_id).padEnd(24);
      const location = `${c.city}, ${c.country}`.padEnd(26);
      const dist = km(c.distance_km).padStart(10);
      const score =
        c.coherence_score != null
          ? ` score=${Number(c.coherence_score).toFixed(2)}`
          : "";
      console.log(`  ${name}  ${location}  ${dist}${score}`);
    }
  }

  const ideas = data?.ideas ?? [];
  if (ideas.length > 0) {
    console.log(`\n  \x1b[1mIdeas from this area\x1b[0m (${ideas.length})\n`);
    for (const idea of ideas) {
      const title = (idea.title || idea.idea_id).slice(0, 40).padEnd(42);
      const by = `by ${(idea.contributor_name || idea.contributor_id).slice(0, 16)}`.padEnd(22);
      const dist = km(idea.distance_km).padStart(10);
      console.log(`  ${title}  ${by}  ${dist}`);
    }
  }

  console.log();
}

export async function handleLocation(args) {
  const [subCmd, ...rest] = args;

  switch (subCmd) {
    case "set":
      return setLocation(rest);
    case "get":
      return getLocation(rest);
    case "clear":
    case "remove":
    case "delete":
      return clearLocation(rest);
    default:
      console.error(
        "Usage:\n" +
          "  coh location set <contributor-id> <city> <country> <lat> <lon> [public|contributors_only|private]\n" +
          "  coh location get <contributor-id>\n" +
          "  coh location clear <contributor-id>",
      );
      process.exit(1);
  }
}

async function setLocation(args) {
  const [contributorId, city, country, latStr, lonStr, visibility = "contributors_only"] = args;
  if (!contributorId || !city || !country || !latStr || !lonStr) {
    console.error(
      "Usage: coh location set <contributor-id> <city> <country> <lat> <lon> [public|contributors_only|private]",
    );
    process.exit(1);
  }

  const lat = parseFloat(latStr);
  const lon = parseFloat(lonStr);
  if (isNaN(lat) || isNaN(lon)) {
    console.error("lat and lon must be numeric values.");
    process.exit(1);
  }

  const payload = {
    city,
    country,
    latitude: lat,
    longitude: lon,
    visibility,
  };

  const data = await patch(`/api/contributors/${encodeURIComponent(contributorId)}/location`, payload);
  console.log();
  console.log(
    `  \x1b[32m✓\x1b[0m Location set for ${contributorId}: ${data.city}, ${data.country} (${data.visibility})`,
  );
  console.log();
}

async function getLocation(args) {
  const [contributorId] = args;
  if (!contributorId) {
    console.error("Usage: coh location get <contributor-id>");
    process.exit(1);
  }

  const data = await get(`/api/contributors/${encodeURIComponent(contributorId)}/location`);
  console.log();
  console.log(`  \x1b[1mLocation for ${contributorId}\x1b[0m`);
  console.log(`  City      : ${data.city}${data.region ? `, ${data.region}` : ""}`);
  console.log(`  Country   : ${data.country}`);
  console.log(`  Lat/Lon   : ${data.latitude}, ${data.longitude}`);
  console.log(`  Visibility: ${data.visibility}`);
  console.log(`  Updated   : ${data.updated_at}`);
  console.log();
}

async function clearLocation(args) {
  const [contributorId] = args;
  if (!contributorId) {
    console.error("Usage: coh location clear <contributor-id>");
    process.exit(1);
  }

  await del(`/api/contributors/${encodeURIComponent(contributorId)}/location`);
  console.log();
  console.log(`  \x1b[32m✓\x1b[0m Location cleared for ${contributorId}.`);
  console.log();
}
