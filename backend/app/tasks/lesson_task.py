import asyncio
import uuid
import json
import re
from typing import Optional, Dict, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.core.database import async_session_maker
from app.models.lesson import LessonPlan, Discussion, LessonStatus
from app.services.ai_service import AIService
from app.services.memory_service import MemoryService

AGENT_ROLES = [
    {
        "role": "教案优化专家",
        "focus": "教学流程设计、目标对齐、教学方法优化",
        "specialty": "教案优化",
        "theories": "精通各类教学模型和教学理论，擅长根据所选模型优化教案设计",
        "preferred_provider": "qwen",
    },
    {
        "role": "学生参与专家",
        "focus": "学生参与度、互动设计、学习体验提升",
        "specialty": "学生参与",
        "theories": "精通各类教学模型和教学理论，擅长运用所选教学模型提升学生课堂参与和互动",
        "preferred_provider": "kimi",
    },
    {
        "role": "创新教学专家",
        "focus": "创新教学方法、项目式学习、现代教学技术应用",
        "specialty": "创新教学",
        "theories": "精通各类教学模型和教学理论，擅长结合所选教学模型进行教学创新",
        "preferred_provider": "doubao",
    },
    {
        "role": "深度学习专家",
        "focus": "概念理解、知识迁移、深层次学习能力培养",
        "specialty": "深度学习",
        "theories": "精通各类教学模型和教学理论，擅长利用所选教学模型促进深层次学习",
        "preferred_provider": "deepseek",
    },
    {
        "role": "认知发展专家",
        "focus": "学生认知规律、思维训练、知识建构科学性",
        "specialty": "认知发展",
        "theories": "精通各类教学模型和教学理论，擅长基于认知科学和所选模型指导教学",
        "preferred_provider": "spark",
    },
]


def _build_discussion_stages_for(active_models: List[Dict]) -> List[Dict]:
    """Build flat list of per-model, per-stage items for discussion from Qwen-recommended models."""
    stages = []
    global_idx = 0
    for model in active_models:
        for local_idx, stage_name in enumerate(model["stages"]):
            stages.append({
                "key": f"{model['key']}_{local_idx}",
                "model_key": model["key"],
                "model_name": model["name"],
                "stage_name": stage_name,
                "global_idx": global_idx,
            })
            global_idx += 1
    return stages


def _build_theories_framework(active_models: List[Dict]) -> str:
    """Build teaching theory framework description from the single recommended model."""
    if not active_models:
        return ""
    model = active_models[0]
    lines = [
        f"【教学理论框架】",
        f"本教案采用「{model['name']}」教学模型。",
    ]
    if model.get("reason"):
        lines.append(f"选用理由：{model['reason']}")
    lines.append("教学阶段：")
    for j, stage in enumerate(model["stages"], 1):
        lines.append(f"  {j}. {stage}")
    lines.append(f"\n请严格按照「{model['name']}」的上述阶段顺序组织教学流程。")
    return "\n".join(lines)


def _build_stages_description_for(active_models: List[Dict]) -> str:
    """Build stages description block from the single selected model."""
    if not active_models:
        return ""
    model = active_models[0]
    lines = [f"【教学环节（{model['name']}）】"]
    for s in model["stages"]:
        lines.append(f"  - {s}")
    return "\n".join(lines)


KNOWN_MODEL_STAGES: Dict[str, List[str]] = {
    "5e": ["参与(Engage)", "探索(Explore)", "解释(Explain)", "精致化(Elaborate)", "评价(Evaluate)"],
    "boppps": ["导入(Bridge-in)", "目标(Objective)", "前测(Pre-assessment)",
               "参与式学习(Participatory)", "后测(Post-assessment)", "总结(Summary)"],
    "pbl": ["问题情境", "任务设计", "自主/合作探究", "成果展示", "反思评价"],
    "addie": ["分析(Analysis)", "设计(Design)", "开发(Development)", "实施(Implementation)", "评估(Evaluation)"],
    "flipped": ["课前自主学习", "课中内化吸收", "课中协作探究", "课后巩固拓展"],
    "situational": ["创设情境", "确定问题", "自主学习", "协作学习", "效果评价"],
    "task_based": ["任务前(Pre-task)", "任务中(Task cycle)", "任务后(Post-task)"],
    "scaffolding": ["搭建脚手架", "进入情境", "独立探索", "协作学习", "效果评价"],
    "cooperative": ["组建小组", "明确任务", "合作探究", "展示交流", "评价反思"],
    "deep_learning": ["深度导入", "深度体验", "深度探究", "深度建构", "深度评价"],
    "unit_design": ["单元目标设定", "学情分析", "内容整合", "活动设计", "多元评价"],
}


def _get_known_model_stages(key: str, name: str) -> List[str]:
    """Return known stages for common teaching models based on key or name."""
    key_lower = key.lower()
    name_lower = name.lower() if name else ""
    for model_key, stages in KNOWN_MODEL_STAGES.items():
        if model_key in key_lower or model_key in name_lower:
            return list(stages)
    if "5e" in name_lower:
        return list(KNOWN_MODEL_STAGES["5e"])
    if "boppps" in name_lower:
        return list(KNOWN_MODEL_STAGES["boppps"])
    if "pbl" in name_lower or "项目" in name_lower:
        return list(KNOWN_MODEL_STAGES["pbl"])
    if "翻转" in name_lower or "flip" in name_lower:
        return list(KNOWN_MODEL_STAGES["flipped"])
    if "情境" in name_lower:
        return list(KNOWN_MODEL_STAGES["situational"])
    if "支架" in name_lower:
        return list(KNOWN_MODEL_STAGES["scaffolding"])
    if "合作" in name_lower or "cooperative" in name_lower:
        return list(KNOWN_MODEL_STAGES["cooperative"])
    return ["导入", "新授", "实践", "巩固", "总结"]


def _parse_model_recommendation(raw_text: str) -> dict:
    """Extract model recommendation JSON from Qwen's output with robust fallback."""
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        brace_match = re.search(r'\{[\s\S]*\}', raw_text)
        if brace_match:
            json_str = brace_match.group(0)
        else:
            json_str = raw_text.strip()

    try:
        data = json.loads(json_str)
        if not isinstance(data, dict):
            raise ValueError("parsed JSON is not a dict")
        if "selected_models" in data and isinstance(data["selected_models"], list):
            valid_models = []
            for m in data["selected_models"]:
                if not isinstance(m, dict):
                    continue
                if "key" not in m:
                    m["key"] = re.sub(r'[^a-z0-9_]', '_', m.get("name", "model").lower())[:20]
                if "stages" not in m or not isinstance(m["stages"], list) or len(m["stages"]) == 0:
                    m["stages"] = _get_known_model_stages(m.get("key", ""), m.get("name", ""))
                else:
                    known = _get_known_model_stages(m.get("key", ""), m.get("name", ""))
                    if len(m["stages"]) < len(known):
                        logger.warning(f"AI returned {len(m['stages'])} stages for {m.get('name')}, expected {len(known)}, using known stages")
                        m["stages"] = known
                if "name" not in m:
                    m["name"] = m["key"]
                if "reason" not in m:
                    m["reason"] = ""
                valid_models.append(m)
            data["selected_models"] = valid_models[:1]
            if not data["selected_models"]:
                raise ValueError("empty selected_models")
            if not data.get("overall_reason"):
                m0 = data["selected_models"][0]
                data["overall_reason"] = f"基于学科特点和学生认知发展规律，推荐采用{m0['name']}。"
            return data
    except (json.JSONDecodeError, ValueError, TypeError, KeyError, AttributeError):
        pass

    logger.warning("Failed to parse model recommendation JSON, using fallback")
    return {
        "overall_reason": "基于学科特点和学生认知发展规律，推荐BOPPPS教学模型，其结构化的六步教学流程适合系统性知识传授。",
        "selected_models": [
            {
                "key": "boppps",
                "name": "BOPPPS教学模型",
                "reason": "BOPPPS模型的六步结构化教学流程（导入-目标-前测-参与式学习-后测-总结）适合系统性知识传授，能确保教学目标明确、评价完整。",
                "stages": ["导入(Bridge-in)", "目标(Objective)", "前测(Pre-assessment)",
                           "参与式学习(Participatory)", "后测(Post-assessment)", "总结(Summary)"],
            },
        ],
    }

MACAU_EXCELLENT_CASE = """【澳门地区优秀教学案例参考】
案例标题：澳门社区小导游地图制作教学案例
适用年级：小学4-6年级
课程时长：45分钟
教学活动流程：
准备活动：创设情境，明确任务（15分钟）
- 目标代号：1-1, 2-1
- 情境导入：教师播放学校宣传片片段，提出任务。范例分析与知识准备。
- 教学资源：PPT、宣传片片段、各种地图范例
- 评价方式：口语评量：观察学生是否理解任务并表现出兴趣。

发展活动：合作探究，动手创作（55分钟）
- 目标代号：2-1, 3-3, 3-1, 3-2, 1-2
- 小组组建与任务布置、实地考察与数据收集、初步绘图与设计
- 教学资源：小组角色卡、任务包、平板电脑、观察记录表、网格纸、海报纸、彩笔
- 评价方式：实作评量、作品评量（过程性）

总结活动：分享回馈，展望延伸（10分钟）
- 目标代号：3-1, 2-2
- 课堂小结与成果预览
- 评价方式：口语评量、情意评量"""

MACAU_LESSON_REQUIREMENTS = """【澳门地区教案设计特殊要求】（必须严格遵守）：
1. 教学目标必须划分为：认知目标、情意目标、技能目标三个维度
2. 教学目标必须明确对应到澳门教青局基本学力要求
3. 必须详细分析学生能力（包括认知能力、学习能力、基础水平）
4. 必须明确标注教学内容的重点和难点
5. 必须把教学内容的难点、重点与学生能力进行对应分析
6. 必须包含以下所有内容结构：
   - 课题名称、班级、人数、教材来源、设计者、时间
   - 学生背景分析
   - 政策规定的上位目标（相关的基本学力要求）
   - 本课目标
   - 教学目标（按认知/情意/技能三维划分，每个目标对应教青局基力）
   - 具体目标（3-5个可测量的学习目标，标注代号1、2、3等）
   - 学生能力分析（认知能力水平、学习基础与能力、学习困难与挑战）
   - 教学内容分析（教学内容重点+学生能力对应、教学内容难点+学生能力对应+突破策略）
   - 教学研究（设计理念与目标、学生的分析、课程架构、节次分配、教学方法与评量、参考资源）
   - 教学流程（使用表格形式，包含：目标代号、活动流程、时间、教学资源、评量五列）
   - 评价方式（体现认知/情意/技能三个维度的评价）
7. 使用繁体中文"""


