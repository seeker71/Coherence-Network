/**
 * Story card — an immersive narrative of a specific person or moment.
 */
type StoryCardProps = {
  title: string;
  body: string;
  note?: string;
};

export function StoryCard({ title, body, note }: StoryCardProps) {
  return (
    <div className="p-8 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-4">
      <h3 className="text-xl font-light text-amber-300/80">{title}</h3>
      <p className="text-stone-300 leading-relaxed">{body}</p>
      {note && <p className="text-sm text-stone-500 italic">{note}</p>}
    </div>
  );
}
