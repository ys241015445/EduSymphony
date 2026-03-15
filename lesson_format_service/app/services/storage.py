"""
教案数据存储服务（内存存储）
"""
from typing import Dict, List, Optional
from datetime import datetime
import uuid
from app.models import LessonPlan

class LessonPlanStorage:
    def __init__(self, max_items: int = 100):
        self.lesson_plans: Dict[str, LessonPlan] = {}
        self.conversions: Dict[str, dict] = {}  # 存储转换结果
        self.max_items = max_items
    
    def add_lesson_plan(self, lesson_plan: LessonPlan) -> str:
        """添加教案，返回ID"""
        lesson_id = str(uuid.uuid4())
        lesson_plan.id = lesson_id
        lesson_plan.created_at = datetime.now()
        
        # 如果超过最大数量，删除最旧的
        if len(self.lesson_plans) >= self.max_items:
            oldest_id = min(self.lesson_plans.keys(), 
                          key=lambda k: self.lesson_plans[k].created_at)
            del self.lesson_plans[oldest_id]
        
        self.lesson_plans[lesson_id] = lesson_plan
        return lesson_id
    
    def get_lesson_plan(self, lesson_id: str) -> Optional[LessonPlan]:
        """获取单个教案"""
        return self.lesson_plans.get(lesson_id)
    
    def get_all_lesson_plans(self) -> List[LessonPlan]:
        """获取所有教案"""
        return list(self.lesson_plans.values())
    
    def save_conversion(self, conversion_id: str, data: dict):
        """保存转换结果"""
        self.conversions[conversion_id] = data
    
    def get_conversion(self, conversion_id: str) -> Optional[dict]:
        """获取转换结果"""
        return self.conversions.get(conversion_id)

# 全局存储实例
storage = LessonPlanStorage()
