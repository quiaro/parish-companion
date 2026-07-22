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
