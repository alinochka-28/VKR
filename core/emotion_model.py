from enum import Enum


class BaseEmotion(str, Enum):
    JOY = "радость"
    SADNESS = "печаль"
    FEAR = "страх"
    ANGER = "гнев"
    TRUST = "доверие"
    DISGUST = "отвращение"
    ANTICIPATION = "ожидание"
    SURPRISE = "удивление"


class ECMESLevel(str, Enum):
    VERY_BAD = "very_bad"
    BAD = "bad"
    NEUTRAL = "neutral"
    GOOD = "good"
    VERY_GOOD = "very_good"


WILSON_GROUPS = {
    1: "goal_oriented", 3: "goal_oriented", 6: "goal_oriented", 7: "goal_oriented",
    2: "social", 11: "social", 12: "social", 18: "social", 19: "social",
    4: "avoidance",
    5: "fatigue",
    8: "introvert",
    9: "joyful",
    13: "anxiety", 21: "anxiety",
    10: "normal", 15: "normal",
    14: "crisis",
    20: "dominance",
    16: "support",
    17: "trust_overcome",
}


WILSON_BASE = {
    "goal_oriented": BaseEmotion.ANTICIPATION,
    "social": BaseEmotion.TRUST,
    "avoidance": BaseEmotion.DISGUST,
    "fatigue": BaseEmotion.SADNESS,
    "introvert": BaseEmotion.SADNESS,
    "joyful": BaseEmotion.JOY,
    "anxiety": BaseEmotion.FEAR,
    "normal": BaseEmotion.TRUST,
    "crisis": BaseEmotion.SADNESS,
    "dominance": BaseEmotion.ANGER,
    "support": BaseEmotion.SADNESS,
    "trust_overcome": BaseEmotion.TRUST,
}


GROUP_EMOTION_BY_ECMES = {
    ("goal_oriented", ECMESLevel.VERY_BAD): BaseEmotion.FEAR,
    ("goal_oriented", ECMESLevel.BAD):      BaseEmotion.SADNESS,
    ("goal_oriented", ECMESLevel.NEUTRAL):  BaseEmotion.ANTICIPATION,
    ("goal_oriented", ECMESLevel.GOOD):     BaseEmotion.SURPRISE,
    ("goal_oriented", ECMESLevel.VERY_GOOD): BaseEmotion.JOY,

    ("social", ECMESLevel.VERY_BAD): BaseEmotion.DISGUST,
    ("social", ECMESLevel.BAD):      BaseEmotion.SADNESS,
    ("social", ECMESLevel.NEUTRAL):  BaseEmotion.TRUST,
    ("social", ECMESLevel.GOOD):     BaseEmotion.ANTICIPATION,
    ("social", ECMESLevel.VERY_GOOD): BaseEmotion.JOY,

    ("avoidance", ECMESLevel.VERY_BAD): BaseEmotion.ANGER,
    ("avoidance", ECMESLevel.BAD):      BaseEmotion.DISGUST,
    ("avoidance", ECMESLevel.NEUTRAL):  BaseEmotion.DISGUST,
    ("avoidance", ECMESLevel.GOOD):     BaseEmotion.SADNESS,
    ("avoidance", ECMESLevel.VERY_GOOD): BaseEmotion.SURPRISE,

    ("fatigue", ECMESLevel.VERY_BAD): BaseEmotion.SADNESS,
    ("fatigue", ECMESLevel.BAD):      BaseEmotion.SADNESS,
    ("fatigue", ECMESLevel.NEUTRAL):  BaseEmotion.SADNESS,
    ("fatigue", ECMESLevel.GOOD):     BaseEmotion.TRUST,
    ("fatigue", ECMESLevel.VERY_GOOD): BaseEmotion.TRUST,

    ("introvert", ECMESLevel.VERY_BAD): BaseEmotion.SADNESS,
    ("introvert", ECMESLevel.BAD):      BaseEmotion.SADNESS,
    ("introvert", ECMESLevel.NEUTRAL):  BaseEmotion.SADNESS,
    ("introvert", ECMESLevel.GOOD):     BaseEmotion.TRUST,
    ("introvert", ECMESLevel.VERY_GOOD): BaseEmotion.TRUST,

    ("joyful", ECMESLevel.VERY_BAD): BaseEmotion.SADNESS,
    ("joyful", ECMESLevel.BAD):      BaseEmotion.SADNESS,
    ("joyful", ECMESLevel.NEUTRAL):  BaseEmotion.JOY,
    ("joyful", ECMESLevel.GOOD):     BaseEmotion.JOY,
    ("joyful", ECMESLevel.VERY_GOOD): BaseEmotion.JOY,

    ("anxiety", ECMESLevel.VERY_BAD): BaseEmotion.FEAR,
    ("anxiety", ECMESLevel.BAD):      BaseEmotion.ANTICIPATION,
    ("anxiety", ECMESLevel.NEUTRAL):  BaseEmotion.FEAR,
    ("anxiety", ECMESLevel.GOOD):     BaseEmotion.SADNESS,
    ("anxiety", ECMESLevel.VERY_GOOD): BaseEmotion.SURPRISE,

    ("normal", ECMESLevel.VERY_BAD): BaseEmotion.ANGER,
    ("normal", ECMESLevel.BAD):      BaseEmotion.SADNESS,
    ("normal", ECMESLevel.NEUTRAL):  BaseEmotion.TRUST,
    ("normal", ECMESLevel.GOOD):     BaseEmotion.ANTICIPATION,
    ("normal", ECMESLevel.VERY_GOOD): BaseEmotion.SURPRISE,

    ("crisis", ECMESLevel.VERY_BAD): BaseEmotion.ANGER,
    ("crisis", ECMESLevel.BAD):      BaseEmotion.ANGER,
    ("crisis", ECMESLevel.NEUTRAL):  BaseEmotion.SADNESS,
    ("crisis", ECMESLevel.GOOD):     BaseEmotion.SURPRISE,
    ("crisis", ECMESLevel.VERY_GOOD): BaseEmotion.TRUST,

    ("dominance", ECMESLevel.VERY_BAD): BaseEmotion.DISGUST,
    ("dominance", ECMESLevel.BAD):      BaseEmotion.ANGER,
    ("dominance", ECMESLevel.NEUTRAL):  BaseEmotion.ANGER,
    ("dominance", ECMESLevel.GOOD):     BaseEmotion.ANTICIPATION,
    ("dominance", ECMESLevel.VERY_GOOD): BaseEmotion.ANTICIPATION,

    ("trust_overcome", ECMESLevel.VERY_BAD): BaseEmotion.DISGUST,
    ("trust_overcome", ECMESLevel.BAD):      BaseEmotion.FEAR,
    ("trust_overcome", ECMESLevel.NEUTRAL):  BaseEmotion.TRUST,
    ("trust_overcome", ECMESLevel.GOOD):     BaseEmotion.TRUST,
    ("trust_overcome", ECMESLevel.VERY_GOOD): BaseEmotion.JOY,
}


