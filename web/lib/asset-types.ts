// Pure helpers for asset types — kept out of any component file so
// Fast Refresh in dev can see consistent React-only exports from
// `_components/AssetGlyph.tsx`.

export function assetTypeLabel(
  translate: (key: string) => string,
  type: string | undefined | null,
): string {
  if (!type) return translate("assets.type.UNKNOWN");
  const upper = type.toUpperCase();
  const key = `assets.type.${upper}`;
  const translated = translate(key);
  return translated === key ? type : translated;
}
