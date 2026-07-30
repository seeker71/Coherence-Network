// Contained surfaces — routes that render as their own self-contained app,
// without the marketing site's header, bottom nav, or badge. A member on a
// contained surface can't accidentally wander out into the rest of the site
// with no way back.
//
// A surface is contained by its path (/grocery) or by its host
// (app.hati.earth, whose root the middleware rewrites). Because a rewrite is
// invisible to the browser, the host case is only knowable server-side, so the
// middleware states it in a request header that the layout reads. Both routes
// to the same knowing live here, so middleware, layout, and ChromeGate agree.

/** Request header the middleware sets when the host names a contained app. */
export const CONTAINED_SURFACE_HEADER = "x-contained-surface";

/** Route prefixes that render as their own contained app. */
export const CONTAINED_PREFIXES = ["/hati-suci", "/grocery"];

/** True when a pathname sits on a contained surface. */
export function isContainedPath(pathname: string): boolean {
  return CONTAINED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(prefix + "/"),
  );
}
