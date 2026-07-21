"""guizang PPT 设计方法论（提示词借鉴，非移植）。

灵感来自 op7418/guizang-ppt-skill 的公开设计方法论（该项目为 AGPL-3.0）。
本文件为**原创中文文案**，仅表达其设计思想/事实性方法（版式体系、留白、字号对比、
主题色纪律等——思想与事实不受版权保护），**不复制其 SKILL.md / 模板 HTML / references /
assets / 校验脚本任何代码或文本**，因此不引入 AGPL 传染。

用途：
- `guizang_skills()`：拼进豆包 PPT 的 system prompt，提升排版审美与节奏。
- `THEMES`：Style A 电子墨水 5 套 + Style B 瑞士锚点色 4 套的 palette 预设，
  供 ppt_html_service 的 HTML 网页版 PPT 选用（键与项目既有 palette 对齐）。
"""
from __future__ import annotations


# ── 设计方法论（注入 PPT prompts）──────────────────────────────────
SKILL_GUIZANG = """
【网页 PPT 高级排版方法论（两套视觉体系，按内容气质择一）】
- Style A 电子杂志×电子墨水：强叙事、观点、个人风格分享。低饱和墨水底色 + 大留白 +
  杂志式版式（大标题压字、图文错落、章节页、金句页），适合演讲/分享/观点表达。
- Style B 瑞士国际主义：网格至上、单一高饱和锚点色、直角、发丝线（1px 细线）、极致字号对比，
  无阴影/无渐变/无圆角，适合事实、产品、数据、方法论表达。

【通用铁律】
1. 克制优于炫技：装饰服务信息，不要浮夸阴影/渐变/滥用色块。
2. 结构优于装饰：信息层级靠字号对比 + 字重 + 网格留白建立，而非卡片堆叠。
3. 图片是第一公民：需要配图的页用 image_prompt 写清画面（比例、主体、风格），图占主视觉。
4. 节奏靠 hero 页：hero（大标题/大数字/整图）与常规页交替，避免连续满版正文。
5. 主题色纪律：整套只用一组预设配色（主色+锚点色+中性背景），不要每页换色。
6. 大字号 + 强对比：标题极大、正文克制；关键数字/结论做成"数据大字报"独占一页。
7. 一页一观点：页标题即结论句；正文只留支撑要点，其余进演讲备注。
8. 中文标题收敛：全中文大标题比英文更占空间，需降一档字号，给正文与图片留白。
"""


def guizang_skills() -> str:
    return SKILL_GUIZANG.strip()


# ── 主题色预设（hex），键与 ppt_service/ppt_html_service 的 palette 对齐 ──
# 键：bg / title_color / body_color / accent / section_bg / bullet_color
THEMES = {
    # Style A 电子墨水（低饱和、杂志感）
    "ink_classic": {  # 墨水经典
        "bg": "#F1EFEA", "title_color": "#0A0A0B", "body_color": "#3A3A3C",
        "accent": "#0A0A0B", "section_bg": "#E7E4DC", "bullet_color": "#8A6D3B",
    },
    "ink_indigo": {  # 靛蓝瓷
        "bg": "#F1F3F5", "title_color": "#0A1F3D", "body_color": "#33414F",
        "accent": "#0A1F3D", "section_bg": "#E3E8EF", "bullet_color": "#2B6CB0",
    },
    "ink_forest": {  # 森林墨
        "bg": "#F5F1E8", "title_color": "#1A2E1F", "body_color": "#3B4A3E",
        "accent": "#1A2E1F", "section_bg": "#E8E5D6", "bullet_color": "#4E7A51",
    },
    "ink_kraft": {  # 牛皮纸
        "bg": "#EEDFC7", "title_color": "#2A1E13", "body_color": "#4A3B2A",
        "accent": "#2A1E13", "section_bg": "#E3D2B6", "bullet_color": "#A9702B",
    },
    "ink_dune": {  # 沙丘
        "bg": "#F0E6D2", "title_color": "#1F1A14", "body_color": "#453C2E",
        "accent": "#1F1A14", "section_bg": "#E6D9BE", "bullet_color": "#B08234",
    },
    # Style B 瑞士锚点色（白底 + 单一高饱和锚点）
    "swiss_ikb": {  # 克莱因蓝
        "bg": "#FFFFFF", "title_color": "#111111", "body_color": "#333333",
        "accent": "#002FA7", "section_bg": "#F2F4FA", "bullet_color": "#002FA7",
    },
    "swiss_lemon": {  # 柠檬黄
        "bg": "#FFFFFF", "title_color": "#111111", "body_color": "#333333",
        "accent": "#FFD500", "section_bg": "#FFFBEA", "bullet_color": "#8A7400",
    },
    "swiss_lime": {  # 柠檬绿
        "bg": "#FFFFFF", "title_color": "#111111", "body_color": "#333333",
        "accent": "#C5E803", "section_bg": "#F6FBE6", "bullet_color": "#5E7A00",
    },
    "swiss_orange": {  # 安全橙
        "bg": "#FFFFFF", "title_color": "#111111", "body_color": "#333333",
        "accent": "#FF6B35", "section_bg": "#FFF3EE", "bullet_color": "#C2410C",
    },
}

# 体系 → 默认主题
STYLE_A_DEFAULT = "ink_classic"
STYLE_B_DEFAULT = "swiss_ikb"


def get_theme(name: str) -> dict | None:
    return THEMES.get(name)
