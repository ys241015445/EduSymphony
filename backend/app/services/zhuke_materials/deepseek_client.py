"""DeepSeek client for 珠科材料助手 (skill deepseek-contract).

Requires DEEPSEEK_API_KEY. Never invents long-form content on failure.
"""
from __future__ import annotations

import json
from typing import Any, Dict

import httpx
from loguru import logger

from app.core.config import settings

DEFAULT_MODEL = "deepseek-v4-pro"
TASKS = ("syllabus", "weeks", "lessons", "material_html", "ppt_deck")

SYSTEM_PROMPT = """你是珠海科技学院教学材料撰写助手。只输出一个 JSON 对象，不要 Markdown 代码围栏，不要解释或前后缀文字。
要求：
1. 与人培中的课名、学分、学时、目标口径一致；不得编造与人培冲突的学分/学时。
2. 简体中文；适合本科大纲/教案。
3. 学时切分自洽。
4. 不生成教学日历图片正文；周次只给文字教学内容。
5. 教案过程分时段（导入/精讲/演示/练习/小结等），粒度可直接上课。
6. 严格符合用户消息中给出的 JSON schema 字段。
7. 生成交互式教学材料 / PPT 时：紧扣给定大纲、进度表授课内容与教案，不得另起无关主题。"""


def _schema_hint(task: str) -> str:
    if task == "syllabus":
        return (
            "输出 schema：course_name, course_code, credits, total_hours, theory_hours, "
            "lab_hours, course_nature, applicable_major, prerequisites, course_objectives[], "
            "course_intro, teaching_methods, assessment{usual_percent,lab_percent,final_percent,notes}, "
            "chapters[{no,title,hours,theory_or_lab,objectives,content,key_points,difficulties,methods_note}], "
            "textbooks[], references[], other_notes"
        )
    if task == "weeks":
        return (
            "输出 schema：meta{course_name,course_code,class_name,schedule}, "
            "theory_weeks[{week,hours,teaching_content,chapter_ref}], "
            "lab_weeks[{week,hours,teaching_content,experiment_name}]"
        )
    if task == "material_html":
        return (
            "输出 schema（交互式教学材料）：title, summary（100-200字）, "
            "sections[{id,title,icon,content（每节至少200字详细说明）,diagram_hint,quiz[{question,answer}]}]；"
            "sections 至少 6 个；icon 可用 fa-book / fa-lightbulb / fa-flask 等 FontAwesome 名；"
            "内容须覆盖上下文中的大纲章节、进度表授课内容与教案重难点。"
        )
    if task == "ppt_deck":
        return (
            "输出 schema（课堂 PPT）：title, subtitle, "
            "slides[{layout,title,subtitle?,bullets[],notes}]；"
            "layout 取值：title_slide / section / content / two_column / image_focus / summary / quiz；"
            "slides 12–20 页；首页 title_slide，中间多样 layout，末页 summary；"
            "bullets 每页 3–6 条，可直接投影；紧扣大纲+进度表授课内容+教案过程。"
        )
    return (
        "输出 schema：lessons[{unit_index,week,title,class_hours,schedule_text,"
        "learning_situation,objectives,key_points,difficulties,methods_and_means,"
        "process[{phase,minutes,teacher_activity,student_activity,intent}],"
        "homework,reflection,materials}]"
    )


def _model() -> str:
    # Prefer explicit materials model; else DEEPSEEK_MODEL; else skill default.
    explicit = (getattr(settings, "ZHUKE_MATERIALS_DEEPSEEK_MODEL", "") or "").strip()
    if explicit:
        return explicit
    m = (settings.DEEPSEEK_MODEL or "").strip()
    if m:
        return m
    return DEFAULT_MODEL


def _base_url() -> str:
    base = (settings.DEEPSEEK_BASE_URL or "https://api.deepseek.com").rstrip("/")
    # settings often include /v1 already
    if base.endswith("/v1"):
        return base[: -len("/v1")]
    return base


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("模型输出不是 JSON 对象")
    return obj


async def generate(task: str, context: Dict[str, Any], *, timeout: float = 300.0) -> Dict[str, Any]:
    if task not in TASKS:
        raise ValueError(f"unknown task: {task}")
    api_key = (settings.DEEPSEEK_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError(
            "未配置 DEEPSEEK_API_KEY。珠科材料助手正文必须由 DeepSeek 生成，禁止本地代写。"
        )

    user_message = (
        f"任务类型: {task}\n{_schema_hint(task)}\n\n"
        f"上下文 JSON:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    url = _base_url().rstrip("/") + "/v1/chat/completions"
    model = _model()
    body: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "response_format": {"type": "json_object"},
        "stream": False,
    }
    # thinking 对部分模型可用；失败时降级重试
    body_thinking = {
        **body,
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        last_err: Exception | None = None
        for payload in (body_thinking, body):
            try:
                resp = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if resp.status_code >= 400:
                    last_err = RuntimeError(f"DeepSeek HTTP {resp.status_code}: {resp.text[:800]}")
                    logger.warning(f"[zhuke_materials] DeepSeek attempt failed: {last_err}")
                    continue
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return _extract_json(content)
            except Exception as e:
                last_err = e
                logger.warning(f"[zhuke_materials] DeepSeek attempt error: {e}")
                continue
        raise RuntimeError(f"DeepSeek 生成失败: {last_err}")
