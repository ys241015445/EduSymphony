#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Call DeepSeek (OpenAI-compatible) to generate syllabus / weeks / lessons JSON.

Default model: deepseek-v4-pro (latest flagship). Override with DEEPSEEK_MODEL.
Requires DEEPSEEK_API_KEY. Does not invent content locally on failure.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-pro"  # latest flagship; see api-docs.deepseek.com
TASKS = ("syllabus", "weeks", "lessons")

SYSTEM_PROMPT = """你是珠海科技学院教学材料撰写助手。只输出一个 JSON 对象，不要 Markdown 代码围栏，不要解释或前后缀文字。
要求：
1. 与人培中的课名、学分、学时、目标口径一致；不得编造与人培冲突的学分/学时。
2. 简体中文；适合本科大纲/教案。
3. 学时切分自洽。
4. 不生成教学日历图片正文；周次只给文字教学内容。
5. 教案过程分时段（导入/精讲/演示/练习/小结等），粒度可直接上课。
6. 严格符合用户消息中给出的 JSON schema 字段。"""


def load_dotenv_nearby() -> None:
    """Load KEY=VALUE from .env next to skill root or cwd if present."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[1] / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
        except OSError:
            pass


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("context must be a JSON object")
    return data


def schema_hint(task: str) -> str:
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
    return (
        "输出 schema：lessons[{unit_index,week,title,class_hours,schedule_text,"
        "learning_situation,objectives,key_points,difficulties,methods_and_means,"
        "process[{phase,minutes,teacher_activity,student_activity,intent}],"
        "homework,reflection,materials}]"
    )


def build_user_message(task: str, context: dict) -> str:
    return (
        f"任务类型: {task}\n"
        f"{schema_hint(task)}\n\n"
        f"上下文 JSON:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def chat_completions(
    *,
    api_key: str,
    base_url: str,
    model: str,
    user_message: str,
    thinking: bool,
    timeout: int,
) -> str:
    url = base_url.rstrip("/") + "/v1/chat/completions"
    body: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "response_format": {"type": "json_object"},
        "stream": False,
        "thinking": {"type": "enabled" if thinking else "disabled"},
    }
    if thinking:
        body["reasoning_effort"] = "high"

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"DeepSeek 网络错误: {e}") from e

    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"DeepSeek 响应格式异常: {payload!r}") from e


def extract_json(text: str) -> dict:
    text = text.strip()
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


def main() -> int:
    load_dotenv_nearby()

    parser = argparse.ArgumentParser(description="Generate ZCST teaching JSON via DeepSeek")
    parser.add_argument("--task", required=True, choices=TASKS)
    parser.add_argument("--context", required=True, type=Path, help="输入上下文 JSON 路径")
    parser.add_argument("--out", required=True, type=Path, help="输出 JSON 路径")
    parser.add_argument("--model", default=os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL))
    parser.add_argument("--base-url", default=os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("DEEPSEEK_TIMEOUT", "300")))
    parser.add_argument(
        "--no-thinking",
        action="store_true",
        help="关闭 thinking（默认开启，利于长教案结构）",
    )
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        print(
            "错误: 未设置 DEEPSEEK_API_KEY。请配置环境变量或在技能目录旁写入本地 .env "
            "（勿提交仓库）。Agent 不得用自身长文顶替 DeepSeek 正文。",
            file=sys.stderr,
        )
        return 2

    try:
        context = read_json(args.context)
        raw = chat_completions(
            api_key=api_key,
            base_url=args.base_url,
            model=args.model,
            user_message=build_user_message(args.task, context),
            thinking=not args.no_thinking,
            timeout=args.timeout,
        )
        result = extract_json(raw)
    except Exception as e:
        print(f"错误: DeepSeek 生成失败 — {e}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    meta = {
        "ok": True,
        "task": args.task,
        "model": args.model,
        "out": str(args.out.resolve()),
    }
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
