/**
 * Thumbnail image grid — used for spaces, practices, nature, network galleries.
 */
import Image from "next/image";
import Link from "next/link";

type GalleryItem = {
  imageSrc: string;
  label: string;
  href: string;
};

type GalleryGridProps = {
  items: GalleryItem[];
  columns?: 3 | 4;
  aspectRatio?: string;
};

export function GalleryGrid({ items, columns = 4, aspectRatio = "4/3" }: GalleryGridProps) {
  const gridCols = columns === 3 ? "md:grid-cols-3" : "md:grid-cols-4";
  return (
    <div className={`grid grid-cols-2 ${gridCols} gap-3`}>
      {items.map((item) => (
        <Link
          key={item.label}
          href={item.href}
          className="group relative overflow-hidden rounded-xl"
          style={{ aspectRatio }}
        >
          <Image
            src={item.imageSrc}
            alt={item.label}
            fill
            className="object-cover group-hover:scale-105 transition-transform duration-500"
            sizes={columns === 3 ? "33vw" : "25vw"}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-stone-950/80 via-transparent to-transparent" />
          <span className="absolute bottom-2 left-3 text-xs text-stone-200 font-medium">
            {item.label}
          </span>
        </Link>
      ))}
    </div>
  );
}
