/**
 * Full-width image + text overlay — the pattern used for root concepts
 * on the vision hub and scenes on the lived page.
 */
import Image from "next/image";
import Link from "next/link";

type ConceptSectionCardProps = {
  title: string;
  body: string;
  note?: string;
  imageSrc: string;
  href?: string;
  priority?: boolean;
};

export function ConceptSectionCard({ title, body, note, imageSrc, href, priority }: ConceptSectionCardProps) {
  return (
    <section className="relative">
      <div className="relative w-full aspect-[16/7] md:aspect-[16/6] overflow-hidden">
        <Image src={imageSrc} alt={title} fill className="object-cover" sizes="100vw" priority={priority} />
        <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/30 to-transparent" />
        <div className="absolute inset-0 bg-gradient-to-b from-stone-950/50 via-transparent to-transparent" />
      </div>
      <div className="relative -mt-28 md:-mt-40 z-10 max-w-4xl mx-auto px-6 pb-16 md:pb-24">
        {href ? (
          <Link href={href} className="group">
            <h2 className="text-2xl md:text-4xl font-extralight tracking-tight text-white group-hover:text-amber-200/90 transition-colors">
              {title}
              <span className="ml-3 text-stone-600 group-hover:text-amber-400/50 text-xl transition-colors">→</span>
            </h2>
          </Link>
        ) : (
          <h2 className="text-2xl md:text-4xl font-extralight tracking-tight text-white">{title}</h2>
        )}
        <p className="text-lg text-stone-300 font-light leading-relaxed max-w-2xl mt-3">{body}</p>
        {note && <p className="text-sm text-stone-500 italic leading-relaxed max-w-xl mt-2">{note}</p>}
      </div>
    </section>
  );
}