SUPPORT_OVERLOAD_BY_ECMES = {
    ECMESLevel.VERY_BAD: BaseEmotion.ANGER,
    ECMESLevel.BAD:      BaseEmotion.SADNESS,
    ECMESLevel.NEUTRAL:  BaseEmotion.SADNESS,
    ECMESLevel.GOOD:     BaseEmotion.ANTICIPATION,
    ECMESLevel.VERY_GOOD: BaseEmotion.ANTICIPATION,
}

SUPPORT_HUG_BY_ECMES = {
    ECMESLevel.VERY_BAD: BaseEmotion.DISGUST,
    ECMESLevel.BAD:      BaseEmotion.FEAR,
    ECMESLevel.NEUTRAL:  BaseEmotion.TRUST,
    ECMESLevel.GOOD:     BaseEmotion.TRUST,
    ECMESLevel.VERY_GOOD: BaseEmotion.JOY,
}


class WilsonSupportType(str, Enum):
    OVERLOAD = "перегрузка"
    SUPPORT = "поддержка"


def _ensure_ecmes(value) -> ECMESLevel:
    if isinstance(value, ECMESLevel):
        return value
    return ECMESLevel(value)


def get_emotion(wilson_position: int, ecmes_level) -> BaseEmotion:
    ecmes = _ensure_ecmes(ecmes_level)
    group = WILSON_GROUPS.get(wilson_position)
    if not group:
        raise ValueError(f"Invalid Wilson position: {wilson_position}")

    if group == "support":
        return SUPPORT_OVERLOAD_BY_ECMES[ecmes]

    return GROUP_EMOTION_BY_ECMES[(group, ecmes)]


def get_emotion_with_support(
    wilson_position: int,
    ecmes_level,
    support_type: WilsonSupportType = None,
) -> BaseEmotion:
    ecmes = _ensure_ecmes(ecmes_level)

    if wilson_position == 16:
        if support_type == WilsonSupportType.OVERLOAD:
            return SUPPORT_OVERLOAD_BY_ECMES[ecmes]
        if support_type == WilsonSupportType.SUPPORT:
            return SUPPORT_HUG_BY_ECMES[ecmes]
        raise ValueError("Для позиции 16 нужно указать support_type")

    return get_emotion(wilson_position, ecmes)