"""
初始化教学模型数据
"""
import asyncio
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import async_session_maker
from app.models.teaching_model import TeachingModel

async def init_models():
    """初始化内置教学模型"""
    models = [
        {
            "id": str(uuid.uuid4()),
            "name": "5E教学模型",
            "name_en": "5E Instructional Model",
            "description": "经典的5E教学模型，包含参与(Engage)、探究(Explore)、解释(Explain)、拓展(Extend)、评价(Evaluate)五个阶段",
            "type": "builtin",
            "config": {
                "stages": [
                    {
                        "id": "engage",
                        "name": "参与阶段",
                        "name_en": "Engage",
                        "description": "引起学生兴趣，激发好奇心，评估前概念",
                        "prompt_template": "作为{agent_role}，请基于以下教学内容设计参与阶段的活动，要求能够引起学生兴趣并评估前概念：\n\n{content}\n\n请提供具体的教学活动设计。"
                    },
                    {
                        "id": "explore",
                        "name": "探究阶段",
                        "name_en": "Explore",
                        "description": "学生主动探索，教师引导观察",
                        "prompt_template": "作为{agent_role}，请基于以下教学内容设计探究阶段的活动，要求学生能够主动探索和发现：\n\n{content}\n\n请提供具体的探究活动设计。"
                    },
                    {
                        "id": "explain",
                        "name": "解释阶段",
                        "name_en": "Explain",
                        "description": "教师讲解概念，学生用自己的话解释",
                        "prompt_template": "作为{agent_role}，请基于以下教学内容设计解释阶段的教学，要求清晰讲解核心概念：\n\n{content}\n\n请提供具体的讲解设计。"
                    },
                    {
                        "id": "extend",
                        "name": "拓展阶段",
                        "name_en": "Extend",
                        "description": "应用新知识到新情境",
                        "prompt_template": "作为{agent_role}，请基于以下教学内容设计拓展阶段的活动，要求能够应用新知识：\n\n{content}\n\n请提供具体的拓展活动设计。"
                    },
                    {
                        "id": "evaluate",
                        "name": "评价阶段",
                        "name_en": "Evaluate",
                        "description": "评估学生学习成果",
                        "prompt_template": "作为{agent_role}，请基于以下教学内容设计评价阶段的活动，要求能够全面评估学习成果：\n\n{content}\n\n请提供具体的评价方案。"
                    }
                ],
                "agents": [
                    {"role": "课程设计专家", "expertise": "教学目标、课程结构"},
                    {"role": "学科专家", "expertise": "学科知识、内容准确性"},
                    {"role": "教学法专家", "expertise": "教学策略、学习活动"},
                    {"role": "评估专家", "expertise": "学习评估、反馈机制"},
                    {"role": "技术整合专家", "expertise": "技术工具、资源整合"}
                ],
                "discussion_rounds": 3,
                "vote_threshold": 0.6
            },
            "applicable_subjects": ["科学", "数学", "物理", "化学", "生物", "地理"],
            "applicable_grades": ["小学", "初中", "高中"]
        },
        {
            "id": str(uuid.uuid4()),
            "name": "BOPPPS教学模型",
            "name_en": "BOPPPS Model",
            "description": "包含导言(Bridge-in)、目标(Objective)、前测(Pre-assessment)、参与式学习(Participatory)、后测(Post-assessment)、总结(Summary)六个环节",
            "type": "builtin",
            "config": {
                "stages": [
                    {
                        "id": "bridge_in",
                        "name": "导言",
                        "name_en": "Bridge-in",
                        "description": "建立新旧知识联系，引入新课题",
                        "prompt_template": "作为{agent_role}，请基于以下教学内容设计导言环节，要求建立新旧知识的联系：\n\n{content}\n\n请提供具体的导言设计。"
                    },
                    {
                        "id": "objective",
                        "name": "学习目标",
                        "name_en": "Objective",
                        "description": "明确告知学生本节课的学习目标",
                        "prompt_template": "作为{agent_role}，请基于以下教学内容明确学习目标：\n\n{content}\n\n请提供具体可测量的学习目标。"
                    },
                    {
                        "id": "pre_assessment",
                        "name": "前测",
                        "name_en": "Pre-assessment",
                        "description": "评估学生现有知识水平",
                        "prompt_template": "作为{agent_role}，请基于以下教学内容设计前测活动：\n\n{content}\n\n请提供具体的前测方案。"
                    },
                    {
                        "id": "participatory",
                        "name": "参与式学习",
                        "name_en": "Participatory Learning",
                        "description": "学生主动参与的学习活动",
                        "prompt_template": "作为{agent_role}，请基于以下教学内容设计参与式学习活动：\n\n{content}\n\n请提供具体的学习活动设计。"
                    },
                    {
                        "id": "post_assessment",
                        "name": "后测",
                        "name_en": "Post-assessment",
                        "description": "检验学习效果",
                        "prompt_template": "作为{agent_role}，请基于以下教学内容设计后测活动：\n\n{content}\n\n请提供具体的后测方案。"
                    },
                    {
                        "id": "summary",
                        "name": "总结",
                        "name_en": "Summary",
                        "description": "总结本节课重点，布置作业",
                        "prompt_template": "作为{agent_role}，请基于以下教学内容设计总结环节：\n\n{content}\n\n请提供具体的总结和作业设计。"
                    }
                ],
                "agents": [
                    {"role": "课程设计专家", "expertise": "教学目标、课程结构"},
                    {"role": "学科专家", "expertise": "学科知识、内容准确性"},
                    {"role": "教学法专家", "expertise": "教学策略、学习活动"},
                    {"role": "评估专家", "expertise": "学习评估、反馈机制"},
                    {"role": "技术整合专家", "expertise": "技术工具、资源整合"}
                ],
                "discussion_rounds": 3,
                "vote_threshold": 0.6
            },
            "applicable_subjects": ["全学科"],
            "applicable_grades": ["大学", "职业教育"]
        },
        {
            "id": str(uuid.uuid4()),
            "name": "PBL项目式学习",
            "name_en": "Project-Based Learning",
            "description": "以项目为中心的学习模式，包含问题情境、任务设计、实施指导、成果展示、反思评价",
            "type": "builtin",
            "config": {
                "stages": [
                    {
                        "id": "problem_context",
                        "name": "问题情境",
                        "name_en": "Problem Context",
                        "description": "创设真实的问题情境",
                        "prompt_template": "作为{agent_role}，请基于以下教学内容创设真实的问题情境：\n\n{content}\n\n请提供具体的问题情境设计。"
                    },
                    {
                        "id": "task_design",
                        "name": "任务设计",
                        "name_en": "Task Design",
                        "description": "设计项目任务和评价标准",
                        "prompt_template": "作为{agent_role}，请基于以下教学内容设计项目任务：\n\n{content}\n\n请提供具体的任务和评价标准。"
                    },
                    {
                        "id": "implementation",
                        "name": "实施指导",
                        "name_en": "Implementation",
                        "description": "项目实施过程的指导和支持",
                        "prompt_template": "作为{agent_role}，请基于以下教学内容设计实施指导方案：\n\n{content}\n\n请提供具体的指导策略。"
                    },
                    {
                        "id": "presentation",
                        "name": "成果展示",
                        "name_en": "Presentation",
                        "description": "学生展示项目成果",
                        "prompt_template": "作为{agent_role}，请基于以下教学内容设计成果展示环节：\n\n{content}\n\n请提供具体的展示方案。"
                    },
                    {
                        "id": "reflection",
                        "name": "反思评价",
                        "name_en": "Reflection",
                        "description": "反思学习过程，评价学习成果",
                        "prompt_template": "作为{agent_role}，请基于以下教学内容设计反思评价环节：\n\n{content}\n\n请提供具体的反思和评价方案。"
                    }
                ],
                "agents": [
                    {"role": "课程设计专家", "expertise": "教学目标、课程结构"},
                    {"role": "学科专家", "expertise": "学科知识、内容准确性"},
                    {"role": "教学法专家", "expertise": "教学策略、学习活动"},
                    {"role": "评估专家", "expertise": "学习评估、反馈机制"},
                    {"role": "技术整合专家", "expertise": "技术工具、资源整合"}
                ],
                "discussion_rounds": 3,
                "vote_threshold": 0.6
            },
            "applicable_subjects": ["全学科"],
            "applicable_grades": ["初中", "高中", "大学"]
        }
    ]
    
    async with async_session_maker() as session:
        for model_data in models:
            model = TeachingModel(**model_data)
            session.add(model)
        
        await session.commit()
        print(f"✅ 成功初始化 {len(models)} 个教学模型")

if __name__ == "__main__":
    asyncio.run(init_models())

