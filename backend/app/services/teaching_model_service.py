"""
教学模型服务
处理教学模型的加载和管理
"""
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.teaching_model import TeachingModel

class TeachingModelService:
    """教学模型服务类"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_model_by_id(self, model_id: str) -> Optional[TeachingModel]:
        """根据ID获取教学模型"""
        result = await self.db.execute(
            select(TeachingModel).where(TeachingModel.id == model_id)
        )
        return result.scalar_one_or_none()
    
    async def get_all_active_models(self) -> List[TeachingModel]:
        """获取所有激活的教学模型"""
        result = await self.db.execute(
            select(TeachingModel)
            .where(TeachingModel.is_active == True)
            .order_by(TeachingModel.usage_count.desc())
        )
        return list(result.scalars().all())
    
    async def get_models_by_subject(
        self,
        subject: str,
        grade_level: Optional[str] = None
    ) -> List[TeachingModel]:
        """根据学科和学段获取适用的教学模型"""
        query = select(TeachingModel).where(TeachingModel.is_active == True)
        
        result = await self.db.execute(query)
        models = list(result.scalars().all())
        
        # 过滤适用的模型
        filtered_models = []
        for model in models:
            # 检查学科
            if model.applicable_subjects:
                if "全学科" in model.applicable_subjects or subject in model.applicable_subjects:
                    # 检查学段
                    if grade_level and model.applicable_grades:
                        if grade_level in model.applicable_grades:
                            filtered_models.append(model)
                    else:
                        filtered_models.append(model)
        
        return filtered_models
    
    def get_stage_config(self, model: TeachingModel, stage_id: str) -> Optional[Dict]:
        """获取指定阶段的配置"""
        stages = model.config.get("stages", [])
        for stage in stages:
            if stage.get("id") == stage_id:
                return stage
        return None
    
    def get_agents_config(self, model: TeachingModel) -> List[Dict]:
        """获取模型的智能体配置"""
        return model.config.get("agents", [])
    
    def get_discussion_config(self, model: TeachingModel) -> Dict:
        """获取讨论配置"""
        return {
            "rounds": model.config.get("discussion_rounds", 3),
            "vote_threshold": model.config.get("vote_threshold", 0.6)
        }
    
    async def increment_usage_count(self, model_id: str):
        """增加模型使用计数"""
        result = await self.db.execute(
            select(TeachingModel).where(TeachingModel.id == model_id)
        )
        model = result.scalar_one_or_none()
        if model:
            model.usage_count += 1
            await self.db.commit()
    
    def format_prompt(
        self,
        template: str,
        agent_role: str,
        content: str,
        **kwargs
    ) -> str:
        """格式化提示词模板"""
        return template.format(
            agent_role=agent_role,
            content=content,
            **kwargs
        )

