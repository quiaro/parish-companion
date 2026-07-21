from dataclasses import dataclass, field
from enum import Enum


class EmotionalTag(Enum):
    # Negative (soothed by Bible verse) — docs/emotional-tags-reference.md
    SADNESS = "sadness"
    GRIEF = "grief"
    NUMBNESS = "numbness"
    HEARTBREAK = "heartbreak"
    ANXIETY = "anxiety"
    FEAR = "fear"
    DREAD = "dread"
    DESPAIR = "despair"
    HOPELESSNESS = "hopelessness"
    LONELINESS = "loneliness"
    REJECTION = "rejection"
    GUILT = "guilt"
    SHAME = "shame"
    REGRET = "regret"
    ANGER = "anger"
    RAGE = "rage"
    BITTERNESS = "bitterness"
    ANGER_AT_GOD = "anger_at_god"
    DOUBT = "doubt"
    CONFUSION = "confusion"
    UNCERTAINTY = "uncertainty"
    EXHAUSTION = "exhaustion"
    OVERWHELM = "overwhelm"
    DISCOURAGEMENT = "discouragement"
    JEALOUSY = "jealousy"
    INSECURITY = "insecurity"
    HELPLESSNESS = "helplessness"
    WORRY_FOR_OTHERS = "worry_for_others"
    PRIDE = "pride"

    # Positive (amplified by Bible verse)
    JOY = "joy"
    DELIGHT = "delight"
    GRATITUDE = "gratitude"
    HOPE = "hope"
    PEACE = "peace"
    CONTENTMENT = "contentment"
    LOVE = "love"
    COURAGE = "courage"
    FAITH = "faith"
    WONDER = "wonder"
    RELIEF = "relief"
    PRIDE_AS_SATISFACTION = "pride_as_satisfaction"


class SituationalTag(Enum):
    # Loss & grief
    BEREAVEMENT = "bereavement"
    MISCARRIAGE_OR_INFERTILITY = "miscarriage_or_infertility"
    TERMINAL_ILLNESS = "terminal_illness"

    # Relationships & family
    MARITAL_CONFLICT = "marital_conflict"
    DIVORCE_OR_SEPARATION = "divorce_or_separation"
    PARENTING_STRUGGLES = "parenting_struggles"
    ESTRANGEMENT = "estrangement"
    CAREGIVING = "caregiving"
    NEW_PARENTHOOD = "new_parenthood"
    SINGLENESS = "singleness"
    ENGAGEMENT_OR_MARRIAGE = "engagement_or_marriage"

    # Work & finances
    JOB_LOSS = "job_loss"
    JOB_SEARCHING = "job_searching"
    NEW_JOB = "new_job"
    CAREER_UNCERTAINTY = "career_uncertainty"
    FINANCIAL_HARDSHIP = "financial_hardship"
    RETIREMENT = "retirement"

    # Health
    PERSONAL_ILLNESS = "personal_illness"
    MENTAL_HEALTH_STRUGGLE = "mental_health_struggle"
    ADDICTION_RECOVERY = "addiction_recovery"
    CHRONIC_PAIN_OR_ILLNESS = "chronic_pain_or_illness"

    # Faith & life direction
    SPIRITUAL_DRYNESS = "spiritual_dryness"
    DISCERNMENT = "discernment"
    NEW_TO_FAITH = "new_to_faith"
    RETURNING_TO_FAITH = "returning_to_faith"

    # Life transitions & milestones
    MOVING_OR_RELOCATION = "moving_or_relocation"
    GRADUATION = "graduation"
    AGING = "aging"
    EMPTY_NEST = "empty_nest"

    # Crisis & trauma
    NATURAL_DISASTER = "natural_disaster"
    ACCIDENT_OR_INJURY = "accident_or_injury"

    # Conflict & social
    PERSECUTION_OR_DISCRIMINATION = "persecution_or_discrimination"
    BETRAYAL = "betrayal"
    SOCIAL_ISOLATION = "social_isolation"
    BULLYING_OR_HARASSMENT = "bullying_or_harassment"
    INCARCERATION = "incarceration"
    IMMIGRATION_STATUS = "immigration_status"


@dataclass
class ClassificationResult:
    is_crisis: bool
    emotional_tags: list[EmotionalTag] = field(default_factory=list)
    situational_tags: list[SituationalTag] = field(default_factory=list)


@dataclass
class FlowReply:
    text: str
    buttons: list[tuple[str, str]] | None = None
