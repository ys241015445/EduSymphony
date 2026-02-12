"""
教案生成任务处理器
处理异步的教案生成任务
"""
import asyncio
import uuid
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.core.database import async_session_maker
from app.models.lesson import LessonPlan, Discussion, LessonStatus
from app.models.teaching_model import TeachingModel
from app.services.teaching_model_service import TeachingModelService
from app.services.ai_service import AIService
from app.services.document_parser import DocumentParserService
from app.services.rag_service import RAGService


class LessonTaskHandler:
    """教案任务处理器"""
    
    def __init__(self):
        self.ai_service = AIService()
        self.doc_parser = DocumentParserService()
        self.rag_service = RAGService()
    
    async def process_lesson(self, lesson_id: str):
        """
        处理教案生成任务
        
        Args:
            lesson_id: 教案ID
        """
        async with async_session_maker() as session:
            try:
                # 获取教案
                lesson = await self._get_lesson(session, lesson_id)
                if not lesson:
                    logger.error(f"教案不存在: {lesson_id}")
                    return
                
                # 更新状态为处理中
                lesson.status = LessonStatus.PROCESSING
                lesson.started_at = datetime.utcnow()
                await session.commit()
                
                # 获取教学模型
                model_service = TeachingModelService(session)
                teaching_model = await model_service.get_model_by_id(lesson.teaching_model_id)
                
                if not teaching_model:
                    raise Exception("教学模型不存在")
                
                # 执行三阶段协作
                await self._execute_three_stage_collaboration(
                    session, lesson, teaching_model
                )
                
                # 更新状态为完成
                lesson.status = LessonStatus.COMPLETED
                lesson.completed_at = datetime.utcnow()
                lesson.progress = 100
                await session.commit()
                
                logger.info(f"✅ 教案生成完成: {lesson_id}")
                
            except Exception as e:
                logger.error(f"❌ 教案生成失败 {lesson_id}: {str(e)}")
                
                # 更新失败状态
                lesson = await self._get_lesson(session, lesson_id)
                if lesson:
                    lesson.status = LessonStatus.FAILED
                    lesson.error_message = str(e)
                    await session.commit()
    
    async def _get_lesson(self, session: AsyncSession, lesson_id: str) -> Optional[LessonPlan]:
        """获取教案"""
        result = await session.execute(
            select(LessonPlan).where(LessonPlan.id == lesson_id)
        )
        return result.scalar_one_or_none()
    
    async def _execute_three_stage_collaboration(
        self,
        session: AsyncSession,
        lesson: LessonPlan,
        teaching_model: TeachingModel
    ):
        """
        执行三阶段协作流程
        
        Stage 1: 5位专家独立分析
        Stage 2: 主持人引导讨论投票
        Stage 3: 生成最终教学材料
        """
        model_service = TeachingModelService(session)
        
        # 获取模型配置
        stages = teaching_model.config.get("stages", [])
        agents = teaching_model.config.get("agents", [])
        discussion_config = model_service.get_discussion_config(teaching_model)
        
        # Stage 1: 独立分析
        logger.info(f"Stage 1: 5位专家独立分析 - {lesson.id}")
        lesson.current_stage = 1
        lesson.progress = 10
        await session.commit()
        
        stage1_results = await self._stage1_independent_analysis(
            session, lesson, teaching_model, agents, stages
        )
        
        # Stage 2: 讨论与投票
        logger.info(f"Stage 2: 主持人引导讨论 - {lesson.id}")
        lesson.current_stage = 2
        lesson.progress = 50
        await session.commit()
        
        stage2_results = await self._stage2_discussion_voting(
            session, lesson, teaching_model, agents, stages, stage1_results, discussion_config
        )
        
        # Stage 3: 生成教学材料
        logger.info(f"Stage 3: 生成教学材料 - {lesson.id}")
        lesson.current_stage = 3
        lesson.progress = 80
        await session.commit()
        
        final_content = await self._stage3_generate_materials(
            lesson, teaching_model, stages, stage2_results
        )
        
        # 保存最终内容
        lesson.final_content = final_content
        lesson.progress = 100
        await session.commit()
    
    async def _stage1_independent_analysis(
        self,
        session: AsyncSession,
        lesson: LessonPlan,
        teaching_model: TeachingModel,
        agents: List[Dict],
        stages: List[Dict]
    ) -> Dict:
        """
        Stage 1: 5位专家独立分析
        每位专家针对每个教学阶段提供建议
        """
        results = {}
        
        for stage in stages:
            stage_id = stage["id"]
            stage_name = stage["name"]
            
            logger.info(f"  分析阶段: {stage_name}")
            
            # 并行请求5位专家的意见
            prompts = []
            for agent in agents:
                base_prompt = stage["prompt_template"].format(
                    agent_role=agent["role"],
                    content=lesson.parsed_content or lesson.source_content
                )
                
                # 使用RAG增强提示词
                enhanced_prompt = await self.rag_service.enhance_prompt_with_rag(
                    base_prompt,
                    subject=lesson.subject,
                    region=lesson.region,
                    n_results=2
                )
                
                prompts.append(enhanced_prompt)
            
            # 批量生成
            responses = await self.ai_service.batch_generate(
                prompts,
                model="gpt-4",
                temperature=0.7,
                max_tokens=1500
            )
            
            # 保存专家意见
            stage_opinions = []
            for i, (agent, response) in enumerate(zip(agents, responses)):
                opinion = {
                    "agent_role": agent["role"],
                    "expertise": agent["expertise"],
                    "opinion": response
                }
                stage_opinions.append(opinion)
                
                # 保存到数据库
                discussion = Discussion(
                    id=str(uuid.uuid4()),
                    lesson_plan_id=lesson.id,
                    stage=1,
                    round=1,
                    topic=stage_name,
                    agent_role=agent["role"],
                    opinion=response,
                    is_accepted=False
                )
                session.add(discussion)
            
            results[stage_id] = stage_opinions
        
        await session.commit()
        return results
    
    async def _stage2_discussion_voting(
        self,
        session: AsyncSession,
        lesson: LessonPlan,
        teaching_model: TeachingModel,
        agents: List[Dict],
        stages: List[Dict],
        stage1_results: Dict,
        discussion_config: Dict
    ) -> Dict:
        """
        Stage 2: 主持人引导讨论和投票
        对每个阶段的方案进行讨论和投票
        """
        results = {}
        rounds = discussion_config["rounds"]
        vote_threshold = discussion_config["vote_threshold"]
        
        for stage in stages:
            stage_id = stage["id"]
            stage_name = stage["name"]
            
            logger.info(f"  讨论阶段: {stage_name}")
            
            opinions = stage1_results[stage_id]
            
            # 多轮讨论
            for round_num in range(1, rounds + 1):
                logger.info(f"    第 {round_num} 轮讨论")
                
                # 对每个意见进行投票
                for opinion in opinions:
                    # 生成投票请求
                    vote_prompt = self._create_vote_prompt(
                        stage_name,
                        opinion,
                        opinions,
                        agents
                    )
                    
                    vote_response = await self.ai_service.generate(
                        vote_prompt,
                        model="gpt-4",
                        temperature=0.3,
                        max_tokens=500
                    )
                    
                    # 解析投票结果（简化版，实际应更复杂）
                    votes = self._parse_votes(vote_response, len(agents))
                    opinion["votes"] = votes
                    opinion["pass_rate"] = votes["agree"] / len(agents)
                
                # 检查是否有方案通过
                passed_opinions = [
                    op for op in opinions
                    if op.get("pass_rate", 0) >= vote_threshold
                ]
                
                if passed_opinions:
                    # 选择得票最高的方案
                    best_opinion = max(passed_opinions, key=lambda x: x["pass_rate"])
                    
                    # 保存通过的意见
                    discussion = Discussion(
                        id=str(uuid.uuid4()),
                        lesson_plan_id=lesson.id,
                        stage=2,
                        round=round_num,
                        topic=stage_name,
                        agent_role=best_opinion["agent_role"],
                        opinion=best_opinion["opinion"],
                        votes=best_opinion["votes"],
                        pass_rate=best_opinion["pass_rate"],
                        is_accepted=True
                    )
                    session.add(discussion)
                    
                    results[stage_id] = best_opinion
                    break
            
            # 如果所有轮次都没通过，使用得票最高的
            if stage_id not in results:
                best_opinion = max(opinions, key=lambda x: x.get("pass_rate", 0))
                results[stage_id] = best_opinion
        
        await session.commit()
        return results
    
    async def _stage3_generate_materials(
        self,
        lesson: LessonPlan,
        teaching_model: TeachingModel,
        stages: List[Dict],
        stage2_results: Dict
    ) -> Dict:
        """
        Stage 3: 生成最终教学材料
        根据通过的方案生成完整的教案
        """
        final_content = {
            "title": lesson.title,
            "subject": lesson.subject,
            "grade_level": lesson.grade_level,
            "teaching_model": teaching_model.name,
            "stages": {}
        }
        
        for stage in stages:
            stage_id = stage["id"]
            stage_name = stage["name"]
            
            if stage_id in stage2_results:
                final_content["stages"][stage_id] = {
                    "name": stage_name,
                    "content": stage2_results[stage_id]["opinion"],
                    "expert": stage2_results[stage_id]["agent_role"]
                }
        
        return final_content
    
    def _create_vote_prompt(
        self,
        stage_name: str,
        opinion: Dict,
        all_opinions: List[Dict],
        agents: List[Dict]
    ) -> str:
        """创建投票提示词"""
        prompt = f"""作为教学专家团队，请对以下{stage_name}的教学方案进行投票评估：

**当前方案**（由{opinion['agent_role']}提出）：
{opinion['opinion']}

**其他专家的方案**：
"""
        for i, other_op in enumerate(all_opinions):
            if other_op != opinion:
                prompt += f"\n{i+1}. {other_op['agent_role']}: {other_op['opinion'][:200]}...\n"
        
        prompt += """

请从以下5个专家角色的角度进行投票（同意/不同意）：
"""
        for agent in agents:
            prompt += f"- {agent['role']} ({agent['expertise']})\n"
        
        prompt += "\n请以JSON格式返回投票结果：{\"votes\": [{\"agent\": \"角色名\", \"vote\": \"agree/disagree\", \"reason\": \"理由\"}]}"
        
        return prompt
    
    def _parse_votes(self, vote_response: str, total_agents: int) -> Dict:
        """解析投票结果"""
        import json
        
        try:
            # 尝试提取JSON
            if "```json" in vote_response:
                json_str = vote_response.split("```json")[1].split("```")[0].strip()
            elif "{" in vote_response:
                json_str = vote_response[vote_response.find("{"):vote_response.rfind("}")+1]
            else:
                json_str = vote_response
            
            data = json.loads(json_str)
            votes_list = data.get("votes", [])
            
            agree_count = sum(1 for v in votes_list if v.get("vote") == "agree")
            
            return {
                "agree": agree_count,
                "disagree": len(votes_list) - agree_count,
                "details": votes_list
            }
        except:
            # 解析失败，假设大多数同意
            return {
                "agree": int(total_agents * 0.7),
                "disagree": int(total_agents * 0.3),
                "details": []
            }

