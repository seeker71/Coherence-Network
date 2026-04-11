/**
 * Shared idea types — mirror the Pydantic models exposed by the API.
 *
 * Fields that only some endpoints include are marked optional. Pages that
 * need a narrower view should declare their own Pick<> or alias instead of
 * redefining the type from scratch (that's what this module is cleaning up).
 *
 * Source of truth: api/app/models/idea.py (`Idea`, `IdeaWithScore`, `IdeaQuestion`).
 * If you add a field here, add it to the Pydantic model too, and vice versa.
 */

export type IdeaQuestion = {
  question: string;
  value_to_whole: number;
  estimated_cost: number;
  answer?: string | null;
  measured_delta?: number | null;
};

export type IdeaWithScore = {
  // Core identity
  id: string;
  name: string;
  description: string;

  // Economics — all always present on the API response.
  potential_value: number;
  actual_value: number;
  estimated_cost: number;
  actual_cost: number;
  confidence: number;
  free_energy_score: number;
  value_gap: number;

  // Lifecycle
  manifestation_status: string;

  // Surface — the API always returns these two as arrays (possibly empty).
  interfaces: string[];
  open_questions: IdeaQuestion[];

  // Optional fields: present only on richer views (detail page, listing page).
  // Narrowing by Pick<> is preferred over redeclaring the whole type.
  stage?: string;
  resistance_risk?: number;

  // Hierarchy (spec 117: fractal restructuring)
  idea_type?: string;
  parent_idea_id?: string | null;
  child_idea_ids?: string[];

  // Curation (super-ideas + pillar grouping)
  is_curated?: boolean;
  pillar?: string | null;
};
