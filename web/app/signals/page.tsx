import type { Metadata } from "next";

import { LivingSignalInstrument } from "@/components/living-signal/LivingSignalInstrument";

export const metadata: Metadata = {
  title: "Living Signal Layer",
  description: "A dynamic Coherence Network instrument for sensing form vitality and living pulse.",
};

export default function SignalsPage() {
  return <LivingSignalInstrument />;
}
