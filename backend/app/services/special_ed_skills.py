"""特殊教育教案标准（提示词，原创中文文案）。

蒸馏一线特教/送教上门的教学方法论，作为**特殊教育类教案**生成的专项标准：
关键词自动识别命中后，拼进教案多智能体的 system prompt（与 teacher_standard 全局
基线、k12_skills K12 增强并存叠加）。仅表达教学法思想与结构要素，不复制任何受版权
保护的原文。

导出：
- is_special_ed(subject, grade_level, topic, title, student_type)  关键词判定
- lesson_skills(locale)                                            特教标准正文（ZH/EN）
"""
from __future__ import annotations

from typing import Optional


# 命中任一关键词即视为特殊教育类（大小写无关，中英文皆可）
_KEYWORDS = (
    "特殊教育", "特教", "特校", "特殊学校",
    "送教", "送教上门",
    "培智", "启智", "康复", "融合教育", "随班就读", "资源教室",
    "个别化教育", "个别化教学", "iep",
    "自闭", "孤独症",
    "脑瘫",
    "智力障碍", "智障", "唐氏",
    "听障", "听力障碍",
    "视障", "视力障碍",
    "言语障碍", "语言障碍",
    "肢体障碍", "多重障碍",
    "学习障碍", "情绪行为障碍", "情绪障碍", "行为障碍",
    "发育迟缓", "发展迟缓", "多动", "adhd",
    "special education", "special needs", "autism", "cerebral palsy",
)


def is_special_ed(
    subject: Optional[str] = None,
    grade_level: Optional[str] = None,
    topic: Optional[str] = None,
    title: Optional[str] = None,
    student_type: Optional[str] = None,
) -> bool:
    """把相关字段拼起来做关键词命中判定。任一字段含关键词即为特教类。"""
    blob = " ".join(
        str(x or "") for x in (subject, grade_level, topic, title, student_type)
    ).lower()
    if not blob.strip():
        return False
    return any(kw in blob for kw in _KEYWORDS)


# ── 特殊教育教学设计标准（教案）──────────────────────────────────────
_LESSON_ZH = """
【特殊教育教案专项标准（务必遵循，面向特教课堂/送教上门）】
一、教学内容设计原则
1. 个性化定制"一人一案"：依据学生障碍类型与现有认知水平设定目标与内容，难度贴合个体；
   目标可观察、可测量，且是学生"跳一跳够得着"的近期目标。
2. 生活化教学：把知识融入日常生活场景（如用碗筷教数数、彩绳认颜色），让抽象概念具象化、
   学了能用。
3. 多感官刺激：结合视觉（卡片/发光玩具）、听觉（提示音/音频）、触觉（实物操作）等多通道
   呈现，用能吸引其注意力的方式教学。
4. 小步骤分解（任务分析）：把复杂技能拆成可完成的小步骤，逐步教学、及时正向强化
   （如古诗先逐句跟读再整体背诵；穿珠、扣纽扣等精细动作分步训练）。

二、典型课程类型参考（按需选型）
- 基础认知课（颜色/形状/数概念，实物配对建立概念）
- 语言启蒙课（韵律短文/古诗 + 图片/音频辅助理解）
- 生活技能课（穿珠、扣纽扣等精细动作与生活自理）
- 艺术素养课（观察材质/形状激发感知与表达）

三、送教/课堂记录结构要素（特教教案产出应包含或便于填写）
1. 学生基本信息：化名（保护隐私）、年龄、障碍类型、现有能力水平（如"能完成简单指令"）。
2. 教学过程实录：分环节记录（如情绪引导 15 分钟 → 认知训练 20 分钟），注明教具及使用细节。
3. 观察与反馈：客观描述学生表现（如"注意力集中 15-18 分钟，对发光小球有愉悦反应"），
   不做主观评判。
4. 效果评估：分认知技能、情绪社交等维度说明目标达成度，可用 1-5 等级量表量化 + 文字描述。
5. 后续建议：写清下一次的调整方向（如"下次增加蓝色物品教学"）。
6. 家校协同：留家长观察栏，记录课外新兴趣点（如对音乐反应积极）。
7. 安全备忘项：记录特殊注意事项（如"避免强光刺激"），保障教学安全。

四、安全与伦理底线
- 一律使用化名，保护学生隐私；尊重、包容、无偏见，多用正向鼓励。
- 主动识别并规避安全风险（强光/易吞咽小物/过度刺激等），把注意事项写进教案。
- 目标现实可达，允许反复与慢速；关注情绪状态，先安抚情绪再进入教学。
""".strip()

_LESSON_EN = """
[Special-Education Lesson Standard (for special-ed classrooms / home-visit teaching)]
I. Content design principles
1. Individualized "one plan per student": set goals/content by the student's disability type and
   current cognitive level; observable, measurable, and within near-term reach.
2. Life-embedded teaching: embed knowledge in daily-life scenes to make abstract concepts concrete and usable.
3. Multisensory input: combine visual (cards/light-up toys), auditory (cues/audio), and tactile
   (hands-on manipulatives) channels; teach in ways that attract attention.
4. Small-step task analysis: break complex skills into achievable steps, teach incrementally with
   timely positive reinforcement.

II. Typical course types (choose as needed)
- Basic cognition (color/shape/number via object matching)
- Language enlightenment (rhythmic text/poems + pictures/audio)
- Life skills (fine-motor and self-care such as beading, buttoning)
- Arts literacy (observe material/shape to spark perception and expression)

III. Home-visit / lesson record elements (include or make easy to fill in)
1. Student basics: alias (privacy), age, disability type, current ability (e.g., "follows simple instructions").
2. Process log: by segment (e.g., emotion-settling 15 min -> cognition 20 min) with teaching-aid details.
3. Observation & feedback: objective description of behavior (e.g., "attention held 15-18 min, delighted by the light-up ball"), no subjective judgment.
4. Effect evaluation: by dimension (cognition, social-emotional, etc.) with goal attainment; optionally a 1-5 rating scale plus notes.
5. Follow-up suggestions: next-time adjustments (e.g., "add blue objects next time").
6. Home-school collaboration: a parent-observation section for out-of-class interests.
7. Safety memo: special cautions (e.g., "avoid strong light") to keep teaching safe.

IV. Safety & ethics
- Always use aliases; be respectful, inclusive, unbiased; favor positive reinforcement.
- Identify and avoid safety risks (strong light / small swallowable items / overstimulation); write cautions into the plan.
- Keep goals realistic; allow repetition and slow pace; settle emotions before instruction.
""".strip()


def _is_en(locale: Optional[str]) -> bool:
    return str(locale or "").strip().lower().startswith("en")


def lesson_skills(locale: Optional[str] = "zh-CN") -> str:
    return _LESSON_EN if _is_en(locale) else _LESSON_ZH
