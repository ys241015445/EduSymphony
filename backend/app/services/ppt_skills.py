"""Consolidated PPT design skills distilled from 20 open-source PPT projects.

每个知识块把下列开源方案的设计精华蒸馏成"可注入豆包 prompt 的中文规范"，
在不改变现有 .pptx 输出范式的前提下，全面提升生成质量。来源（编号对应用户清单）：

    02 ppt-master              — 结构化叙事 + 页面职能划分
    03 AiPPT                   — 大纲→逐页两阶段、内容密度控制
    04 ai-to-pptx              — 主题模板 token 化（配色/字体/间距成套）
    05 GordenSuperPPTSkills    — "一页一핵心观点"、金字塔表达
    06 EditDeck                — 版式栅格与对齐、留白节奏
    07 frontend-slides         — 网格系统、视觉层级、模块化卡片
    08 guizang-ppt-skill       — 高级感排版：对比/重复/亲密/对齐四原则
    09 html-ppt-skill          — 强视觉层级、大标题 + 支撑信息、数据可视化优先
    10 huashu-design           — 话术/叙事驱动，先讲故事再排版
    11 beautiful-html-templates— 精美模板美学：配色和谐、字重对比
    12 codex-ppt-skill         — 严格自检清单（信息密度、可读性、一致性）
    13 NanoBanana-PPT-Skills   — 视觉隐喻 / 图像化表达（image_prompt 描述法）
    14 banana-slides           — 图文配比、以图表意
    15 presenton               — 大纲驱动 + 说话人备注
    16 LandPPT                 — 章节化教学结构、目录/小结闭环
    17 presentation-ai         — 简洁要点、动词开头、并列结构
    18 PPTAgent                — 参考范例驱动 + 生成后自评修订
    19 visual-explainer        — 复杂概念可视化：类比/分步/对照
    20 Paper2Any               — 从长文档提炼要点、去冗余
"""
from __future__ import annotations


# ── 通用设计原则（注入大纲 + 逐页 + 兜底）─────────────────────────────
# 蒸馏自 05/07/08/09/12/17：CRAP 四原则、一页一观点、金字塔、视觉层级。
SKILL_DESIGN_PRINCIPLES = """
【顶级 PPT 设计原则（务必遵守）】
1. 一页一核心观点：每页只讲清一个主张，页标题就是这一页的"结论句"（动词/判断句，非名词短语）。
2. 金字塔表达：先给结论，再给 2-4 条支撑（论据/例子/数据），避免流水账。
3. 视觉层级分明：标题 > 关键结论 > 支撑要点 > 备注，信息按重要度分层，切忌所有文字一个字号。
4. CRAP 排版四原则：对比(Contrast) 制造重点、重复(Repetition) 保持一致、对齐(Alignment) 建立秩序、亲密(Proximity) 归类相关信息。
5. 信息密度克制：正文页要点 ≤6 条，单条 ≤50 字；宁可多分一页，也不要堆满一页。
6. 数据优先可视化：能用数字/对比/流程/时间线表达的，就别用纯文字（选 stats/big_number/timeline/comparison 等 layout）。
7. 并列结构一致：同一页的要点用统一句式（如都以动词开头），长度相近。
8. 视觉隐喻：为适合配图的页写 image_prompt（20-40 字画面描述），用具体场景/类比让抽象概念可感。
""".strip()


