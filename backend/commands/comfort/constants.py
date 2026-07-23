from commands.comfort.models import EmotionalTag

# K-06: a single one of these tags in a classification result, combined with a high
# passage-request frequency, is enough to trigger the pastoral-outreach escalation offer.
# See docs/high-risk-emotional-tags.md for the reasoning behind this specific subset —
# any change to it should be a deliberate decision documented there, not an ad hoc edit.
HIGH_RISK_EMOTIONAL_TAGS = frozenset(
    {
        EmotionalTag.DESPAIR,
        EmotionalTag.HOPELESSNESS,
        EmotionalTag.LONELINESS,
        EmotionalTag.HELPLESSNESS,
        EmotionalTag.RAGE,
    }
)

# K-07 Step G: when retrieval finds no relevant match, a random verse tagged with one of
# these is presented instead of forcing a bad match. 
# See docs/comfort-technical-summary.md's Step G for the reasoning.
FALLBACK_EMOTIONAL_TAGS = frozenset({EmotionalTag.FAITH, EmotionalTag.HOPE, EmotionalTag.LOVE})
