/** Shared types for Living Collective vision pages. */

export type Concept = {
  id: string;
  name: string;
  description: string;
  level?: number;
  story_content?: string;
  keywords?: string[];
  domains?: string[];
  details?: string;
  examples?: string[];
  aligned_places?: Array<{ name: string; location: string; note: string }>;
  aligned_communities?: Array<{ name: string; url: string; what: string }>;
  how_it_fits?: string;
  blueprint_notes?: string;
  visual_path?: string;
  sacred_frequency?: { hz: number; quality: string };
  resources?: Array<{ name: string; url: string; type: string; description: string }>;
  materials_and_methods?: Array<{ name: string; description: string }>;
  scale_notes?: { small?: string; medium?: string; large?: string };
  location_adaptations?: Array<{ climate: string; notes: string }>;
  visuals?: Array<{ prompt: string; caption: string }>;
  cost_notes?: string;
};

export type Edge = { id: string; from: string; to: string; type: string };

export type RelatedItems = {
  concept_id: string;
  ideas: string[];
  specs: string[];
  total: number;
};

export type LCConcept = {
  id: string;
  name: string;
  level?: number;
  sacred_frequency?: { hz: number; quality: string };
};