# ── 版式目录（注入大纲 + 兜底，指导 layout 选择）─────────────────────
# 蒸馏自 02/06/07/16/19：页面职能 + 何时用哪种版式。
SKILL_LAYOUT_CATALOG = """
【版式选择指南（按页面职能挑 layout，刻意混用制造节奏）】
- title_slide：封面，仅首页。
- agenda：目录，建议第 2 页，列本课 3-6 个模块。
- section_header：章节过渡页，每进入新模块前插一页。
- content：常规要点页，3-6 条 bullets。
- two_column：并列/分类信息（如"优点 / 局限"、"课内 / 课外"）。
- comparison：A vs B 对照（概念辨析、方法对比、正误对比），填 left_title/right_title。
- timeline：时间/历史/发展顺序，steps 3-6 个。
- process_steps：操作步骤/解题流程/实验流程，steps 3-6 个。
- stats：3-4 个关键指标并排（数据支撑、学情数据）。
- big_number：单个震撼数字/占比 + 一句解读（开场抓注意力或强调关键结论）。
- quadrant：2×2 四象限/四分类（如 SWOT、四种题型、四个维度）。
- checklist：清单/口诀/要牢记的规则（复习页、注意事项）。
- definition：核心概念的"术语 + 精准定义 + 展开"（讲新概念必用）。
- callout：一句话重点强调/金句/结论卡片。
- quote：名言/原文引用/情境导入。
- closing：结尾，总结 + 升华，仅末页。
硬性：整组至少出现 6 种不同 layout，避免连续 3 页 content；讲新概念优先 definition，
讲对比优先 comparison，讲数据优先 stats/big_number，讲流程优先 process_steps/timeline。
""".strip()


# ── 视觉/配色/字体方向（注入风格分析）───────────────────────────────
# 蒸馏自 04/06/08/11：模板 token 化、配色和谐、字重对比、留白。
SKILL_STYLE_DIRECTION = """
【视觉风格设计要点】
1. 模板要成套：配色(bg/title/body/accent/section/bullet)、版式、字体、封面变体作为一个整体协调，而非拼凑。
2. 配色和谐且对比足：主色 + 强调色 + 中性背景；title 与 bg 对比度要高，body 在 bg 上清晰可读。
3. 字重制造层级：标题重、正文常规；强调靠字重/颜色，而非全部加粗。
4. 学段适配：小学明亮暖色(kawaii/natural)；中学稳重(modern/editorial)；大学/专业课学术深色(academic/business)；计算机/工程可 tech。
5. 留白即高级感：不要填满版面，给标题和重点留出呼吸空间。
""".strip()


# ── 单页深度创作法（注入逐页生成）───────────────────────────────────
# 蒸馏自 03/10/13/15/18/19/20：叙事驱动、图文配比、自评、可视化、去冗余。
SKILL_PAGE_CRAFT = """
【单页深度创作法】
1. 叙事驱动：先想"这页要讲的一个小故事/一个问题"，再落成要点，避免干巴巴罗列。
2. 结论先行：bullet 第一条尽量是本页最重要的判断，其余作支撑。
3. 具体大于抽象：每条要点尽量带一个例子/数据/场景/类比，杜绝空泛套话。
4. 去冗余：删掉与本页核心无关的信息；同义反复只保留最有力的一条。
5. 图文意识：若本页概念抽象或适合画面，写好 image_prompt（具体画面 + 风格），供后续配图。
6. 生成后自检（PPTAgent 式）：落笔后快速核对——是否一页一观点？要点是否 ≤6 条且并列一致？
   layout 与内容是否匹配？notes 是否可让老师照着开口讲？不达标则就地修正再输出。
""".strip()


# ── 组合入口：供 prompt 拼接 ─────────────────────────────────────────

def outline_skills() -> str:
    """注入大纲阶段：设计原则 + 版式目录。"""
    return f"{SKILL_DESIGN_PRINCIPLES}\n\n{SKILL_LAYOUT_CATALOG}"


def page_skills() -> str:
    """注入逐页阶段：设计原则 + 单页创作法。"""
    return f"{SKILL_DESIGN_PRINCIPLES}\n\n{SKILL_PAGE_CRAFT}"


def single_shot_skills() -> str:
    """注入单轮兜底：设计原则 + 版式目录 + 单页创作法。"""
    return f"{SKILL_DESIGN_PRINCIPLES}\n\n{SKILL_LAYOUT_CATALOG}\n\n{SKILL_PAGE_CRAFT}"


def style_skills() -> str:
    """注入风格分析阶段。"""
    return SKILL_STYLE_DIRECTION
