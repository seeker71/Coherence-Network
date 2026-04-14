"use client";

import { useState, useCallback } from "react";

/**
 * Image component that handles Pollinations AI image generation.
 * Pollinations generates images on-the-fly and may return 503 when busy.
 * This component retries up to 3 times with exponential backoff,
 * shows a spinner while loading, and fades in when ready.
 */
export default function PollinationsImage({
  src,
  alt,
  className = "",
}: {
  src: string;
  alt: string;
  className?: string;
}) {
  const [attempt, setAttempt] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);

  const handleError = useCallback(() => {
    if (attempt < 3) {
      const delay = 3000 * (attempt + 1); // 3s, 6s, 9s
      setTimeout(() => setAttempt((a) => a + 1), delay);
    } else {
      setFailed(true);
    }
  }, [attempt]);

  // Append retry param to bust cache on retry
  const imgSrc = attempt > 0 ? `${src}&_r=${attempt}` : src;

  return (
    <div className={`relative ${className}`}>
      {/* Spinner — visible while loading or retrying */}
      {!loaded && !failed && (
        <div className="absolute inset-0 flex items-center justify-center bg-stone-800/50 rounded-xl">
          <div className="text-center space-y-2 px-4">
            <div className="w-8 h-8 mx-auto rounded-full border-2 border-stone-600 border-t-amber-400/60 animate-spin" />
            <p className="text-xs text-stone-500">{alt}</p>
            {attempt > 0 && (
              <p className="text-[10px] text-stone-600">Retry {attempt}/3...</p>
            )}
          </div>
        </div>
      )}

      {/* Failed state */}
      {failed && (
        <div className="absolute inset-0 flex items-center justify-center bg-stone-800/30 rounded-xl">
          <div className="text-center space-y-1 px-4">
            <p className="text-xs text-stone-500">{alt}</p>
            <p className="text-[10px] text-stone-600">Image unavailable</p>
          </div>
        </div>
      )}

      {/* Actual image — hidden until loaded */}
      {!failed && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          key={attempt}
          src={imgSrc}
          alt={alt}
          className="absolute inset-0 w-full h-full object-cover rounded-xl transition-opacity duration-500"
          style={{ opacity: loaded ? 1 : 0, color: "transparent", fontSize: 0 }}
          loading="eager"
          onLoad={() => setLoaded(true)}
          onError={handleError}
        />
      )}
    </div>
  );
}
