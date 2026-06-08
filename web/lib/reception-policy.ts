// reception-policy.ts — the frozen (ice) projection of the body's
// first-encounter consent policy, WEB facets. The canonical, phase-mobile
// source is docs/coherence-substrate/reception-consent-policy.form — ONE policy
// over every channel, each channel's consents a FACET that can rest at
// ice / water / gas per substrate-thermodynamics.form. This module is the ICE
// state of the two web facets: the stable defaults the web carriers read. To
// change a facet, MELT the Form policy (re-tune), then re-FREEZE the new resting
// state here. Carriers READ this single source; they never bake their own copy.
//
// The RULE that decides these resting states is runnable, three-way-proven Form:
// form-stdlib/reception-consent.fk (proven by tests/reception-consent-band.fk). The
// logic lives in the body, not here — these values are its frozen output. Change the
// rule there first; this projection follows.
//
// Each consent rests at its sovereign default; the arriving cell sets the true
// value. Exposure-bearing consents rest closed — no silent exposure.

// web-begin facet — the /begin contributor door. Name-on-contributions rests
// open (weaving in is the chosen yes to be known); findable + email rest closed.
export interface BeginConsentDefaults {
  /** name shown on what you place here — rests open */
  shareName: boolean;
  /** discoverable by others in the directory — rests closed (opt-in) */
  findable: boolean;
  /** occasional updates by email — rests closed (opt-in) */
  emailUpdates: boolean;
}

export const RECEPTION_CONSENT_DEFAULTS: BeginConsentDefaults = {
  shareName: true,
  findable: false,
  emailUpdates: false,
};

// web-interest facet — the /vision/join interest form. Every consent rests
// closed: nothing is shared or subscribed unless the arriving cell opts in.
export interface InterestConsentDefaults {
  shareName: boolean;
  shareLocation: boolean;
  shareSkills: boolean;
  findable: boolean;
  emailUpdates: boolean;
}

export const INTEREST_CONSENT_DEFAULTS: InterestConsentDefaults = {
  shareName: false,
  shareLocation: false,
  shareSkills: false,
  findable: false,
  emailUpdates: false,
};
