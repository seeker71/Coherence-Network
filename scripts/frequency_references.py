"""Frequency reference corpus for the Living Collective scoring engine.

Two sets of reference sentences:
  LIVING_REFERENCES  — extracted from concept files' "The Feeling" sections
  INSTITUTIONAL_REFERENCES — representative institutional/corporate/medical tone

These are used as embedding anchors: text is scored by its cosine proximity
to the living centroid vs. the institutional centroid.

Update these lists as the KB evolves.
"""

# ---------------------------------------------------------------------------
# Living frequency — extracted verbatim from docs/vision-kb/concepts/ files
# Source files: lc-pulse, lc-space, lc-ceremony, lc-stillness, lc-beauty,
#   lc-play, lc-offering, lc-intimacy, lc-rest, lc-composting, lc-elders,
#   lc-resonating
# ---------------------------------------------------------------------------

LIVING_REFERENCES: list[str] = [
    # lc-pulse
    "There is a hum — not audible, but palpable.",
    "A warmth that isn't temperature.",
    "Your body relaxes in a way it doesn't relax alone.",
    "Something in your chest opens, like a fist you didn't know was clenched finally letting go.",
    "The pulse is what remains when you stop performing and start being.",
    "Children vibrate at it naturally.",
    # lc-space
    "The Hearth wraps you in warmth that isn't only thermal: it's the accumulated residue of ten thousand meals cooked here, the laughter soaked into the cob walls.",
    "You sit on the earthen bench and the silence is not empty.",
    "You don't use these spaces. You enter them and they change you.",
    "A conference room is a container — it holds whatever you put in it and gives nothing back.",
    # lc-ceremony
    "Someone has lit a fire. You did not plan to stop walking, but your feet bring you to the circle anyway.",
    "Something in your chest unclenches.",
    "The circle holds it the way a bowl holds water — simply, completely, by being the right shape.",
    # lc-stillness
    "You lie there and listen to the house breathe — the settling of wood, the tick of something cooling, the vast nothing that is not nothing at all.",
    "The silence between you thickens into something with weight, with warmth, with a kind of intelligence.",
    "This is not the absence of sound. This is the field's most powerful instrument, playing.",
    # lc-beauty
    "You pour tea. Steam curls. The bowl warms your palms and you understand, in a way that has nothing to do with thinking, that this object is beautiful because it is honest.",
    "Beauty here is not something added. It is what remains when carelessness is removed.",
    # lc-play
    "Something loosens in your chest. Your stride changes. You're walking faster without deciding to.",
    "Nobody asked them to. Nobody is watching with a clipboard.",
    "The part of you that has been sitting in meetings for twenty years stretches, yawns, and remembers it has a body.",
    # lc-offering
    "There is no gap between the woman and the work.",
    "None of these people are working. None of them are playing. They are doing the thing that flows from who they are, and the community is being nourished by the overflow.",
    "This is what offering feels like from the inside: not sacrifice, not duty, not even generosity. Just the heart beating because that is what a heart does.",
    # lc-intimacy
    "The relief of being witnessed without a single thing being asked of me.",
    "I realize I have spent decades learning how to hide, and that this person is not interested in any of my hiding.",
    "The safety is not in a contract or a rule. The safety is in the field itself — its warmth, its steadiness, its refusal to look away.",
    # lc-rest
    "This gap is not empty. It is held open on purpose, the way a musician holds a rest in the score.",
    "The rest generated what effort could not.",
    # lc-composting
    "You kneel at the edge of the compost pile on a cool morning and push your hands into the dark center.",
    "The pile does not rush. It does not grieve what it was. It just keeps turning, keeps feeding, keeps becoming.",
    # lc-elders
    "You realize you have been moving at a speed that makes the world blurry. Her pace is not slow. Your pace was too fast to see anything.",
    "It reminded everyone that this community has been through harder things and is still here.",
    # lc-resonating
    "A harmonic appears in the air between you that no single throat is producing.",
    "Each person sounding their own true note, and those distinct notes aligning into a chord richer than any single voice could produce.",
    "When resonance is real, you feel it in the bones before the mind names it.",
]


# ---------------------------------------------------------------------------
# Institutional frequency — representative corporate/medical/institutional tone
# ---------------------------------------------------------------------------

INSTITUTIONAL_REFERENCES: list[str] = [
    "The community management board shall approve all membership applications.",
    "Elder care services are provided through the health department program.",
    "Revenue targets for Q3 require stakeholder compliance with spending protocols.",
    "Mental health interventions will be administered according to treatment guidelines.",
    "Residents must submit maintenance requests through the approved ticketing system.",
    "The aging population requires enhanced care management and supervision programs.",
    "All community members are required to attend mandatory orientation sessions.",
    "Performance metrics will be evaluated on a quarterly basis by the oversight committee.",
    "Resource allocation decisions are subject to board review and approval processes.",
    "The wellness program coordinator will schedule assessments for all participants.",
    "Compliance with dietary guidelines is monitored by the nutrition services department.",
    "Facility maintenance schedules are posted on the administrative bulletin board.",
    "Grievance procedures must follow the established chain of command protocol.",
    "Participation in community activities is tracked through the attendance management system.",
    "The budget committee has approved a twelve percent reduction in recreational funding.",
    "Behavioral health screenings are required for all new resident intake procedures.",
    "Staff-to-resident ratios must meet the minimum standards set by regulatory agencies.",
    "The strategic planning committee will present the five-year development roadmap.",
    "All shared spaces are subject to the facility usage policy and booking requirements.",
    "Incident reports must be filed within twenty-four hours of any reportable event.",
    "The human resources department manages the volunteer coordination program.",
    "Annual inspections verify compliance with safety codes and operational standards.",
    "Membership dues are payable quarterly and subject to annual cost-of-living adjustments.",
    "The executive director reports to the board of trustees on financial performance.",
    "Clinical pathways define the standard of care for each patient population segment.",
    "Data-driven decision making ensures optimal resource utilization across departments.",
    "The governance framework establishes clear accountability and reporting structures.",
    "Risk management protocols require documentation of all adverse events and near-misses.",
    "Service delivery models are benchmarked against industry best practices and standards.",
    "The admissions committee evaluates applicants based on established eligibility criteria.",
]