def _sio():
    try:
        from app.main import sio
        return sio
    except Exception:
        return None


async def _emit(event: str, data: dict, room: Optional[str] = None):
    sio = _sio()
    if sio:
        try:
            if room:
                await sio.emit(event, data, room=room)
            else:
                await sio.emit(event, data)
        except Exception as e:
            logger.warning(f"Socket emit failed for {event}: {e}")
    else:
        logger.warning(f"Socket not available for event {event}")


def _strip_markdown(text: str) -> str:
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    return text.strip()


def _is_macau_or_hk(region: str) -> bool:
    if not region:
        return False
    return region.lower() in ('macau', 'hongkong', '澳门', '香港', 'macao')


LOCALE_INSTRUCTION = {
    "zh-CN": "",
    "zh-TW": "\n\n【語言要求】請全程使用繁體中文（台灣用語習慣）撰寫所有教案內容。",
    "en": "\n\n[Language Requirement] Please write all lesson plan content entirely in English.",
}

def _locale_hint(lesson: LessonPlan) -> str:
    return LOCALE_INSTRUCTION.get(getattr(lesson, "locale", None) or "zh-CN", "")

def _build_context(lesson: LessonPlan, parent_content: str = "") -> str:
    parts = [f"教案标题: {lesson.title}", f"学科: {lesson.subject}", f"学段: {lesson.grade_level}"]
    if lesson.specific_grade:
        parts.append(f"具体年级: {lesson.specific_grade}")
    if lesson.topic:
        parts.append(f"教案主题: {lesson.topic}")
    if lesson.student_type:
        parts.append(f"学生类别: {lesson.student_type}")
    if lesson.avoid_issues:
        parts.append(f"需要避免的问题: {lesson.avoid_issues}")
    if lesson.teacher_feedback:
        parts.append(f"\n【教师反馈（上一课）】:\n{lesson.teacher_feedback}")
    if parent_content:
        parts.append(f"\n【上一课教案摘要】:\n{parent_content[:2000]}")
    parts.append(f"\n教案内容:\n{(lesson.parsed_content or lesson.source_content or '')[:3000]}")
    return "\n".join(parts)




