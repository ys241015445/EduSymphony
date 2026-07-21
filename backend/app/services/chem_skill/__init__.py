"""Vendored + adapted `edu-chem-reaction` skill for chemistry teaching materials.

移植自 edulab（github.com/wy51ai/edulab，Apache-2.0）的 edu-chem-reaction 技能：
用 SymPy 配平 + 校验原子守恒/映射 + 推导键差，产出 Three.js + KaTeX 可交互微观反应演示网页。

模块：
- reaction_kernel : SymPy 配平/校验/装配核心（忠实移植）
- molecules       : VSEPR 分子几何库（忠实移植）
- reaction_template.html : 数据驱动模板（忠实移植）
- render          : assemble_data 结果 -> HTML 字符串（后端适配，不落盘）
- presets         : 6 个反应预设 + REGISTRY + generate_reaction_html（改造自 generate.py）
- extract         : 化学检测 + 分类到预设（新增）

对外主入口：`generate_reaction_html(key) -> str`、`classify_reaction`、`looks_like_chemistry`。
"""
from .presets import generate_reaction_html, list_presets, REGISTRY  # noqa: F401
from .extract import looks_like_chemistry, classify_reaction  # noqa: F401
