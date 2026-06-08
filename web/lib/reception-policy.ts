// reception-policy.ts — the frozen (ice) projection of the body's
// reception-consent policy. The canonical, phase-mobile source is
// docs/coherence-substrate/reception-consent-policy.form — a Recipe that can
// rest at ice / water / gas per substrate-thermodynamics.form. This module is
// its ICE state: the stable default a carrier reads. To change it, MELT the
// Form policy (re-tune the rule), then re-FREEZE the new resting state here.
// Carriers (/begin and kin) READ this single source; they never bake their own
// copy — that is what kept the old hard-coded booleans forced into ice.
//
// Each consent rests at its sovereign default; the arriving cell sets the true
// value. Exposure-bearing consents (findable, email) rest closed — no silent
// exposure. Name-on-contributions rests open (weaving in is the chosen yes to
// be known), visible and revocable.

export interface ReceptionConsentDefaults {
  /** name shown on what you place here — rests open */
  shareName: boolean;
  /** discoverable by others in the directory — rests closed (opt-in) */
  findable: boolean;
  /** occasional updates by email — rests closed (opt-in) */
  emailUpdates: boolean;
}

export const RECEPTION_CONSENT_DEFAULTS: ReceptionConsentDefaults = {
  shareName: true,
  findable: false,
  emailUpdates: false,
};
