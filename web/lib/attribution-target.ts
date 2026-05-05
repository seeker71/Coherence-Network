export type AttributionTarget = {
  entityType: string;
  entityId: string;
  assetId: string;
  conceptId?: string | null;
};

function pageIdFromPath(pathname: string): string {
  const trimmed = pathname.replace(/^\/+|\/+$/g, "");
  if (!trimmed) return "home";
  return trimmed
    .split("/")
    .map((part) => decodeURIComponent(part))
    .join("-")
    .replace(/[^a-zA-Z0-9_.:-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function attributionTargetFromHref(href: string): AttributionTarget | null {
  if (!href || href.startsWith("#")) return null;

  let pathname = href;
  try {
    pathname = new URL(href, "https://coherencycoin.com").pathname;
  } catch {
    pathname = href.split(/[?#]/, 1)[0] || href;
  }

  const parts = pathname.replace(/^\/+|\/+$/g, "").split("/").filter(Boolean);
  if (parts[0] === "meet" && parts[1] && parts[2]) {
    const entityId = decodeURIComponent(parts[2]);
    if (parts[1] === "concept") {
      return {
        entityType: "concept",
        entityId,
        assetId: entityId,
        conceptId: entityId,
      };
    }
    if (parts[1] === "idea") {
      return { entityType: "idea", entityId, assetId: entityId };
    }
    if (parts[1] === "asset") {
      return { entityType: "asset", entityId, assetId: entityId };
    }
    if (parts[1] === "spec") {
      return { entityType: "spec", entityId, assetId: entityId };
    }
  }
  if (parts[0] === "ideas" && parts[1]) {
    const entityId = decodeURIComponent(parts[1]);
    return { entityType: "idea", entityId, assetId: entityId };
  }
  if ((parts[0] === "vision" || parts[0] === "concepts") && parts[1]) {
    const entityId = decodeURIComponent(parts[1]);
    return {
      entityType: "concept",
      entityId,
      assetId: entityId,
      conceptId: entityId,
    };
  }
  if (parts[0] === "assets" && parts[1]) {
    const entityId = decodeURIComponent(parts[1]);
    return { entityType: "asset", entityId, assetId: entityId };
  }
  if (parts[0] === "specs" && parts[1]) {
    const entityId = decodeURIComponent(parts[1]);
    return { entityType: "spec", entityId, assetId: entityId };
  }

  const entityId = pageIdFromPath(pathname);
  return { entityType: "page", entityId, assetId: `page:${entityId}` };
}
