"""K12 教学法指南（提示词借鉴，适配中国新课标）。

方法论借鉴自 anthropics/k12-teacher-skills 的 k12-lesson-planning 与
k12-lesson-differentiation（Claude for Teachers 官方 Agent Skills）。本文件为
**原创中文文案**，仅表达其教学法思想/事实性最佳实践，**不复制其 SKILL.md /
references / 代码任何文本**；并把其美标（CCSS/NGSS）+ Learning Commons KG 依赖
替换为**中国新课标/课程标准**语境（本项目无该连接器）。

用途：拼进所有 education_level=k12 的 AI 教师 system prompt（教案多智能体、
学期大纲、课程工具），大学/珠科链路不注入。

导出：
- is_k12(level)                 判断是否 K12
- lesson_skills(locale)         教案/大纲内容创作用
- course_tool_skills(locale)    课程工具（大纲/习题/练习/PPT）用
"""
from __future__ import annotations

from typing import Optional


def is_k12(level: Optional[str]) -> bool:
    """None / '' / 'k12' 视为 K12；其余（如 'university'）为非 K12。"""
    return (level or "k12").strip().lower() == "k12"


# ── 核心 K12 教学法（教案/大纲）─────────────────────────────────────
_LESSON_ZH = """
【K-12 教学设计准则（务必遵循，面向中小学课堂）】
1. 标准对齐：对齐国家《义务教育/普通高中课程标准》（新课标）对应学段的核心素养与学业要求；
   写清本课落在哪个知识点/能力点上，并顺应学生的认知进阶顺序。
2. 明确目标 + 成功标准：用可观察、可测量的语言写学习目标；并给出"学生达成后能做什么"的成功标准。
3. 渐进释放（我做→我们做→你做）：教师示范 → 师生共做 → 学生独立练习，逐步放手。
4. 完整课堂结构：导入(激活先验/情境)→ 新授(核心概念，配例证)→ 练习(由扶到放)→
   检查理解(CFU，穿插提问/小测)→ 小结与退出票(exit ticket，快速检测本课目标是否达成)。
5. 前置与误区：列出本课的前置知识/关键术语；预判学生常见误区并给出纠正策略。
6. 分层差异化意识：针对"低于/达到/高于"学段水平及特殊需求学生，给出可选支架或拓展
   （如降低/提高任务难度、增加范例、提供句式支架），保持核心内容一致。
7. 学习科学最佳实践：善用检索练习、间隔复习、示例-练习交替、控制认知负荷、及时反馈。
8. 版权护栏：始终原创，**不得照抄**教材/教辅/试卷的原文（阅读材料、题干、讨论问题、活动叙述等），
   可借鉴其结构与情境思路，但用自己的话重写。
9. 密度得当：内容充实但不堆砌，聚焦本课目标，确保一线教师拿来即可上课。
""".strip()

_LESSON_EN = """
[K-12 Instructional Design Principles (for school classrooms)]
1. Standards alignment: align to the national curriculum standards for the grade band; state
   the target knowledge/skill and respect the learning progression.
2. Clear objectives + success criteria: observable, measurable; state what students can do once they succeed.
3. Gradual release (I do -> we do -> you do): model, guided practice, then independent practice.
4. Full lesson arc: hook (activate prior knowledge) -> new content (with examples) -> practice
   (scaffolded to independent) -> checks for understanding -> summary + exit ticket.
5. Prerequisites & misconceptions: list prior knowledge/key terms; anticipate common misconceptions and how to address them.
6. Differentiation awareness: provide optional scaffolds/extensions for below/at/above level and special needs, keeping core content consistent.
7. Learning-science best practices: retrieval practice, spacing, worked-example/practice alternation, cognitive-load control, timely feedback.
8. Copyright guardrail: always original; never reproduce textbook/assessment text verbatim — reuse structure/ideas, rewrite in your own words.
9. Right density: rich but not bloated, focused on the objective, classroom-ready.
""".strip()


# ── 课程工具（大纲/习题/练习/PPT）精简版 ────────────────────────────
_TOOL_ZH = """
【K-12 教学素材准则】
- 对齐新课标学段与核心素养；紧扣学习目标，服务真实课堂。
- 难度与梯度贴合学段，含由扶到放的练习与检查理解环节。
- 兼顾"低于/达到/高于"水平学生的分层与支架意识。
- 始终原创，不照抄教材/试卷原文；如需引用改用自己的话重写。
""".strip()

_TOOL_EN = """
[K-12 Teaching Material Principles]
- Align to curriculum-standard grade band and core competencies; serve the learning objective and a real classroom.
- Match difficulty/progression to the grade band; include scaffolded practice and checks for understanding.
- Keep differentiation awareness for below/at/above level students.
- Always original; never copy textbook/assessment text verbatim — rewrite in your own words.
""".strip()


def _is_en(locale: Optional[str]) -> bool:
    return str(locale or "").strip().lower().startswith("en")


def lesson_skills(locale: Optional[str] = "zh-CN") -> str:
    return _LESSON_EN if _is_en(locale) else _LESSON_ZH


def course_tool_skills(locale: Optional[str] = "zh-CN") -> str:
    return _TOOL_EN if _is_en(locale) else _TOOL_ZH
