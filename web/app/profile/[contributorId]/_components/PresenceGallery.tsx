import Image from "next/image";

/**
 * Renders a presence's photo gallery from /people/{slug}/*.jpg
 * as a responsive grid. Click an image to open it full-size.
 *
 * The list of photos is probed at request time in page.tsx and
 * passed as srcs (absolute paths under /people/{slug}/).
 */
export function PresenceGallery({
  srcs,
  alt,
}: {
  srcs: string[];
  alt: string;
}) {
  if (!srcs.length) return null;

  return (
    <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 sm:p-8 space-y-5">
      <p className="text-xs uppercase tracking-widest text-muted-foreground">
        Photographs
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {srcs.map((src, i) => (
          <a
            key={src}
            href={src}
            target="_blank"
            rel="noopener noreferrer"
            className="relative aspect-[3/4] rounded-xl overflow-hidden bg-stone-800/50 group"
          >
            <Image
              src={src}
              alt={`${alt} — photograph ${i + 1}`}
              fill
              sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
              className="object-cover transition-transform duration-500 group-hover:scale-[1.02]"
              loading={i < 3 ? "eager" : "lazy"}
            />
          </a>
        ))}
      </div>
    </section>
  );
}