class LessonTaskHandler:
    def __init__(self):
        self.ai_service = AIService()
        self.memory_service = MemoryService(ai_service=self.ai_service)
        self._assign_providers()

    def _assign_providers(self):
        available = self.ai_service.get_available_providers()
        if not available:
            return
        for i, agent in enumerate(AGENT_ROLES):
            preferred = agent.get("preferred_provider")
            if preferred and preferred in available:
                agent["provider"] = preferred
            else:
                agent["provider"] = available[i % len(available)]
        provider_map = {a["role"]: a.get("provider", "?") for a in AGENT_ROLES}
        logger.info(f"AI专家模型分配: {provider_map}")

    async def process_lesson(self, lesson_id: str):
        logger.info(f"=== process_lesson STARTED for {lesson_id} ===")
        async with async_session_maker() as session:
            try:
                lesson = await self._get_lesson(session, lesson_id)
                if not lesson:
                    logger.error(f"教案不存在: {lesson_id}")
                    return

                lesson.status = LessonStatus.PROCESSING.value
                lesson.started_at = datetime.utcnow()
                lesson.final_content = None
                await session.commit()
                logger.info(f"[{lesson_id}] Status set to PROCESSING, final_content cleared")

                room = f"lesson_{lesson_id}"
                await _emit("progress_update", {
                    "lesson_id": lesson_id, "status": "processing",
                    "progress": 0, "stage": "started",
                }, room)

                parent_content = ""
                if lesson.parent_lesson_id:
                    parent = await self._get_lesson(session, lesson.parent_lesson_id)
                    if parent and parent.final_content:
                        fc_parent = parent.final_content if isinstance(parent.final_content, dict) else {}
                        parent_content = fc_parent.get("full_optimized", "") or fc_parent.get("full_draft", "")

                context = _build_context(lesson, parent_content)

                # ════════════════════════════════════════
                # PHASE 0: Qwen deep analysis → recommend teaching models
                # ════════════════════════════════════════
                logger.info(f"[{lesson_id}] PHASE 0: Qwen deep analysis for model recommendation...")
                await _emit("progress_update", {
                    "lesson_id": lesson_id, "progress": 2,
                    "stage": "model_recommendation", "message": "AI正在深度分析最适合的教学模型...",
                }, room)

                model_rec = await self._recommend_teaching_models(lesson, room, context, session)
                active_models = model_rec["selected_models"]

                lesson.final_content = {"model_recommendation": model_rec}
                lesson.progress = 10
                await session.commit()

                if lesson.mode == "semi_auto":
                    lesson.status = LessonStatus.AWAITING_CONFIRMATION.value
                    lesson.current_phase = "model_recommendation_done"
                    await session.commit()
                    await _emit("progress_update", {
                        "lesson_id": lesson_id, "status": "awaiting_confirmation",
                        "progress": 10, "stage": "awaiting_confirmation",
                        "phase": "model_recommendation_done",
                        "message": "模型分析完成，等待教师确认",
                    }, room)
                    return

                discussion_stages = _build_discussion_stages_for(active_models)
                total_discussion = len(discussion_stages)
                theories_framework = _build_theories_framework(active_models)
                model_names_str = "、".join(m["name"] for m in active_models)

                local_agents = [
                    {**agent, "theories": f"熟练掌握{model_names_str}，{model_rec['overall_reason']}"}
                    for agent in AGENT_ROLES
                ]

                # ════════════════════════════════════════
                # PHASE 1: Generate FULL initial draft (integrating recommended models)
                # ════════════════════════════════════════
                logger.info(f"[{lesson_id}] PHASE 1: Generating full integrated draft with {model_names_str}...")
                await _emit("progress_update", {
                    "lesson_id": lesson_id, "progress": 12,
                    "stage": "phase_drafts", "message": f"正在生成初步教案（融合{model_names_str}）...",
                }, room)

                full_draft = await self._generate_full_draft_stream(
                    lesson, room, context, session,
                    active_models=active_models,
                    theories_framework=theories_framework,
                    model_names_str=model_names_str,
                )

                all_final_stages = {}
                for ds in discussion_stages:
                    all_final_stages[ds["key"]] = {
                        "model_key": ds["model_key"],
                        "model_name": ds["model_name"],
                        "stage_name": ds["stage_name"],
                        "draft": "",
                        "content": "",
                        "expert": "",
                    }

                lesson.final_content = {
                    **lesson.final_content,
                    "title": lesson.title,
                    "subject": lesson.subject,
                    "grade_level": lesson.grade_level,
                    "topic": lesson.topic,
                    "student_type": lesson.student_type,
                    "teaching_models": [m["name"] for m in active_models],
                    "full_draft": full_draft,
                    "stages": all_final_stages,
                }
                lesson.progress = 40
                await session.commit()

                await _emit("all_drafts_ready", {
                    "lesson_id": lesson_id,
                    "total_stages": total_discussion,
                }, room)
                logger.info(f"[{lesson_id}] PHASE 1 complete, draft length: {len(full_draft)}")

                if lesson.mode == "semi_auto":
                    lesson.status = LessonStatus.AWAITING_CONFIRMATION.value
                    lesson.current_phase = "draft_done"
                    await session.commit()
                    await _emit("progress_update", {
                        "lesson_id": lesson_id, "status": "awaiting_confirmation",
                        "progress": 40, "stage": "awaiting_confirmation",
                        "phase": "draft_done", "message": "初步教案已生成，等待教师确认",
                    }, room)
                    return

                # ════════════════════════════════════════
                # PHASE 2: AI teacher discussion per model per stage (dynamic count)
                # ════════════════════════════════════════
                await _emit("progress_update", {
                    "lesson_id": lesson_id, "progress": 45,
                    "stage": "phase_optimize", "message": "初步教案已完成，开始按理论环节教研讨论...",
                }, room)
                logger.info(f"[{lesson_id}] PHASE 2: Per-model discussion ({total_discussion} stages)...")

                for ds in discussion_stages:
                    stage_num = ds["global_idx"] + 1
                    stage_label = f"{ds['model_name']} - {ds['stage_name']}"
                    stage_key = ds["key"]
                    idx = ds["global_idx"]

                    lesson.current_stage = stage_num
                    lesson.progress = 45 + int((idx / total_discussion) * 50)
                    await session.commit()

                    await _emit("progress_update", {
                        "lesson_id": lesson_id,
                        "progress": lesson.progress,
                        "stage": "section_start",
                        "section": stage_label,
                        "section_key": stage_key,
                        "section_index": idx,
                    }, room)

                    memory_ctx = self.memory_service.get_accumulated_context(lesson_id)
                    enriched_context = f"{context}\n\n{memory_ctx}" if memory_ctx else context

                    opinions = await self._stage1_analysis_stream(
                        session, lesson, stage_label, stage_num, room,
                        enriched_context, full_draft[:3000],
                        agents=local_agents, theories_framework=theories_framework,
                    )

                    expert_votes = await self._stage2_expert_votes(
                        session, lesson, stage_label, stage_num, opinions, room,
                        agents=local_agents,
                    )

                    best = await self._stage2_vote(
                        session, lesson, stage_label, stage_num, opinions, room,
                        expert_votes,
                    )
                    await _emit("discussion_update", {
                        "lesson_id": lesson_id, "stage": stage_num,
                        "type": "vote_complete",
                        "accepted_role": best["agent_role"],
                        "pass_rate": best.get("pass_rate", 0.6),
                        "agree": best.get("agree", 3),
                        "disagree": best.get("disagree", 2),
                    }, room)

                    final_content = await self._stage3_finalize_stream(
                        lesson, stage_label, stage_num, full_draft[:2000],
                        best["opinion"], room, context,
                        theories_framework=theories_framework,
                        model_names_str=model_names_str,
                    )

                    all_final_stages[stage_key]["content"] = final_content
                    all_final_stages[stage_key]["expert"] = best["agent_role"]

                    lesson.final_content = {
                        **lesson.final_content,
                        "stages": all_final_stages,
                    }
                    await session.commit()

                    await _emit("progress_update", {
                        "lesson_id": lesson_id,
                        "progress": 45 + int((stage_num / total_discussion) * 50),
                        "stage": "section_done",
                        "section": stage_label,
                        "section_key": stage_key,
                        "section_index": idx,
                        "content_preview": final_content[:300],
                    }, room)

                    try:
                        conv_text = "\n".join(
                            f"{o['agent_role']}: {o['opinion'][:200]}" for o in opinions
                        )
                        summary = await self.memory_service.summarize_round(conv_text)
                        accumulated = self.memory_service.get_accumulated_context(lesson_id)
                        self.memory_service.save_round_memory(
                            lesson_id=lesson_id,
                            stage=stage_num,
                            round_num=1,
                            agents=[{"role": o["agent_role"], "opinion": o["opinion"][:500]} for o in opinions],
                            vote_result={"accepted": best["agent_role"], "pass_rate": best.get("pass_rate", 0)},
                            summary=summary,
                            accumulated_context=accumulated,
                        )
                    except Exception as mem_err:
                        logger.warning(f"[{lesson_id}] Memory save failed: {mem_err}")

                # Generate full optimized document
                logger.info(f"[{lesson_id}] Generating full optimized document...")
                full_optimized = await self._generate_full_optimized_stream(
                    lesson, room, context, all_final_stages, session,
                    active_models=active_models,
                    theories_framework=theories_framework,
                    model_names_str=model_names_str,
                )
                lesson.final_content = {
                    **lesson.final_content,
                    "full_optimized": full_optimized,
                }

                lesson.status = LessonStatus.COMPLETED.value
                lesson.completed_at = datetime.utcnow()
                lesson.progress = 100
                await session.commit()

                await _emit("lesson_completed", {
                    "lesson_id": lesson_id, "status": "completed",
                }, room)
                logger.info(f"教案生成完成: {lesson_id}")

            except Exception as e:
                logger.error(f"教案生成失败 {lesson_id}: {e}", exc_info=True)
                lesson = await self._get_lesson(session, lesson_id)
                if lesson:
                    lesson.status = LessonStatus.FAILED.value
                    lesson.error_message = str(e)
                    await session.commit()
                await _emit("progress_update", {
                    "lesson_id": lesson_id, "status": "failed",
                    "error": str(e),
                }, f"lesson_{lesson_id}")

    async def process_lesson_quick(self, lesson_id: str):
        """Quick mode: only generate Phase 1 (initial draft), skip discussion & optimization."""
        logger.info(f"=== process_lesson_quick STARTED for {lesson_id} ===")
        async with async_session_maker() as session:
            try:
                lesson = await self._get_lesson(session, lesson_id)
                if not lesson:
                    logger.error(f"教案不存在: {lesson_id}")
                    return

                lesson.status = LessonStatus.PROCESSING.value
                lesson.started_at = datetime.utcnow()
                lesson.final_content = None
                await session.commit()

                room = f"lesson_{lesson_id}"
                await _emit("progress_update", {
                    "lesson_id": lesson_id, "status": "processing",
                    "progress": 0, "stage": "started",
                }, room)

                context = _build_context(lesson)

                # Phase 0: Qwen model recommendation (also in quick mode)
                logger.info(f"[{lesson_id}] QUICK Phase 0: Model recommendation...")
                await _emit("progress_update", {
                    "lesson_id": lesson_id, "progress": 5,
                    "stage": "model_recommendation", "message": "AI正在分析最适合的教学模型...",
                }, room)
                model_rec = await self._recommend_teaching_models(lesson, room, context, session)
                active_models = model_rec["selected_models"]
                theories_framework = _build_theories_framework(active_models)
                model_names_str = "、".join(m["name"] for m in active_models)

                logger.info(f"[{lesson_id}] QUICK: Generating full draft with {model_names_str}...")
                await _emit("progress_update", {
                    "lesson_id": lesson_id, "progress": 15,
                    "stage": "phase_drafts", "message": f"正在快速生成教案（{model_names_str}）...",
                }, room)

                full_draft = await self._generate_full_draft_stream(
                    lesson, room, context, session,
                    active_models=active_models,
                    theories_framework=theories_framework,
                    model_names_str=model_names_str,
                )

                lesson.final_content = {
                    "model_recommendation": model_rec,
                    "title": lesson.title,
                    "subject": lesson.subject,
                    "grade_level": lesson.grade_level,
                    "topic": lesson.topic,
                    "student_type": lesson.student_type,
                    "teaching_models": [m["name"] for m in active_models],
                    "full_draft": full_draft,
                    "stages": {},
                    "mode": "quick",
                }
                lesson.status = LessonStatus.COMPLETED.value
                lesson.completed_at = datetime.utcnow()
                lesson.progress = 100
                await session.commit()

                await _emit("lesson_completed", {
                    "lesson_id": lesson_id, "status": "completed",
                }, room)
                logger.info(f"快速教案生成完成: {lesson_id}, draft length: {len(full_draft)}")

            except Exception as e:
                logger.error(f"快速教案生成失败 {lesson_id}: {e}", exc_info=True)
                lesson = await self._get_lesson(session, lesson_id)
                if lesson:
                    lesson.status = LessonStatus.FAILED.value
                    lesson.error_message = str(e)
                    await session.commit()
                await _emit("progress_update", {
                    "lesson_id": lesson_id, "status": "failed",
                    "error": str(e),
                }, f"lesson_{lesson_id}")

    async def continue_after_model_recommendation(self, lesson_id: str):
        """Resume processing after teacher confirms model recommendation (semi-auto)."""
        logger.info(f"[{lesson_id}] Semi-auto: continuing after model recommendation...")
        async with async_session_maker() as session:
            try:
                lesson = await self._get_lesson(session, lesson_id)
                if not lesson:
                    return
                lesson.status = LessonStatus.PROCESSING.value
                await session.commit()

                room = f"lesson_{lesson_id}"
                context = _build_context(lesson)
                fc = lesson.final_content or {}
                model_rec = fc.get("model_recommendation", {})
                active_models = model_rec.get("selected_models", [])
                theories_framework = _build_theories_framework(active_models)
                model_names_str = "、".join(m["name"] for m in active_models)

                full_draft = await self._generate_full_draft_stream(
                    lesson, room, context, session,
                    active_models=active_models,
                    theories_framework=theories_framework,
                    model_names_str=model_names_str,
                )

                discussion_stages = _build_discussion_stages_for(active_models)
                all_final_stages = {}
                for ds in discussion_stages:
                    all_final_stages[ds["key"]] = {
                        "model_key": ds["model_key"], "model_name": ds["model_name"],
                        "stage_name": ds["stage_name"], "draft": "", "content": "", "expert": "",
                    }

                lesson.final_content = {
                    **fc, "title": lesson.title, "subject": lesson.subject,
                    "grade_level": lesson.grade_level, "topic": lesson.topic,
                    "student_type": lesson.student_type,
                    "teaching_models": [m["name"] for m in active_models],
                    "full_draft": full_draft, "stages": all_final_stages,
                }
                lesson.progress = 40
                await session.commit()

                if lesson.mode == "semi_auto":
                    lesson.status = LessonStatus.AWAITING_CONFIRMATION.value
                    lesson.current_phase = "draft_done"
                    await session.commit()
                    await _emit("progress_update", {
                        "lesson_id": lesson_id, "status": "awaiting_confirmation",
                        "progress": 40, "stage": "awaiting_confirmation",
                        "phase": "draft_done", "message": "初步教案已生成，等待教师确认",
                    }, room)
                    return

                await self._run_discussion_and_optimize(lesson_id, session, lesson, room, context,
                    active_models, theories_framework, model_names_str, full_draft, all_final_stages, discussion_stages)
            except Exception as e:
                logger.error(f"Continue after model rec failed {lesson_id}: {e}", exc_info=True)

    async def continue_after_draft(self, lesson_id: str):
        """Resume after teacher confirms initial draft (semi-auto)."""
        logger.info(f"[{lesson_id}] Semi-auto: continuing after draft...")
        async with async_session_maker() as session:
            try:
                lesson = await self._get_lesson(session, lesson_id)
                if not lesson:
                    return
                lesson.status = LessonStatus.PROCESSING.value
                await session.commit()

                room = f"lesson_{lesson_id}"
                context = _build_context(lesson)
                fc = lesson.final_content or {}
                model_rec = fc.get("model_recommendation", {})
                active_models = model_rec.get("selected_models", [])
                theories_framework = _build_theories_framework(active_models)
                model_names_str = "、".join(m["name"] for m in active_models)
                full_draft = fc.get("full_draft", "")
                all_final_stages = fc.get("stages", {})
                discussion_stages = _build_discussion_stages_for(active_models)

                await self._run_discussion_and_optimize(lesson_id, session, lesson, room, context,
                    active_models, theories_framework, model_names_str, full_draft, all_final_stages, discussion_stages)
            except Exception as e:
                logger.error(f"Continue after draft failed {lesson_id}: {e}", exc_info=True)

    async def continue_after_stage(self, lesson_id: str):
        """Alias for continue_after_draft - resumes from wherever discussion left off."""
        await self.continue_after_draft(lesson_id)

    async def _run_discussion_and_optimize(
        self, lesson_id, session, lesson, room, context,
        active_models, theories_framework, model_names_str, full_draft, all_final_stages, discussion_stages,
    ):
        """Shared logic: run discussion for all stages, then optimize."""
        total_discussion = len(discussion_stages)
        model_rec = (lesson.final_content or {}).get("model_recommendation", {})
        overall_reason = model_rec.get("overall_reason", "")
        theories_suffix = f"熟练掌握{model_names_str}，{overall_reason}" if overall_reason else f"熟练掌握{model_names_str}"
        local_agents = [
            {**agent, "theories": theories_suffix}
            for agent in AGENT_ROLES
        ]

        for ds in discussion_stages:
            stage_num = ds["global_idx"] + 1
            stage_label = f"{ds['model_name']} - {ds['stage_name']}"
            stage_key = ds["key"]
            idx = ds["global_idx"]

            existing = all_final_stages.get(stage_key, {})
            if existing.get("content"):
                continue

            lesson.current_stage = stage_num
            lesson.progress = 45 + int((idx / total_discussion) * 50)
            await session.commit()

            await _emit("progress_update", {
                "lesson_id": lesson_id, "progress": lesson.progress,
                "stage": "section_start", "section": stage_label,
                "section_key": stage_key, "section_index": idx,
            }, room)

            memory_ctx = self.memory_service.get_accumulated_context(lesson_id)
            enriched_context = f"{context}\n\n{memory_ctx}" if memory_ctx else context

            opinions = await self._stage1_analysis_stream(
                session, lesson, stage_label, stage_num, room,
                enriched_context, full_draft[:3000],
                agents=local_agents, theories_framework=theories_framework,
            )
            expert_votes = await self._stage2_expert_votes(
                session, lesson, stage_label, stage_num, opinions, room,
                agents=local_agents,
            )
            best = await self._stage2_vote(
                session, lesson, stage_label, stage_num, opinions, room, expert_votes,
            )
            await _emit("discussion_update", {
                "lesson_id": lesson_id, "stage": stage_num, "type": "vote_complete",
                "accepted_role": best["agent_role"], "pass_rate": best.get("pass_rate", 0.6),
                "agree": best.get("agree", 3), "disagree": best.get("disagree", 2),
            }, room)

            final_content = await self._stage3_finalize_stream(
                lesson, stage_label, stage_num, full_draft[:2000],
                best["opinion"], room, context,
                theories_framework=theories_framework, model_names_str=model_names_str,
            )
            all_final_stages[stage_key]["content"] = final_content
            all_final_stages[stage_key]["expert"] = best["agent_role"]
            lesson.final_content = {**lesson.final_content, "stages": all_final_stages}
            await session.commit()

            await _emit("progress_update", {
                "lesson_id": lesson_id, "progress": 45 + int((stage_num / total_discussion) * 50),
                "stage": "section_done", "section": stage_label, "section_key": stage_key,
                "section_index": idx, "content_preview": final_content[:300],
            }, room)

            try:
                conv_text = "\n".join(f"{o['agent_role']}: {o['opinion'][:200]}" for o in opinions)
                summary = await self.memory_service.summarize_round(conv_text)
                accumulated = self.memory_service.get_accumulated_context(lesson_id)
                self.memory_service.save_round_memory(
                    lesson_id=lesson_id, stage=stage_num, round_num=1,
                    agents=[{"role": o["agent_role"], "opinion": o["opinion"][:500]} for o in opinions],
                    vote_result={"accepted": best["agent_role"], "pass_rate": best.get("pass_rate", 0)},
                    summary=summary, accumulated_context=accumulated,
                )
            except Exception as mem_err:
                logger.warning(f"[{lesson_id}] Memory save failed: {mem_err}")

        full_optimized = await self._generate_full_optimized_stream(
            lesson, room, context, all_final_stages, session,
            active_models=active_models, theories_framework=theories_framework,
            model_names_str=model_names_str,
        )
        lesson.final_content = {**lesson.final_content, "full_optimized": full_optimized}
        lesson.status = LessonStatus.COMPLETED.value
        lesson.completed_at = datetime.utcnow()
        lesson.progress = 100
        await session.commit()

        await _emit("lesson_completed", {"lesson_id": lesson_id, "status": "completed"}, room)
        logger.info(f"教案生成完成: {lesson_id}")

    async def _get_lesson(self, session: AsyncSession, lesson_id: str) -> Optional[LessonPlan]:
        result = await session.execute(select(LessonPlan).where(LessonPlan.id == lesson_id))
        return result.scalar_one_or_none()

    # ── Phase 0: Qwen deep analysis to recommend teaching models ──

    async def _recommend_teaching_models(
        self, lesson: LessonPlan, room: str, context: str, session: AsyncSession,
    ) -> dict:
        await _emit("stream_start", {
            "lesson_id": lesson.id, "stage": 0,
            "agent_role": "教学模型分析", "phase": "model_recommendation",
        }, room)

        grade_info = lesson.specific_grade or lesson.grade_level
        student_info = f"\n学生类型：{lesson.student_type}" if lesson.student_type else ""

        preferred_theory = getattr(lesson, 'teaching_model_id', None) or ""
        if preferred_theory in ("all", ""):
            preferred_theory = ""

        if preferred_theory:
            return await self._use_teacher_selected_model(
                lesson, room, preferred_theory, grade_info, student_info,
            )

        prompt = f"""你是资深教育专家和课程设计专家。请深度分析以下课程信息，从教育学理论角度独立推导最适合的教学模型。

【课程信息】
科目：{lesson.subject}
课题/主题：{lesson.topic or lesson.title}
年级：{grade_info}{student_info}

【分析要求】
请从以下维度深度思考：
1. 该学科的核心素养和学科特点
2. 该课题的知识性质（概念建构/技能训练/情感体验/项目探究等）
3. 该年龄段学生的认知发展规律
4. 最有效的学习方式和教学组织形式

基于以上分析，推荐1个最适合的教学模型（可以是任何教育学领域的模型，
如5E模型、BOPPPS、PBL、单元整体教学、深度学习模型、翻转课堂、情境教学、
任务型教学法、支架式教学、合作学习等，也可以是你认为更合适的其他模型）。
只推荐最匹配的1个，并详细说明为什么这个模型最适合此课题。

【重要】stages字段必须列出该教学模型的所有完整阶段，不能遗漏！
例如：5E模型必须有5个阶段(Engage,Explore,Explain,Elaborate,Evaluate)；
BOPPPS必须有6个阶段；PBL至少有5个阶段。请按照该模型的标准定义列出全部阶段。

【输出格式】（严格按此JSON格式输出，不要输出其他内容）：
{{
  "overall_reason": "对该科目和课题的深度分析，说明为什么选择这个模型（150-250字，包含学科特点、知识性质、学生认知规律等分析）",
  "selected_models": [
    {{
      "key": "model_key_lowercase_english",
      "name": "教学模型名称",
      "reason": "为什么该模型最适合这个科目/课题的详细理由（100-200字）",
      "stages": ["该模型的第1阶段名称", "第2阶段名称", "...", "最后阶段名称（列出全部，不得省略）"]
    }}
  ]
}}"""

        sys_msg = "你是资深教育专家和课程设计专家。请根据学科和课题特点，从教育学理论角度分析并推荐1个最适合的教学模型。严格按JSON格式输出，selected_models数组只包含1个模型。"

        full_text = ""
        chunk_count = 0
        try:
            async for chunk in self.ai_service.generate_stream(
                prompt, provider_name="qwen", system_message=sys_msg, max_tokens=2000,
            ):
                full_text += chunk
                chunk_count += 1
                await _emit("stream_chunk", {
                    "lesson_id": lesson.id, "stage": 0,
                    "agent_role": "教学模型分析", "chunk": chunk,
                    "phase": "model_recommendation",
                }, room)
        except Exception as e:
            logger.warning(f"Model recommendation stream failed: {e}, falling back")
            try:
                full_text = await self.ai_service.generate(
                    prompt, provider_name="qwen", system_message=sys_msg, max_tokens=2000,
                )
            except Exception as e2:
                logger.warning(f"Model recommendation fallback also failed: {e2}")
                full_text = ""

        await _emit("stream_end", {
            "lesson_id": lesson.id, "stage": 0,
            "agent_role": "教学模型分析", "full_text": full_text,
            "phase": "model_recommendation",
        }, room)

        result = _parse_model_recommendation(full_text)
        logger.info(f"[{lesson.id}] Phase 0 done: recommended {[m['name'] for m in result['selected_models']]}")
        return result

    async def _use_teacher_selected_model(
        self, lesson: LessonPlan, room: str,
        preferred_theory: str, grade_info: str, student_info: str,
    ) -> dict:
        """Teacher already chose a theory in semi-auto mode — use it directly,
        only ask AI to explain how it applies to this specific lesson."""
        model_key = re.sub(r'[^a-z0-9_]', '_', preferred_theory.lower())[:20]
        stages = _get_known_model_stages(model_key, preferred_theory)

        prompt = f"""你是资深教育专家。教师已经为本节课选定了教学理论/模型：「{preferred_theory}」。
请针对以下课程信息，说明该理论如何具体应用于本节课，以及它的优势所在。

【课程信息】
科目：{lesson.subject}
课题/主题：{lesson.topic or lesson.title}
年级：{grade_info}{student_info}

请用150-250字简要阐述「{preferred_theory}」在本节课中的适用性和应用策略。
不需要推荐其他模型，直接围绕「{preferred_theory}」展开分析。"""

        sys_msg = f"你是资深教育专家。教师已选定「{preferred_theory}」，请围绕该理论分析其在本节课的适用性。直接输出分析文字，不要输出JSON。"

        full_text = ""
        try:
            async for chunk in self.ai_service.generate_stream(
                prompt, provider_name="qwen", system_message=sys_msg, max_tokens=800,
            ):
                full_text += chunk
                await _emit("stream_chunk", {
                    "lesson_id": lesson.id, "stage": 0,
                    "agent_role": "教学模型分析", "chunk": chunk,
                    "phase": "model_recommendation",
                }, room)
        except Exception as e:
            logger.warning(f"Teacher-selected model reason generation failed: {e}")
            full_text = f"教师选定「{preferred_theory}」作为本节课的教学理论。"

        await _emit("stream_end", {
            "lesson_id": lesson.id, "stage": 0,
            "agent_role": "教学模型分析", "full_text": full_text,
            "phase": "model_recommendation",
        }, room)

        result = {
            "overall_reason": full_text.strip(),
            "selected_models": [{
                "key": model_key,
                "name": preferred_theory,
                "reason": full_text.strip(),
                "stages": stages,
            }],
        }
        logger.info(f"[{lesson.id}] Phase 0 done (teacher-selected): {preferred_theory}")
        return result

    # ── Full draft generation (ONE integrated call) ──

    async def _generate_full_draft_stream(
        self, lesson: LessonPlan, room: str, context: str,
        session: AsyncSession,
        active_models: Optional[List[Dict]] = None,
        theories_framework: Optional[str] = None,
        model_names_str: Optional[str] = None,
    ) -> str:
        await _emit("stream_start", {
            "lesson_id": lesson.id, "stage": 0,
            "agent_role": "教案编写专家", "phase": "full_draft",
        }, room)
        logger.info(f"[{lesson.id}] full_draft stream_start emitted")

        is_macau = _is_macau_or_hk(getattr(lesson, 'region', '') or '')

        if not active_models:
            rec = (lesson.final_content or {}).get("model_recommendation", {})
            active_models = rec.get("selected_models", [])
        if not theories_framework:
            theories_framework = _build_theories_framework(active_models) if active_models else ""
        if not model_names_str:
            model_names_str = active_models[0]["name"] if active_models else "BOPPPS教学模型"

        stages_desc = _build_stages_description_for(active_models) if active_models else ""

        avoid_note = ""
        if lesson.avoid_issues:
            avoid_note = f"\n特别注意: 避免以下问题: {lesson.avoid_issues}"

        if is_macau:
            prompt = f"""請根據以下主題和內容，生成一份完整的教案。本教案採用{model_names_str}，請嚴格按照該模型的教學階段組織教學流程。

{context}{avoid_note}

{theories_framework}

{MACAU_EXCELLENT_CASE}

{MACAU_LESSON_REQUIREMENTS}

{stages_desc}

請嚴格按照以下格式生成一份完整的教案，每個部分都要詳細、具體、可操作：

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                      初步教學設計方案
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【課題名稱】
{lesson.title}

【班級】
{lesson.specific_grade or '待確定'}

【人數】
[填寫班級人數]

【教材來源】
[填寫教材來源]

【設計者】
AI教師

【時間】
[填寫教學日期]

【學生背景分析】
[詳細描述學生已有知識基礎、學習特點、認知水平等，至少150字]

【政策規定的上位目標（相關的基本學力要求）】
[列出相關的澳門教青局基本學力要求，至少100字，具體引用《小學教育階段基本學力要求》等文件]

【本課目標】
[概述本節課的整體目標，50-80字]

【教學目標】（按認知、情意、技能三個維度劃分，對應澳門教青局基力）

一、認知目標（Cognitive Goals）
1.1 [認知目標1] → 對應基力：[對應的基本學力要求]
1.2 [認知目標2] → 對應基力：[對應的基本學力要求]

二、情意目標（Affective Goals）
2.1 [情意目標1] → 對應基力：[對應的基本學力要求]
2.2 [情意目標2] → 對應基力：[對應的基本學力要求]

三、技能目標（Psychomotor Goals）
3.1 [技能目標1] → 對應基力：[對應的基本學力要求]
3.2 [技能目標2] → 對應基力：[對應的基本學力要求]

【具體目標】
[列出3-5個具體的、可測量的學習目標，標註代號1、2、3等]

【學生能力分析】
一、認知能力水平 [至少100字]
二、學習基礎與能力 [至少100字]
三、學習困難與挑戰 [至少80字]

【教學內容分析】
一、教學內容重點
  重點1：[內容] → 學生能力對應：[分析]
  重點2：[內容] → 學生能力對應：[分析]

二、教學內容難點
  難點1：[內容] → 學生能力對應：[分析] → 突破策略：[策略]
  難點2：[內容] → 學生能力對應：[分析] → 突破策略：[策略]

【教學研究】
一、設計理念與目標 [至少150字，體現{model_names_str}的教學理念]
二、學生的分析 [至少150字]
三、課程架構 [至少100字]
四、節次分配 [至少80字]
五、教學方法與評量 [至少100字，體現{model_names_str}的教學方法]
六、參考資源 [至少80字]

【教學流程】（嚴格按照{model_names_str}的階段組織，每個環節標註對應的階段名稱）

請使用表格形式呈現教學流程，表格必須包含：目標代號、活動流程、時間、教學資源、評量五列。
在每個教學環節中標註對應{model_names_str}的哪個階段。

【評價方式】（體現認知/情意/技能三個維度的評價，體現{model_names_str}的評價理念）

適合{lesson.grade_level}學生，學科: {lesson.subject}。
使用繁體中文。不使用Markdown標記。直接輸出純文本教案內容。"""
        else:
            prompt = f"""请根据以下主题和内容，生成一份完整的教案。本教案采用{model_names_str}，请严格按照该模型的教学阶段组织教学流程。

{context}{avoid_note}

{theories_framework}

{stages_desc}

请生成一份完整的教案，包含：

1. 教学目标（3-4个具体目标，体现{model_names_str}的教学理念）
2. 教学重点和难点
3. 教学准备
4. 学生能力分析

5. 教学过程（严格按照{model_names_str}的各个阶段顺序组织）：
   请参照上述教学理论框架中的阶段进行组织。
   每个环节包含具体的教学步骤、时间分配、教学活动设计，并标注对应{model_names_str}的哪个阶段。

6. 板书设计
7. 作业布置
8. 教学评价（体现{model_names_str}的评价理念）

适合{lesson.grade_level}学生，学科: {lesson.subject}。
确保教案结构完整，时间分配合理。
不使用Markdown标记。直接输出纯文本教案内容。"""

        locale_hint = _locale_hint(lesson)
        sys_msg = f"你是资深教案编写专家，精通{model_names_str}。请基于该教学模型生成一份完整标准教案文档，不要使用Markdown格式，直接输出纯文本。{locale_hint}"
        if is_macau:
            sys_msg = f"你是資深教案編寫專家，精通{model_names_str}，熟悉澳門地區教育政策和教青局基本學力要求。請用繁體中文基於該教學模型生成完整教案，不使用Markdown格式。"

        full_text = ""
        chunk_count = 0
        try:
            async for chunk in self.ai_service.generate_stream(
                prompt, system_message=sys_msg, max_tokens=8000,
            ):
                full_text += chunk
                chunk_count += 1
                await _emit("stream_chunk", {
                    "lesson_id": lesson.id, "stage": 0,
                    "agent_role": "教案编写专家", "chunk": chunk,
                    "phase": "full_draft",
                }, room)
                if chunk_count % 30 == 0:
                    lesson.final_content = {
                        **(lesson.final_content or {}),
                        "full_draft": full_text,
                        "_streaming": True,
                    }
                    await session.commit()
            logger.info(f"[{lesson.id}] full_draft done, {chunk_count} chunks, {len(full_text)} chars")
        except Exception as e:
            logger.warning(f"Full draft stream failed: {e}, falling back")
            full_text = await self.ai_service.generate(
                prompt, system_message=sys_msg, max_tokens=8000,
            )

        full_text = _strip_markdown(full_text)

        await _emit("stream_end", {
            "lesson_id": lesson.id, "stage": 0,
            "agent_role": "教案编写专家", "full_text": full_text,
            "phase": "full_draft",
        }, room)

        return full_text

    def _split_draft_into_stages(self, full_draft: str) -> Dict[int, str]:
        """Legacy helper — no longer used in the main flow."""
        return {}

    # ── Full optimized document generation ──

    async def _generate_full_optimized_stream(
        self, lesson: LessonPlan, room: str, context: str,
        all_final_stages: Dict, session: AsyncSession,
        active_models: Optional[List[Dict]] = None,
        theories_framework: Optional[str] = None,
        model_names_str: Optional[str] = None,
    ) -> str:
        await _emit("stream_start", {
            "lesson_id": lesson.id, "stage": 0,
            "agent_role": "教案编写专家", "phase": "full_optimized",
        }, room)

        is_macau = _is_macau_or_hk(getattr(lesson, 'region', '') or '')

        if not active_models:
            rec = (lesson.final_content or {}).get("model_recommendation", {})
            active_models = rec.get("selected_models", [])
        if not theories_framework:
            theories_framework = _build_theories_framework(active_models) if active_models else ""
        if not model_names_str:
            model_names_str = active_models[0]["name"] if active_models else "BOPPPS教学模型"

        per_stage_content = ""
        if active_models:
            model = active_models[0]
            per_stage_content += f"\n【{model['name']}各阶段优化内容】\n"
            for local_idx, stage_name in enumerate(model["stages"]):
                key = f"{model['key']}_{local_idx}"
                stage_data = all_final_stages.get(key, {})
                content = stage_data.get("content", "")
                expert = stage_data.get("expert", "")
                if content:
                    per_stage_content += f"  {stage_name}（专家: {expert}）:\n{content[:800]}\n"

        full_draft = (lesson.final_content or {}).get("full_draft", "")

        avoid_note = ""
        if lesson.avoid_issues:
            avoid_note = f"\n特别注意: 避免以下问题: {lesson.avoid_issues}"

        if is_macau:
            prompt = f"""你是教研組主持人，現在需要將初始教案和教研老師們的改進建議整合，生成一份優化後的新教案。
本教案採用{model_names_str}。

{theories_framework}

{MACAU_LESSON_REQUIREMENTS}

【初始教案】（必須完整保留結構並遵循澳門教案要求）：
{full_draft[:4000]}

【各階段教研專家優化後的內容】：
{per_stage_content}

{context}{avoid_note}

【優化要求】：
1. 保留初始教案的完整結構和主要內容，格式必須與澳門地區標準教案格式完全一致
2. 將各階段專家的優化意見逐條完整融入到對應章節
3. 在各教學環節標註對應{model_names_str}的哪個階段
4. 優化後內容比原教案更詳細（增長30-50%）
5. 改進後的內容更科學、更符合{model_names_str}的教學理論
6. 必須包含澳門教案的所有必需結構（課題名稱、班級、教學目標三維劃分、學生能力分析、教學內容分析、教學流程表格等）
7. 語言流暢自然，使用繁體中文
8. 不使用Markdown標記，直接輸出純文本
9. 教學流程必須使用表格形式（目標代號、活動流程、時間、教學資源、評量）

現在開始生成優化教案（必須包含所有必需內容結構和{model_names_str}階段標註）："""
            sys_msg = f"你是教研組主持人，精通{model_names_str}，熟悉澳門教育政策。請用繁體中文輸出，不使用Markdown格式。"
        else:
            prompt = f"""你是教研组主持人，现在需要基于初始教案和各阶段教研专家的优化意见，生成一份优化后的完整教案。
本教案采用{model_names_str}。

{theories_framework}

【初始教案】：
{full_draft[:4000]}

【各阶段教研专家优化后的内容】：
{per_stage_content}

{context}{avoid_note}

【优化要求】：
1. 保留初始教案的完整结构和主要内容
2. 将各阶段专家的优化内容逐条深度融入对应章节
3. 在各教学环节标注对应{model_names_str}的哪个阶段
4. 严格遵循{model_names_str}的教学框架组织内容
5. 优化后的教案更详细、更科学、更可操作
6. 语言流畅自然，不使用Markdown标记
7. 输出完整的教案文档

现在开始生成优化教案（标注{model_names_str}阶段对应关系）："""
            locale_hint_opt = _locale_hint(lesson)
            sys_msg = f"你是教研讨论主持人，精通{model_names_str}。请整合优化内容生成完整教案文档，不要使用Markdown格式。{locale_hint_opt}"

        full_text = ""
        chunk_count = 0
        try:
            async for chunk in self.ai_service.generate_stream(
                prompt, system_message=sys_msg, max_tokens=8000,
            ):
                full_text += chunk
                chunk_count += 1
                await _emit("stream_chunk", {
                    "lesson_id": lesson.id, "stage": 0,
                    "agent_role": "教案编写专家", "chunk": chunk,
                    "phase": "full_optimized",
                }, room)
                if chunk_count % 30 == 0:
                    lesson.final_content = {
                        **(lesson.final_content or {}),
                        "full_optimized": full_text,
                        "_streaming": True,
                    }
                    await session.commit()
        except Exception as e:
            logger.warning(f"Full optimized stream failed: {e}")
            full_text = await self.ai_service.generate(
                prompt, system_message=sys_msg, max_tokens=8000,
            )

        full_text = _strip_markdown(full_text)

        await _emit("stream_end", {
            "lesson_id": lesson.id, "stage": 0,
            "agent_role": "教案编写专家", "full_text": full_text,
            "phase": "full_optimized",
        }, room)

        return full_text

    # ── Per-stage draft generation (used by regenerate) ──

    async def _generate_draft_stream(
        self, lesson: LessonPlan, stage_name: str,
        stage_num: int, room: str, context: str,
        theories_framework: Optional[str] = None,
        model_names_str: Optional[str] = None,
    ) -> str:
        await _emit("stream_start", {
            "lesson_id": lesson.id, "stage": stage_num,
            "agent_role": "教案编写专家", "phase": "draft",
        }, room)

        is_macau = _is_macau_or_hk(getattr(lesson, 'region', '') or '')

        rec = (lesson.final_content or {}).get("model_recommendation", {})
        _active_models = rec.get("selected_models", [])
        if not theories_framework:
            theories_framework = _build_theories_framework(_active_models) if _active_models else ""
        if not model_names_str:
            model_names_str = _active_models[0]["name"] if _active_models else "BOPPPS教学模型"

        avoid_note = ""
        if lesson.avoid_issues:
            avoid_note = f"\n- 避免以下问题: {lesson.avoid_issues}"

        prompt = f"""请为教案中的"{stage_name}"环节撰写初步教案草稿。
该环节属于对应教学模型中的一个具体阶段。

{context}

{theories_framework}

{'澳门地区要求：' + MACAU_LESSON_REQUIREMENTS if is_macau else ''}

要求:
- 包含具体教学步骤、时间分配、教学活动
- 标注该环节对应{model_names_str}的哪个阶段
- 适合{lesson.grade_level}学生，学科: {lesson.subject}{avoid_note}
- {'使用繁体中文，遵循澳门教案要求' if is_macau else '语言精炼专业'}
- 不使用任何Markdown标记，直接输出纯文本"""

        sys_msg = f"你是资深教案编写专家，熟练掌握{model_names_str}等教学模型。请直接输出纯文本，不要使用Markdown格式。{_locale_hint(lesson)}"

        full_text = ""
        try:
            async for chunk in self.ai_service.generate_stream(
                prompt, system_message=sys_msg,
            ):
                full_text += chunk
                await _emit("stream_chunk", {
                    "lesson_id": lesson.id, "stage": stage_num,
                    "agent_role": "教案编写专家", "chunk": chunk,
                    "phase": "draft",
                }, room)
        except Exception as e:
            logger.warning(f"Draft stream failed: {e}")
            full_text = await self.ai_service.generate(prompt, system_message=sys_msg)

        full_text = _strip_markdown(full_text)

        await _emit("stream_end", {
            "lesson_id": lesson.id, "stage": stage_num,
            "agent_role": "教案编写专家", "full_text": full_text,
            "phase": "draft",
        }, room)

        return full_text

    # ── Phase 1: Expert (AI teacher) analysis on the draft ──

    async def _stage1_analysis_stream(
        self, session: AsyncSession, lesson: LessonPlan,
        stage_name: str, stage_num: int, room: str,
        context: str, draft: str,
        agents: Optional[List[Dict]] = None,
        theories_framework: Optional[str] = None,
    ) -> List[Dict]:
        agents = agents or AGENT_ROLES
        tasks = []
        for agent in agents:
            tasks.append(self._agent_analyze_stream(
                lesson, stage_name, agent, room, stage_num,
                context, draft,
                theories_framework=theories_framework,
            ))
        results = await asyncio.gather(*tasks, return_exceptions=True)

        opinions = []
        for i, result in enumerate(results):
            agent = agents[i]
            provider_name = agent.get("provider", "unknown")
            raw_text = result if isinstance(result, str) else f"分析生成失败 ({provider_name}): {result}"
            opinion_text = _strip_markdown(raw_text)
            disc = Discussion(
                id=str(uuid.uuid4()),
                lesson_plan_id=lesson.id,
                stage=stage_num,
                round=1,
                topic=stage_name,
                agent_role=agent["role"],
                opinion=opinion_text,
                is_accepted=False,
            )
            session.add(disc)
            opinions.append({
                "agent_role": agent["role"],
                "opinion": opinion_text,
                "id": disc.id,
                "provider": provider_name,
            })
        await session.commit()
        return opinions

    async def _agent_analyze_stream(
        self, lesson: LessonPlan, stage_name: str,
        agent: Dict, room: str, stage_num: int,
        context: str, draft: str,
        theories_framework: Optional[str] = None,
    ) -> str:
        provider_name = agent.get("provider")
        agent_role = agent["role"]
        agent_specialty = agent.get("specialty", "教学")
        agent_focus = agent.get("focus", "教学质量")
        agent_theories = agent.get("theories", "")

        await _emit("stream_start", {
            "lesson_id": lesson.id, "stage": stage_num,
            "agent_role": agent_role,
            "provider": provider_name or "",
            "phase": "analysis",
        }, room)

        is_macau = _is_macau_or_hk(getattr(lesson, 'region', '') or '')

        theories_ref = ""
        if theories_framework:
            theories_ref = f"\n\n{theories_framework}\n"

        prompt = f"""你是一位{agent_specialty}，{agent_theories}。
请从{agent_focus}角度，结合本教案所采用的教学模型，分析以下教案环节并提供改进建议。
{theories_ref}
当前教学环节: {stage_name}

教案内容：
{draft[:2500]}

请严格按照以下格式输出（简洁明确）：

关键发现：[从{agent_specialty}角度，结合教学模型发现的问题或亮点，50-80字]

主要建议：[具体可操作的改进建议，要体现所选教学模型的应用，60-100字]

专业评分：[1-10分及理由]

{'注意：请考虑澳门地区教育政策和学生特点，确保建议符合澳门教案要求。' if is_macau else ''}
注意：基于实际内容分析，简洁专业。不使用Markdown格式。"""

        sys_msg = f"你是{agent_specialty}，{agent_theories}。请用专业视角评审教案并提出改进建议。直接输出纯文本，不使用Markdown格式。"

        full_text = ""
        try:
            async for chunk in self.ai_service.generate_stream(
                prompt, provider_name=provider_name, system_message=sys_msg,
            ):
                full_text += chunk
                await _emit("stream_chunk", {
                    "lesson_id": lesson.id, "stage": stage_num,
                    "agent_role": agent_role, "chunk": chunk,
                    "phase": "analysis",
                }, room)
        except Exception as e:
            logger.warning(f"Stream failed for {agent_role}, falling back: {e}")
            full_text = await self.ai_service.generate(
                prompt, provider_name=provider_name, system_message=sys_msg,
            )

        full_text = _strip_markdown(full_text)

        await _emit("stream_end", {
            "lesson_id": lesson.id, "stage": stage_num,
            "agent_role": agent_role, "full_text": full_text,
            "phase": "analysis",
        }, room)

        return full_text

    # ── Phase 2a: Each expert votes agree/disagree on EVERY suggestion ──

    async def _stage2_expert_votes(
        self, session: AsyncSession, lesson: LessonPlan,
        stage_name: str, stage_num: int,
        opinions: List[Dict], room: str,
        agents: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """Each AI expert votes agree/disagree+reason on every opinion. Returns per-expert results."""
        opinions_text = "\n\n".join(
            f"[建议{i}] {op['agent_role']}:\n{op['opinion'][:500]}" for i, op in enumerate(opinions)
        )
        num_opinions = len(opinions)

        async def _single_expert_vote(agent: Dict) -> Dict:
            provider_name = agent.get("provider")
            agent_role = agent["role"]
            agent_specialty = agent.get("specialty", "教学")

            await _emit("stream_start", {
                "lesson_id": lesson.id, "stage": stage_num,
                "agent_role": agent_role, "phase": "expert_vote",
            }, room)

            format_lines = "\n".join(
                f"[建议{i}] {opinions[i]['agent_role']}: 赞成/反对 | 原因（20-40字）"
                for i in range(num_opinions)
            )

            prompt = f"""你是{agent_specialty}（{agent.get('theories', '')}）。
请从你的专业视角，对以下关于"{stage_name}"环节的{num_opinions}条教研建议逐一进行投票评审。
每条建议你都必须给出"赞成"或"反对"，并说明具体原因。

{opinions_text}

请严格按以下格式逐条输出（不使用Markdown标记）：

{format_lines}"""

            sys_msg = f"你是{agent_specialty}。请对每条建议独立判断，给出赞成或反对及具体原因。不使用Markdown。"
            full_text = ""
            try:
                async for chunk in self.ai_service.generate_stream(
                    prompt, provider_name=provider_name, system_message=sys_msg, max_tokens=800,
                ):
                    full_text += chunk
                    await _emit("stream_chunk", {
                        "lesson_id": lesson.id, "stage": stage_num,
                        "agent_role": agent_role, "chunk": chunk,
                        "phase": "expert_vote",
                    }, room)
            except Exception as e:
                logger.warning(f"Expert vote stream failed for {agent_role}: {e}")
                try:
                    full_text = await self.ai_service.generate(
                        prompt, provider_name=provider_name, system_message=sys_msg, max_tokens=800,
                    )
                except Exception:
                    full_text = f"投票异常: {agent_role}"

            full_text = _strip_markdown(full_text)
            await _emit("stream_end", {
                "lesson_id": lesson.id, "stage": stage_num,
                "agent_role": agent_role, "full_text": full_text,
                "phase": "expert_vote",
            }, room)

            per_opinion_votes = self._parse_per_opinion_votes(full_text, num_opinions)
            return {
                "agent_role": agent_role,
                "vote_text": full_text,
                "per_opinion": per_opinion_votes,
            }

        agents = agents or AGENT_ROLES
        tasks = [_single_expert_vote(agent) for agent in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        vote_results = []
        for i, r in enumerate(results):
            if isinstance(r, dict):
                vote_results.append(r)
            else:
                agent_role = agents[i]["role"] if i < len(agents) else "unknown"
                fallback = [{"vote": "赞成", "reason": "无法获取投票"}] * num_opinions
                vote_results.append({"agent_role": agent_role, "vote_text": str(r), "per_opinion": fallback})

        return vote_results

    @staticmethod
    def _parse_per_opinion_votes(text: str, num_opinions: int) -> List[Dict]:
        """Parse per-opinion votes from expert response text."""
        results = []
        lines = text.split('\n')
        for i in range(num_opinions):
            found = False
            for line in lines:
                if f'建议{i}' in line or f'[{i}]' in line:
                    is_agree = '赞成' in line and '反对' not in line.split('赞成')[0]
                    is_disagree = '反对' in line
                    vote = 'disagree' if is_disagree and not is_agree else 'agree'
                    if '赞成' in line and '反对' in line:
                        agree_pos = line.find('赞成')
                        disagree_pos = line.find('反对')
                        if '|' in line:
                            before_pipe = line.split('|')[0]
                            vote = 'disagree' if '反对' in before_pipe else 'agree'
                        elif ':' in line or '：' in line:
                            sep = ':' if ':' in line else '：'
                            after_sep = line.split(sep, 1)[-1].strip()
                            vote = 'disagree' if after_sep.startswith('反对') else 'agree'
                        else:
                            vote = 'disagree' if disagree_pos < agree_pos else 'agree'

                    reason = ""
                    for sep in ['|', '，', ',']:
                        if sep in line:
                            parts = line.split(sep, 1)
                            if len(parts) > 1:
                                reason = parts[-1].strip()
                                break
                    if not reason:
                        for sep in ['原因', '理由']:
                            if sep in line:
                                reason = line.split(sep, 1)[-1].strip(': ：')
                                break
                    if not reason:
                        reason = line.strip()

                    results.append({"vote": vote, "reason": reason[:100]})
                    found = True
                    break
            if not found:
                results.append({"vote": "agree", "reason": "未明确表态"})
        return results

    # ── Phase 2b: Tally per-opinion votes, save to DB, select best ──

    async def _stage2_vote(
        self, session: AsyncSession, lesson: LessonPlan,
        stage_name: str, stage_num: int,
        opinions: List[Dict], room: str,
        expert_votes: List[Dict],
    ) -> Dict:
        num_opinions = len(opinions)

        per_opinion_details: Dict[int, List[Dict]] = {i: [] for i in range(num_opinions)}
        for ev in expert_votes:
            per_opinion = ev.get("per_opinion", [])
            for oi in range(min(len(per_opinion), num_opinions)):
                per_opinion_details[oi].append({
                    "voter": ev["agent_role"],
                    "vote": per_opinion[oi].get("vote", "agree"),
                    "reason": per_opinion[oi].get("reason", ""),
                })

        per_opinion_tally = {}
        for oi in range(num_opinions):
            agree = sum(1 for v in per_opinion_details[oi] if v["vote"] == "agree")
            disagree = len(per_opinion_details[oi]) - agree
            per_opinion_tally[oi] = {"agree": agree, "disagree": disagree}

        for oi, op in enumerate(opinions):
            disc_result = await session.execute(
                select(Discussion).where(Discussion.id == op["id"])
            )
            disc = disc_result.scalar_one_or_none()
            if disc:
                disc.votes = {
                    "summary": per_opinion_tally[oi],
                    "details": per_opinion_details[oi],
                }
                total_v = per_opinion_tally[oi]["agree"] + per_opinion_tally[oi]["disagree"]
                disc.pass_rate = round(per_opinion_tally[oi]["agree"] / max(total_v, 1), 2)
        await session.commit()

        await _emit("votes_saved", {
            "lesson_id": lesson.id, "stage": stage_num,
        }, room)

        if num_opinions == 0:
            return {
                "agent_role": "未知", "opinion": "", "pass_rate": 0,
                "agree": 0, "disagree": 0,
            }

        best_idx = max(range(num_opinions), key=lambda i: per_opinion_tally[i]["agree"])

        vote_summary_lines = []
        for oi in range(num_opinions):
            t = per_opinion_tally[oi]
            marker = " ★" if oi == best_idx else ""
            vote_summary_lines.append(
                f"[建议{oi}] {opinions[oi]['agent_role']}: {t['agree']}票赞成 / {t['disagree']}票反对{marker}"
            )
        vote_summary = "\n".join(vote_summary_lines)
        vote_summary += f"\n\n投票结果: {opinions[best_idx]['agent_role']} 的建议获得最多赞成票（{per_opinion_tally[best_idx]['agree']}/{len(expert_votes)}），采纳此建议。"

        await _emit("stream_start", {
            "lesson_id": lesson.id, "stage": stage_num,
            "agent_role": "教研主持人", "phase": "vote_result",
        }, room)
        await _emit("stream_chunk", {
            "lesson_id": lesson.id, "stage": stage_num,
            "agent_role": "教研主持人", "chunk": vote_summary,
            "phase": "vote_result",
        }, room)
        await _emit("stream_end", {
            "lesson_id": lesson.id, "stage": stage_num,
            "agent_role": "教研主持人", "full_text": vote_summary,
            "phase": "vote_result",
        }, room)

        best = opinions[best_idx]

        disc_result = await session.execute(
            select(Discussion).where(Discussion.id == best["id"])
        )
        d = disc_result.scalar_one_or_none()
        if d:
            d.is_accepted = True
            await session.commit()

        best["pass_rate"] = per_opinion_tally[best_idx]["agree"] / max(len(expert_votes), 1)
        best["agree"] = per_opinion_tally[best_idx]["agree"]
        best["disagree"] = per_opinion_tally[best_idx]["disagree"]
        return best

    # ── Phase 3: Finalize incorporating draft + feedback ──

    async def _stage3_finalize_stream(
        self, lesson: LessonPlan, stage_name: str,
        stage_num: int, draft: str, accepted_opinion: str,
        room: str, context: str,
        theories_framework: Optional[str] = None,
        model_names_str: Optional[str] = None,
    ) -> str:
        await _emit("stream_start", {
            "lesson_id": lesson.id, "stage": stage_num,
            "agent_role": "教案编写专家", "phase": "finalize",
        }, room)

        is_macau = _is_macau_or_hk(getattr(lesson, 'region', '') or '')

        if not model_names_str:
            rec = (lesson.final_content or {}).get("model_recommendation", {})
            active_models = rec.get("selected_models", [])
            model_names_str = active_models[0]["name"] if active_models else "BOPPPS教学模型"

        avoid_note = ""
        if lesson.avoid_issues:
            avoid_note = f"\n- 避免以下问题: {lesson.avoid_issues}"

        prompt = f"""基于初步教案草稿和被采纳的专家改进意见，生成"{stage_name}"环节的最终优化教案。
该环节对应{model_names_str}的教学阶段。

--- 初步草稿 ---
{draft[:1500]}
--- 草稿结束 ---

--- 被采纳的专家改进意见 ---
{accepted_opinion[:1500]}
--- 意见结束 ---

融合要求:
1. 在草稿基础上将专家意见逐条深度融入教案正文
2. 不能只追加，要自然融入
3. 标注该环节对应{model_names_str}的哪个阶段
4. 优化后内容比原草稿更详细（增长30-50%）
5. 包含具体教学步骤
6. 适合{lesson.grade_level}学生，学科: {lesson.subject}{avoid_note}
7. {'使用繁体中文，遵循澳门教案格式要求，确保包含目标代号、时间、教学资源、评量等要素' if is_macau else '语言精炼专业'}
8. 不使用任何Markdown标记，直接输出纯文本"""

        sys_msg = f"你是资深教案编写专家，熟练掌握{model_names_str}等教学模型。请直接输出纯文本，不要使用Markdown格式。{_locale_hint(lesson)}"

        full_text = ""
        try:
            async for chunk in self.ai_service.generate_stream(
                prompt, system_message=sys_msg,
            ):
                full_text += chunk
                await _emit("stream_chunk", {
                    "lesson_id": lesson.id, "stage": stage_num,
                    "agent_role": "教案编写专家", "chunk": chunk,
                    "phase": "finalize",
                }, room)
        except Exception as e:
            logger.warning(f"Finalize stream failed: {e}")
            full_text = await self.ai_service.generate(prompt, system_message=sys_msg)

        full_text = _strip_markdown(full_text)

        await _emit("stream_end", {
            "lesson_id": lesson.id, "stage": stage_num,
            "agent_role": "教案编写专家", "full_text": full_text,
            "phase": "finalize",
        }, room)

        return full_text

    # ── Regenerate full draft and restart whole process ──

    async def regenerate_full_process(self, lesson_id: str):
        """Regenerate draft from scratch, then re-run discussions + optimization."""
        logger.info(f"=== regenerate_full_process for {lesson_id} ===")
        async with async_session_maker() as session:
            try:
                lesson = await self._get_lesson(session, lesson_id)
                if not lesson:
                    raise ValueError("教案不存在")

                lesson.status = LessonStatus.PROCESSING.value
                lesson.progress = 5
                lesson.final_content = None
                await session.commit()

                room = f"lesson_{lesson_id}"
                context = _build_context(lesson)

                # Clear old discussions
                old_discs = await session.execute(
                    select(Discussion).where(Discussion.lesson_plan_id == lesson_id)
                )
                for d in old_discs.scalars().all():
                    await session.delete(d)
                await session.commit()

                await _emit("progress_update", {
                    "lesson_id": lesson_id, "status": "processing",
                    "progress": 2, "stage": "model_recommendation", "message": "AI正在重新分析最适合的教学模型...",
                }, room)

                model_rec = await self._recommend_teaching_models(lesson, room, context, session)
                active_models = model_rec["selected_models"]
                theories_framework = _build_theories_framework(active_models)
                model_names_str = "、".join(m["name"] for m in active_models)

                lesson.final_content = {"model_recommendation": model_rec}
                lesson.progress = 10
                await session.commit()

                local_agents = [
                    {**agent, "theories": f"熟练掌握{model_names_str}，{model_rec['overall_reason']}"}
                    for agent in AGENT_ROLES
                ]

                await _emit("progress_update", {
                    "lesson_id": lesson_id, "progress": 12,
                    "stage": "phase_drafts", "message": f"正在重新生成初步教案（{model_names_str}）...",
                }, room)

                full_draft = await self._generate_full_draft_stream(
                    lesson, room, context, session,
                    active_models=active_models,
                    theories_framework=theories_framework,
                    model_names_str=model_names_str,
                )

                discussion_stages = _build_discussion_stages_for(active_models)
                total_discussion = len(discussion_stages)
                all_final_stages = {}
                for ds in discussion_stages:
                    all_final_stages[ds["key"]] = {
                        "model_key": ds["model_key"],
                        "model_name": ds["model_name"],
                        "stage_name": ds["stage_name"],
                        "draft": "",
                        "content": "",
                        "expert": "",
                    }

                lesson.final_content = {
                    **lesson.final_content,
                    "title": lesson.title, "subject": lesson.subject,
                    "grade_level": lesson.grade_level, "topic": lesson.topic,
                    "student_type": lesson.student_type,
                    "teaching_models": [m["name"] for m in active_models],
                    "full_draft": full_draft, "stages": all_final_stages,
                }
                lesson.progress = 40
                await session.commit()

                await _emit("all_drafts_ready", {"lesson_id": lesson_id, "total_stages": total_discussion}, room)
                await _emit("progress_update", {
                    "lesson_id": lesson_id, "progress": 45,
                    "stage": "phase_optimize", "message": "初步教案已重新生成，开始按理论环节教研讨论...",
                }, room)

                for ds in discussion_stages:
                    stage_num = ds["global_idx"] + 1
                    stage_label = f"{ds['model_name']} - {ds['stage_name']}"
                    stage_key = ds["key"]
                    idx = ds["global_idx"]

                    lesson.current_stage = stage_num
                    lesson.progress = 45 + int((idx / total_discussion) * 50)
                    await session.commit()

                    await _emit("progress_update", {
                        "lesson_id": lesson_id, "progress": lesson.progress,
                        "stage": "section_start", "section": stage_label,
                        "section_key": stage_key, "section_index": idx,
                    }, room)

                    memory_ctx = self.memory_service.get_accumulated_context(lesson_id)
                    enriched_context = f"{context}\n\n{memory_ctx}" if memory_ctx else context

                    opinions = await self._stage1_analysis_stream(
                        session, lesson, stage_label, stage_num, room, enriched_context, full_draft[:3000],
                        agents=local_agents, theories_framework=theories_framework,
                    )
                    expert_votes = await self._stage2_expert_votes(
                        session, lesson, stage_label, stage_num, opinions, room,
                        agents=local_agents,
                    )
                    best = await self._stage2_vote(session, lesson, stage_label, stage_num, opinions, room, expert_votes)
                    await _emit("discussion_update", {
                        "lesson_id": lesson_id, "stage": stage_num,
                        "type": "vote_complete", "accepted_role": best["agent_role"],
                        "pass_rate": best.get("pass_rate", 0.6),
                        "agree": best.get("agree", 3),
                        "disagree": best.get("disagree", 2),
                    }, room)

                    final_content = await self._stage3_finalize_stream(
                        lesson, stage_label, stage_num, full_draft[:2000], best["opinion"], room, enriched_context,
                        theories_framework=theories_framework,
                        model_names_str=model_names_str,
                    )
                    all_final_stages[stage_key]["content"] = final_content
                    all_final_stages[stage_key]["expert"] = best["agent_role"]
                    lesson.final_content = {**lesson.final_content, "stages": all_final_stages}
                    await session.commit()

                    try:
                        conv_text = "\n".join(f"{o['agent_role']}: {o['opinion'][:200]}" for o in opinions)
                        summary = await self.memory_service.summarize_round(conv_text)
                        accumulated = self.memory_service.get_accumulated_context(lesson_id)
                        self.memory_service.save_round_memory(
                            lesson_id=lesson_id, stage=stage_num, round_num=1,
                            agents=[{"role": o["agent_role"], "opinion": o["opinion"][:500]} for o in opinions],
                            vote_result={"accepted": best["agent_role"], "pass_rate": best.get("pass_rate", 0)},
                            summary=summary, accumulated_context=accumulated,
                        )
                    except Exception as mem_err:
                        logger.warning(f"[{lesson_id}] Memory save failed in regenerate: {mem_err}")

                    await _emit("progress_update", {
                        "lesson_id": lesson_id,
                        "progress": 45 + int((stage_num / total_discussion) * 50),
                        "stage": "section_done", "section": stage_label,
                        "section_key": stage_key, "section_index": idx,
                        "content_preview": final_content[:300],
                    }, room)

                full_optimized = await self._generate_full_optimized_stream(
                    lesson, room, context, all_final_stages, session,
                    active_models=active_models,
                    theories_framework=theories_framework,
                    model_names_str=model_names_str,
                )
                lesson.final_content = {**lesson.final_content, "full_optimized": full_optimized}
                lesson.status = LessonStatus.COMPLETED.value
                lesson.completed_at = datetime.utcnow()
                lesson.progress = 100
                await session.commit()

                await _emit("lesson_completed", {"lesson_id": lesson_id, "status": "completed"}, room)
                logger.info(f"regenerate_full_process completed: {lesson_id}")

            except Exception as e:
                logger.error(f"regenerate_full_process failed {lesson_id}: {e}", exc_info=True)
                lesson = await self._get_lesson(session, lesson_id)
                if lesson:
                    lesson.status = LessonStatus.FAILED.value
                    lesson.error_message = str(e)
                    await session.commit()
                await _emit("progress_update", {
                    "lesson_id": lesson_id, "status": "failed", "error": str(e),
                }, f"lesson_{lesson_id}")

    # ── Re-optimize: keep draft + discussions, regenerate optimized doc ──

    async def regenerate_optimized(self, lesson_id: str):
        """Re-run optimization using existing draft and discussions."""
        logger.info(f"=== regenerate_optimized for {lesson_id} ===")
        async with async_session_maker() as session:
            try:
                lesson = await self._get_lesson(session, lesson_id)
                if not lesson or not lesson.final_content:
                    raise ValueError("教案不存在或尚未生成")

                room = f"lesson_{lesson_id}"
                context = _build_context(lesson)
                all_final_stages = lesson.final_content.get("stages", {})

                lesson.status = LessonStatus.PROCESSING.value
                lesson.progress = 80
                if lesson.final_content and "full_optimized" in lesson.final_content:
                    fc = dict(lesson.final_content)
                    del fc["full_optimized"]
                    lesson.final_content = fc
                await session.commit()

                await _emit("progress_update", {
                    "lesson_id": lesson_id, "status": "processing",
                    "progress": 80, "stage": "re_optimize", "message": "正在二次优化教案...",
                }, room)

                full_optimized = await self._generate_full_optimized_stream(
                    lesson, room, context, all_final_stages, session,
                )
                lesson.final_content = {**lesson.final_content, "full_optimized": full_optimized}
                lesson.status = LessonStatus.COMPLETED.value
                lesson.completed_at = datetime.utcnow()
                lesson.progress = 100
                await session.commit()

                await _emit("lesson_completed", {"lesson_id": lesson_id, "status": "completed"}, room)
                logger.info(f"regenerate_optimized completed: {lesson_id}")

            except Exception as e:
                logger.error(f"regenerate_optimized failed {lesson_id}: {e}", exc_info=True)
                lesson = await self._get_lesson(session, lesson_id)
                if lesson:
                    lesson.status = LessonStatus.FAILED.value
                    lesson.error_message = str(e)
                    await session.commit()
                await _emit("progress_update", {
                    "lesson_id": lesson_id, "status": "failed", "error": str(e),
                }, f"lesson_{lesson_id}")

    # ── Regenerate a single stage ──

    async def regenerate_single_stage(
        self, lesson_id: str, stage_key: str, version: str = "draft",
    ) -> str:
        async with async_session_maker() as session:
            lesson = await self._get_lesson(session, lesson_id)
            if not lesson or not lesson.final_content:
                raise ValueError("教案不存在或尚未生成")

            stages = lesson.final_content.get("stages", {})
            stage_data = stages.get(stage_key)
            if not stage_data:
                raise ValueError(f"环节 {stage_key} 不存在")

            context = _build_context(lesson)
            model_name = stage_data.get("model_name", "")
            stage_name = stage_data.get("stage_name", "")
            stage_label = f"{model_name} - {stage_name}" if model_name else stage_name

            rec = (lesson.final_content or {}).get("model_recommendation", {})
            active_models = rec.get("selected_models", [])
            theories_framework = _build_theories_framework(active_models) if active_models else None
            model_names_str = "、".join(m["name"] for m in active_models) if active_models else None

            discussion_stages = _build_discussion_stages_for(active_models) if active_models else []
            stage_num = next(
                (ds["global_idx"] + 1 for ds in discussion_stages if ds["key"] == stage_key),
                1,
            )
            room = f"lesson_{lesson_id}"
            full_draft = (lesson.final_content or {}).get("full_draft", "")

            if version == "draft":
                new_text = await self._generate_draft_stream(
                    lesson, stage_label, stage_num, room, context,
                    theories_framework=theories_framework,
                    model_names_str=model_names_str,
                )
                stage_data["draft"] = new_text
            else:
                disc_result = await session.execute(
                    select(Discussion).where(
                        Discussion.lesson_plan_id == lesson_id,
                        Discussion.stage == stage_num,
                        Discussion.is_accepted == True,
                    )
                )
                accepted_disc = disc_result.scalar_one_or_none()
                accepted_opinion = accepted_disc.opinion if accepted_disc else ""

                new_text = await self._stage3_finalize_stream(
                    lesson, stage_label, stage_num, full_draft[:2000],
                    accepted_opinion, room, context,
                    theories_framework=theories_framework,
                    model_names_str=model_names_str,
                )
                stage_data["content"] = new_text

            stages[stage_key] = stage_data
            lesson.final_content = {**lesson.final_content, "stages": stages}
            await session.commit()

            await _emit("stage_regenerated", {
                "lesson_id": lesson_id,
                "stage_key": stage_key,
                "version": version,
                "content": new_text,
            }, room)

            return new_text
