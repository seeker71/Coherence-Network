(async () => {
  const cutoff = new Date("2024-05-07T00:00:00");
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();

  function parseHeading(label) {
    const now = new Date();
    if (!label) return null;
    if (label === "Today") return new Date(now.getFullYear(), now.getMonth(), now.getDate());
    if (label === "Yesterday") return new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
    let parsed = new Date(`${label}, ${now.getFullYear()}`);
    if (!Number.isNaN(parsed.getTime()) && parsed > now) {
      parsed = new Date(`${label}, ${now.getFullYear() - 1}`);
    }
    if (!Number.isNaN(parsed.getTime())) return parsed;
    parsed = new Date(label);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function currentItems() {
    const nodes = [
      ...document.querySelectorAll("h2"),
      ...document.querySelectorAll('[role="listitem"][aria-label*="Card showing"]'),
    ].sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
    const out = [];
    let heading = "";
    let headingDate = null;
    for (const node of nodes) {
      if (node.tagName === "H2") {
        heading = clean(node.innerText);
        headingDate = parseHeading(heading);
        continue;
      }
      const links = [...node.querySelectorAll("a")].map((a) => ({
        text: clean(a.innerText),
        href: a.href || "",
      }));
      const rawLines = clean(node.innerText).split(" ").length ? node.innerText.split(/\n+/).map(clean).filter(Boolean) : [];
      const platform = rawLines[0] || clean(node.getAttribute("aria-label")).replace("Card showing an activity from ", "");
      const titleLink = links.find((link) => link.href.includes("youtube.com/watch") || link.href.includes("music.youtube.com/watch") || link.href.includes("youtube.com/results") || link.href.includes("youtube.com/post"));
      const creatorLink = links.find((link) => link.href.includes("/channel/"));
      const durationLink = links.find((link) => /^\d{1,2}:\d{2}(?::\d{2})?$/.test(link.text));
      const timeLine = rawLines.find((line) => line.includes("Details")) || "";
      const actionLine = rawLines.find((line) => /^(Watched|Searched for|Viewed)\b/.test(line)) || "";
      out.push({
        source: platform.toLowerCase().includes("music") ? "youtube-music-myactivity-2y" : "youtube-myactivity-2y",
        platform,
        dateHeading: heading,
        absoluteDate: headingDate ? headingDate.toISOString().slice(0, 10) : null,
        title: titleLink ? titleLink.text : actionLine.replace(/^(Watched|Searched for|Viewed)\s+/, ""),
        action: (actionLine.match(/^(Watched|Searched for|Viewed)\b/) || [""])[0],
        creator: creatorLink ? creatorLink.text : "",
        timeLine,
        duration: durationLink ? durationLink.text : "",
        url: titleLink ? titleLink.href : "",
        rawLines,
      });
    }
    return out;
  }

  const seen = new Map();
  const stats = { clicks: 0, stagnant: 0, oldestDate: null, stoppedBecause: "" };
  for (let i = 0; i < 500; i += 1) {
    for (const item of currentItems()) {
      const key = [item.absoluteDate, item.timeLine, item.platform, item.title, item.creator, item.url].join("|");
      if (!seen.has(key)) seen.set(key, item);
    }
    const dates = [...seen.values()].map((item) => item.absoluteDate).filter(Boolean).sort();
    stats.oldestDate = dates[0] || null;
    if (stats.oldestDate && new Date(`${stats.oldestDate}T00:00:00`) < cutoff) {
      stats.stoppedBecause = "older-than-cutoff";
      break;
    }
    const before = seen.size;
    const loadMore = [...document.querySelectorAll("button")].find((button) => clean(button.innerText) === "Load more");
    if (!loadMore) {
      stats.stoppedBecause = "no-load-more";
      break;
    }
    loadMore.click();
    stats.clicks += 1;
    await sleep(1800);
    window.scrollTo(0, document.body.scrollHeight);
    await sleep(600);
    if (seen.size === before) stats.stagnant += 1;
    else stats.stagnant = 0;
    if (stats.stagnant >= 8) {
      stats.stoppedBecause = "stagnant";
      break;
    }
  }

  const events = [...seen.values()].filter((item) => {
    if (!item.absoluteDate) return true;
    return new Date(`${item.absoluteDate}T00:00:00`) >= cutoff;
  });
  const payload = {
    generatedAt: new Date().toISOString(),
    requestedRange: { from: "2024-05-07", to: "2026-05-07" },
    stats,
    events,
  };
  return fetch("http://127.0.0.1:8766/", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  }).then((response) => response.json());
})()
