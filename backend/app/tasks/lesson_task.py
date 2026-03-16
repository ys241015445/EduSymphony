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

AGENT_ROLES = [
    {
        "role": "教案优化专家",
        "focus": "教学流程设计、目标对齐、教学方法优化",
        "specialty": "教案优化",
        "theories": "精通5E教学模型、BOPPPS教学模型、PBL项目式学习三种教学理论，擅长将三种理论融合应用于教案设计",
        "preferred_provider": "qwen",
    },
    {
        "role": "学生参与专家",
        "focus": "学生参与度、互动设计、学习体验提升",
        "specialty": "学生参与",
        "theories": "精通5E教学模型、BOPPPS教学模型、PBL项目式学习三种教学理论，擅长运用三种理论提升学生课堂参与和互动",
        "preferred_provider": "kimi",
    },
    {
        "role": "创新教学专家",
        "focus": "创新教学方法、项目式学习、现代教学技术应用",
        "specialty": "创新教学",
        "theories": "精通5E教学模型、BOPPPS教学模型、PBL项目式学习三种教学理论，擅长结合三种理论进行教学创新",
        "preferred_provider": "doubao",
    },
    {
        "role": "深度学习专家",
        "focus": "概念理解、知识迁移、深层次学习能力培养",
        "specialty": "深度学习",
        "theories": "精通5E教学模型、BOPPPS教学模型、PBL项目式学习三种教学理论，擅长利用三种理论促进深层次学习",
        "preferred_provider": "deepseek",
    },
    {
        "role": "认知发展专家",
        "focus": "学生认知规律、思维训练、知识建构科学性",
        "specialty": "认知发展",
        "theories": "精通5E教学模型、BOPPPS教学模型、PBL项目式学习三种教学理论，擅长基于认知科学整合三种理论",
        "preferred_provider": "spark",
    },
]

ALL_MODELS = [
    {"key": "5e", "name": "5E教学模型", "stages": [
        "引入(Engage)", "探索(Explore)", "解释(Explain)", "拓展(Extend)", "评价(Evaluate)",
    ]},
    {"key": "boppps", "name": "BOPPPS教学模型", "stages": [
        "导入(Bridge-in)", "目标(Objective)", "前测(Pre-assessment)",
        "参与式学习(Participatory)", "后测(Post-assessment)", "总结(Summary)",
    ]},
    {"key": "pbl", "name": "PBL教学模型", "stages": [
        "问题情境", "任务设计", "实施过程", "成果展示", "反思评价",
    ]},
]


def _build_all_discussion_stages() -> List[Dict]:
    """Build the flat list of per-theory, per-stage items for discussion (16 total)."""
    stages = []
    global_idx = 0
    for model in ALL_MODELS:
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

THREE_THEORIES_FRAMEWORK = """【三大教学理论框架（本教案综合融合运用）】

一、5E教学模型（Engage-Explore-Explain-Extend-Evaluate）
1. 引入（Engage）：吸引学生注意力并激发探究兴趣，利用认知冲突或情境问题。
2. 探究（Explore）：学生基于已有知识进行自主探究，建构新意义，习得新技能。
3. 解释（Explain）：学生解释探索收获，教师引导整理概念，促进理解。
4. 应用/迁移（Extend）：在新情境下应用知识解决新问题（基于最近发展区）。
5. 评估（Evaluate）：多元评价真实反馈学习，形成性+总结性评估。

二、BOPPPS教学模型（Bridge-in-Objective-Pre-assessment-Participatory-Post-assessment-Summary）
1. 导入（Bridge-in）：建立学习兴趣与动机。
2. 目标（Objective）：明确学习目标，让学生知道要学什么。
3. 前测（Pre-assessment）：诊断学生已有知识和能力水平。
4. 参与式学习（Participatory）：学生主动参与学习活动。
5. 后测（Post-assessment）：检测学习成果。
6. 总结（Summary）：梳理总结，巩固迁移。

三、PBL项目式学习（Problem-Based Learning）
1. 问题情境：创设真实问题情境，激发学习动机。
2. 任务设计：设计有挑战性的学习任务。
3. 实施过程：学生自主探究、小组合作完成任务。
4. 成果展示：学生展示学习成果，交流分享。
5. 反思评价：反思学习过程，评价学习成效。

【融合理念】：三种理论不是分开使用，而是有机整合在教学的每个环节中。
例如：导入环节同时体现5E的引入激趣、BOPPPS的桥接导入、PBL的问题情境创设。"""

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


def _build_context(lesson: LessonPlan) -> str:
    parts = [f"教案标题: {lesson.title}", f"学科: {lesson.subject}", f"学段: {lesson.grade_level}"]
    if lesson.specific_grade:
        parts.append(f"具体年级: {lesson.specific_grade}")
    if lesson.topic:
        parts.append(f"教案主题: {lesson.topic}")
    if lesson.student_type:
        parts.append(f"学生类别: {lesson.student_type}")
    if lesson.avoid_issues:
        parts.append(f"需要避免的问题: {lesson.avoid_issues}")
    parts.append(f"\n教案内容:\n{(lesson.parsed_content or lesson.source_content or '')[:3000]}")
    return "\n".join(parts)


def _build_stages_description() -> str:
    lines = ["【教学环节（融合三大理论）】"]
    for model in ALL_MODELS:
        lines.append(f"\n{model['name']}:")
        for s in model["stages"]:
            lines.append(f"  - {s}")
    return "\n".join(lines)


class LessonTaskHandler:
    def __init__(self):
        self.ai_service = AIService()
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

                context = _build_context(lesson)
                discussion_stages = _build_all_discussion_stages()
                total_discussion = len(discussion_stages)

                # ════════════════════════════════════════
                # PHASE 1: Generate FULL initial draft (integrating all 3 theories)
                # ════════════════════════════════════════
                logger.info(f"[{lesson_id}] PHASE 1: Generating full integrated draft...")
                await _emit("progress_update", {
                    "lesson_id": lesson_id, "progress": 5,
                    "stage": "phase_drafts", "message": "正在生成初步教案（融合5E+BOPPPS+PBL）...",
                }, room)

                full_draft = await self._generate_full_draft_stream(
                    lesson, room, context, session,
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
                    "title": lesson.title,
                    "subject": lesson.subject,
                    "grade_level": lesson.grade_level,
                    "topic": lesson.topic,
                    "student_type": lesson.student_type,
                    "teaching_models": ["5E", "BOPPPS", "PBL"],
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

                # ════════════════════════════════════════
                # PHASE 2: AI teacher discussion per theory per stage (16 items)
                # ════════════════════════════════════════
                await _emit("progress_update", {
                    "lesson_id": lesson_id, "progress": 45,
                    "stage": "phase_optimize", "message": "初步教案已完成，开始按理论环节教研讨论...",
                }, room)
                logger.info(f"[{lesson_id}] PHASE 2: Per-theory discussion ({total_discussion} stages)...")

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

                    opinions = await self._stage1_analysis_stream(
                        session, lesson, stage_label, stage_num, room,
                        context, full_draft[:3000],
                    )

                    expert_votes = await self._stage2_expert_votes(
                        session, lesson, stage_label, stage_num, opinions, room,
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

                # Generate full optimized document
                logger.info(f"[{lesson_id}] Generating full optimized document...")
                full_optimized = await self._generate_full_optimized_stream(
                    lesson, room, context, all_final_stages, session,
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

                logger.info(f"[{lesson_id}] QUICK: Generating full draft...")
                await _emit("progress_update", {
                    "lesson_id": lesson_id, "progress": 10,
                    "stage": "phase_drafts", "message": "正在快速生成教案...",
                }, room)

                full_draft = await self._generate_full_draft_stream(
                    lesson, room, context, session,
                )

                lesson.final_content = {
                    "title": lesson.title,
                    "subject": lesson.subject,
                    "grade_level": lesson.grade_level,
                    "topic": lesson.topic,
                    "student_type": lesson.student_type,
                    "teaching_models": ["5E", "BOPPPS", "PBL"],
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

    async def _get_lesson(self, session: AsyncSession, lesson_id: str) -> Optional[LessonPlan]:
        result = await session.execute(select(LessonPlan).where(LessonPlan.id == lesson_id))
        return result.scalar_one_or_none()

    # ── Full draft generation (ONE integrated call) ──

    async def _generate_full_draft_stream(
        self, lesson: LessonPlan, room: str, context: str,
        session: AsyncSession,
    ) -> str:
        await _emit("stream_start", {
            "lesson_id": lesson.id, "stage": 0,
            "agent_role": "教案编写专家", "phase": "full_draft",
        }, room)
        logger.info(f"[{lesson.id}] full_draft stream_start emitted")

        is_macau = _is_macau_or_hk(getattr(lesson, 'region', '') or '')
        stages_desc = _build_stages_description()

        avoid_note = ""
        if lesson.avoid_issues:
            avoid_note = f"\n特别注意: 避免以下问题: {lesson.avoid_issues}"

        if is_macau:
            prompt = f"""請根據以下主題和內容，生成一份完整的教案。本教案必須綜合融合5E教學模型、BOPPPS教學模型、PBL項目式學習三種教學理論，不是分開生成三份，而是融合成一份完整的教案。

{context}{avoid_note}

{THREE_THEORIES_FRAMEWORK}

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
一、設計理念與目標 [至少150字，體現5E+BOPPPS+PBL融合理念]
二、學生的分析 [至少150字]
三、課程架構 [至少100字]
四、節次分配 [至少80字]
五、教學方法與評量 [至少100字，體現三種理論的融合應用]
六、參考資源 [至少80字]

【教學流程】（融合5E+BOPPPS+PBL三大理論，每個環節標註對應的理論要素）

請使用表格形式呈現教學流程，表格必須包含：目標代號、活動流程、時間、教學資源、評量五列。
在每個教學環節中標註融合了哪些理論要素，如：【5E-引入+BOPPPS-導入+PBL-問題情境】

環節一：導入與情境創設
環節二：目標確定與前測
環節三：探究與任務設計
環節四：參與式學習與實施
環節五：解釋與成果展示
環節六：拓展應用
環節七：評價與反思
環節八：總結

【評價方式】（體現認知/情意/技能三個維度的評價，融合三種理論的評價理念）

適合{lesson.grade_level}學生，學科: {lesson.subject}。
使用繁體中文。不使用Markdown標記。直接輸出純文本教案內容。"""
        else:
            prompt = f"""请根据以下主题和内容，生成一份完整的教案。本教案必须综合融合5E教学模型、BOPPPS教学模型、PBL项目式学习三种教学理论，不是分开生成三份，而是融合成一份完整的教案。

{context}{avoid_note}

{THREE_THEORIES_FRAMEWORK}

{stages_desc}

请生成一份完整的教案，包含：

1. 教学目标（3-4个具体目标，体现三种理论的融合）
2. 教学重点和难点
3. 教学准备
4. 学生能力分析

5. 教学过程（按以下融合环节组织，每个环节标注融合了哪些理论要素）：

   环节一：导入与情境创设
   （融合5E-引入 + BOPPPS-导入 + PBL-问题情境）
   
   环节二：目标确定与前测
   （融合BOPPPS-目标 + BOPPPS-前测）
   
   环节三：探究与任务设计
   （融合5E-探索 + PBL-任务设计）
   
   环节四：参与式学习与实施
   （融合BOPPPS-参与式学习 + PBL-实施过程）
   
   环节五：解释与成果展示
   （融合5E-解释 + PBL-成果展示）
   
   环节六：拓展应用
   （融合5E-拓展 + PBL深化）
   
   环节七：评价与反思
   （融合5E-评价 + BOPPPS-后测 + PBL-反思评价）
   
   环节八：总结
   （融合BOPPPS-总结 + 整体回顾）

6. 板书设计
7. 作业布置
8. 教学评价（体现三种理论的评价理念）

每个环节包含具体的教学步骤、时间分配、教学活动设计。
适合{lesson.grade_level}学生，学科: {lesson.subject}。
确保教案结构完整，时间分配合理。
不使用Markdown标记。直接输出纯文本教案内容。"""

        sys_msg = "你是资深教案编写专家，精通5E教学模型、BOPPPS教学模型和PBL项目式学习三种教学理论。请生成一份融合三种理论的完整标准教案文档，不要使用Markdown格式，直接输出纯文本。"
        if is_macau:
            sys_msg = "你是資深教案編寫專家，精通5E教學模型、BOPPPS教學模型和PBL項目式學習三種教學理論，熟悉澳門地區教育政策和教青局基本學力要求。請用繁體中文生成融合三種理論的完整教案，不使用Markdown格式。"

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
    ) -> str:
        await _emit("stream_start", {
            "lesson_id": lesson.id, "stage": 0,
            "agent_role": "教案编写专家", "phase": "full_optimized",
        }, room)

        is_macau = _is_macau_or_hk(getattr(lesson, 'region', '') or '')

        per_stage_content = ""
        for model in ALL_MODELS:
            per_stage_content += f"\n【{model['name']}】\n"
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
            prompt = f"""你是教研組主持人，現在需要將初始教案和教研老師們的改進建議融合，生成一份優化後的新教案。
本教案融合了5E教學模型、BOPPPS教學模型、PBL項目式學習三種教學理論。

{THREE_THEORIES_FRAMEWORK}

{MACAU_LESSON_REQUIREMENTS}

【初始教案】（必須完整保留結構並遵循澳門教案要求）：
{full_draft[:4000]}

【各環節教研專家優化後的內容】：
{per_stage_content}

{context}{avoid_note}

【融合要求】：
1. 保留初始教案的完整結構和主要內容，格式必須與澳門地區標準教案格式完全一致
2. 將各環節專家的優化意見逐條完整融入到對應章節
3. 在各教學環節標註融合了哪些理論要素，如：【5E-引入+BOPPPS-導入+PBL-問題情境】
4. 融合後內容比原教案更詳細（增長30-50%）
5. 改進後的內容更科學、更符合三種教學理論的融合要求
6. 必須包含澳門教案的所有必需結構（課題名稱、班級、教學目標三維劃分、學生能力分析、教學內容分析、教學流程表格等）
7. 語言流暢自然，使用繁體中文
8. 不使用Markdown標記，直接輸出純文本
9. 教學流程必須使用表格形式（目標代號、活動流程、時間、教學資源、評量）

現在開始生成優化教案（必須包含所有必需內容結構和三種理論融合標註）："""
            sys_msg = "你是教研組主持人，精通5E教學模型、BOPPPS教學模型和PBL項目式學習，熟悉澳門教育政策。請用繁體中文輸出，不使用Markdown格式。"
        else:
            prompt = f"""你是教研组主持人，现在需要基于初始教案和各环节教研专家的优化意见，生成一份融合优化后的完整教案。
本教案融合了5E教学模型、BOPPPS教学模型、PBL项目式学习三种教学理论。

{THREE_THEORIES_FRAMEWORK}

【初始教案】：
{full_draft[:4000]}

【各环节教研专家优化后的内容】：
{per_stage_content}

{context}{avoid_note}

【优化要求】：
1. 保留初始教案的完整结构和主要内容
2. 将各环节专家的优化内容逐条深度融入对应章节
3. 在各教学环节标注融合了哪些理论要素，如：【5E-引入+BOPPPS-导入+PBL-问题情境】
4. 体现三种理论的有机融合（不是分开使用，而是每个环节都体现多种理论）
5. 融合后的教案更详细、更科学、更可操作
6. 语言流畅自然，不使用Markdown标记
7. 输出完整的教案文档

现在开始生成优化教案（包含三种理论融合标注）："""
            sys_msg = "你是教研讨论主持人，精通5E教学模型、BOPPPS教学模型和PBL项目式学习。请整合优化内容生成完整教案文档，不要使用Markdown格式。"

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
    ) -> str:
        await _emit("stream_start", {
            "lesson_id": lesson.id, "stage": stage_num,
            "agent_role": "教案编写专家", "phase": "draft",
        }, room)

        is_macau = _is_macau_or_hk(getattr(lesson, 'region', '') or '')
        avoid_note = ""
        if lesson.avoid_issues:
            avoid_note = f"\n- 避免以下问题: {lesson.avoid_issues}"

        prompt = f"""请为教案中的"{stage_name}"环节撰写初步教案草稿。
该环节属于对应教学理论中的一个具体阶段。

{context}

{THREE_THEORIES_FRAMEWORK}

{'澳门地区要求：' + MACAU_LESSON_REQUIREMENTS if is_macau else ''}

要求:
- 包含具体教学步骤、时间分配、教学活动
- 标注该环节融合了哪些理论要素
- 适合{lesson.grade_level}学生，学科: {lesson.subject}{avoid_note}
- {'使用繁体中文，遵循澳门教案要求' if is_macau else '语言精炼专业'}
- 不使用任何Markdown标记，直接输出纯文本"""

        sys_msg = f"你是资深教案编写专家，精通5E教学模型、BOPPPS教学模型和PBL项目式学习三种教学理论。请直接输出纯文本，不要使用Markdown格式。"

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
    ) -> List[Dict]:
        tasks = []
        for agent in AGENT_ROLES:
            tasks.append(self._agent_analyze_stream(
                lesson, stage_name, agent, room, stage_num,
                context, draft,
            ))
        results = await asyncio.gather(*tasks, return_exceptions=True)

        opinions = []
        for i, result in enumerate(results):
            agent = AGENT_ROLES[i]
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

        prompt = f"""你是一位{agent_specialty}，{agent_theories}。
请从{agent_focus}角度，结合5E教学模型、BOPPPS教学模型和PBL项目式学习三种教学理论，分析以下教案环节并提供改进建议。

当前教学环节: {stage_name}

教案内容：
{draft[:2500]}

请严格按照以下格式输出（简洁明确）：

关键发现：[从{agent_specialty}角度，结合三种教学理论发现的问题或亮点，50-80字]

主要建议：[具体可操作的改进建议，要体现三种教学理论的融合应用，60-100字]

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

        tasks = [_single_expert_vote(agent) for agent in AGENT_ROLES]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        vote_results = []
        for i, r in enumerate(results):
            if isinstance(r, dict):
                vote_results.append(r)
            else:
                agent_role = AGENT_ROLES[i]["role"] if i < len(AGENT_ROLES) else "unknown"
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
    ) -> str:
        await _emit("stream_start", {
            "lesson_id": lesson.id, "stage": stage_num,
            "agent_role": "教案编写专家", "phase": "finalize",
        }, room)

        is_macau = _is_macau_or_hk(getattr(lesson, 'region', '') or '')
        avoid_note = ""
        if lesson.avoid_issues:
            avoid_note = f"\n- 避免以下问题: {lesson.avoid_issues}"

        prompt = f"""基于初步教案草稿和被采纳的专家改进意见，生成"{stage_name}"环节的最终优化教案。
该环节融合了5E教学模型、BOPPPS教学模型和PBL项目式学习三种教学理论。

--- 初步草稿 ---
{draft[:1500]}
--- 草稿结束 ---

--- 被采纳的专家改进意见 ---
{accepted_opinion[:1500]}
--- 意见结束 ---

融合要求:
1. 在草稿基础上将专家意见逐条深度融入教案正文
2. 不能只追加，要自然融入
3. 标注该环节融合了哪些理论要素（5E/BOPPPS/PBL）
4. 融合后内容比原草稿更详细（增长30-50%）
5. 包含具体教学步骤
6. 适合{lesson.grade_level}学生，学科: {lesson.subject}{avoid_note}
7. {'使用繁体中文，遵循澳门教案格式要求，确保包含目标代号、时间、教学资源、评量等要素' if is_macau else '语言精炼专业'}
8. 不使用任何Markdown标记，直接输出纯文本"""

        sys_msg = "你是资深教案编写专家，精通5E教学模型、BOPPPS教学模型和PBL项目式学习三种教学理论。请直接输出纯文本，不要使用Markdown格式。"

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
                    "progress": 5, "stage": "started", "message": "正在重新生成初步教案...",
                }, room)

                full_draft = await self._generate_full_draft_stream(lesson, room, context, session)

                discussion_stages = _build_all_discussion_stages()
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
                    "title": lesson.title, "subject": lesson.subject,
                    "grade_level": lesson.grade_level, "topic": lesson.topic,
                    "student_type": lesson.student_type,
                    "teaching_models": ["5E", "BOPPPS", "PBL"],
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

                    opinions = await self._stage1_analysis_stream(
                        session, lesson, stage_label, stage_num, room, context, full_draft[:3000],
                    )
                    expert_votes = await self._stage2_expert_votes(
                        session, lesson, stage_label, stage_num, opinions, room,
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
                        lesson, stage_label, stage_num, full_draft[:2000], best["opinion"], room, context,
                    )
                    all_final_stages[stage_key]["content"] = final_content
                    all_final_stages[stage_key]["expert"] = best["agent_role"]
                    lesson.final_content = {**lesson.final_content, "stages": all_final_stages}
                    await session.commit()

                    await _emit("progress_update", {
                        "lesson_id": lesson_id,
                        "progress": 45 + int((stage_num / total_discussion) * 50),
                        "stage": "section_done", "section": stage_label,
                        "section_key": stage_key, "section_index": idx,
                        "content_preview": final_content[:300],
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
            discussion_stages = _build_all_discussion_stages()
            stage_num = next(
                (ds["global_idx"] + 1 for ds in discussion_stages if ds["key"] == stage_key),
                1,
            )
            room = f"lesson_{lesson_id}"
            full_draft = (lesson.final_content or {}).get("full_draft", "")

            if version == "draft":
                new_text = await self._generate_draft_stream(
                    lesson, stage_label, stage_num, room, context,
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
