"""
初始化参考资料库
添加教学理论、课程标准、优秀案例等参考资料
"""
import asyncio
import uuid
from app.services.rag_service import RAGService

async def init_references():
    """初始化参考资料"""
    rag_service = RAGService()
    
    # 教学理论参考
    theory_references = [
        {
            "id": str(uuid.uuid4()),
            "content": """5E教学模型是由美国生物学课程研究(BSCS)开发的一种建构主义教学模式，包括五个阶段：
1. Engage（参与）：通过提问、演示或活动引起学生兴趣，评估学生已有知识。
2. Explore（探究）：学生通过实验、观察、讨论等主动探索概念。
3. Explain（解释）：学生用自己的语言解释发现，教师引入科学术语和概念。
4. Extend（拓展）：将新学概念应用到新情境中，深化理解。
5. Evaluate（评价）：评估学生对概念的理解程度和探究能力。

5E模型强调学生的主动学习和概念建构，特别适合科学教育。""",
            "metadata": {
                "type": "theory",
                "title": "5E教学模型理论基础",
                "subject": "科学",
                "region": "mainland"
            }
        },
        {
            "id": str(uuid.uuid4()),
            "content": """BOPPPS教学模型起源于加拿大，是一种高效的教学设计框架：
1. Bridge-in（导言）：建立新旧知识联系，激发学习动机。
2. Objective（目标）：明确具体可测量的学习目标。
3. Pre-assessment（前测）：了解学生起点，调整教学策略。
4. Participatory Learning（参与式学习）：通过互动活动促进深度学习。
5. Post-assessment（后测）：检验学习效果，提供及时反馈。
6. Summary（总结）：强化重点，布置延伸任务。

BOPPPS强调目标导向和持续评估，适用于各学科各学段。""",
            "metadata": {
                "type": "theory",
                "title": "BOPPPS教学模型详解",
                "subject": "全学科",
                "region": "mainland"
            }
        },
        {
            "id": str(uuid.uuid4()),
            "content": """项目式学习(PBL)是一种以学生为中心的教学方法，核心要素包括：
1. 真实问题情境：源于现实世界的复杂挑战。
2. 学生主导：学生自主规划、执行、监控项目进程。
3. 持续探究：通过提问、调研、实验等方式深入探索。
4. 协作学习：团队合作，发挥各自优势。
5. 成果展示：向真实受众展示项目成果。
6. 反思评价：批判性思考学习过程和结果。

PBL能培养学生的问题解决能力、创新思维和团队协作能力。""",
            "metadata": {
                "type": "theory",
                "title": "项目式学习(PBL)理论",
                "subject": "全学科",
                "region": "mainland"
            }
        }
    ]
    
    # 课程标准参考（大陆）
    standard_references = [
        {
            "id": str(uuid.uuid4()),
            "content": """《义务教育科学课程标准(2022年版)》核心理念：
1. 面向全体学生，注重科学素养培养。
2. 倡导探究式学习，强调亲身经历科学探究过程。
3. 体现科学本质，培养科学思维和创新精神。
4. 联系生产生活实际，增强学以致用意识。
5. 重视科学态度和责任，培育社会主义核心价值观。

课程内容包括物质科学、生命科学、地球与宇宙科学、技术与工程四个领域。""",
            "metadata": {
                "type": "standard",
                "title": "义务教育科学课程标准2022",
                "subject": "科学",
                "region": "mainland"
            }
        },
        {
            "id": str(uuid.uuid4()),
            "content": """《普通高中数学课程标准(2017年版2020年修订)》强调六大核心素养：
1. 数学抽象：从具体情境中抽象出数学概念和规则。
2. 逻辑推理：基于数学事实进行严密推理。
3. 数学建模：用数学语言描述和解决实际问题。
4. 直观想象：借助空间想象和几何直观理解数学。
5. 数学运算：掌握运算法则，实现准确计算。
6. 数据分析：收集、整理、分析数据，做出合理决策。

教学应注重素养导向，实施探究式、项目式学习。""",
            "metadata": {
                "type": "standard",
                "title": "普通高中数学课程标准",
                "subject": "数学",
                "region": "mainland"
            }
        }
    ]
    
    # 优秀案例参考
    case_references = [
        {
            "id": str(uuid.uuid4()),
            "content": """【5E案例】小学科学《光的传播》
- Engage：用手电筒在烟雾中展示光束，提问"光是怎么传播的？"
- Explore：学生分组实验，用激光笔、镜子、水等材料探索光的路径。
- Explain：学生描述观察结果，教师引入"光沿直线传播"概念。
- Extend：设计潜望镜，应用光的反射原理。
- Evaluate：绘制光路图，解释生活中的光现象（影子、日食等）。

亮点：动手实验比例高，概念从观察中自然生成。""",
            "metadata": {
                "type": "case",
                "title": "5E模型案例：光的传播",
                "subject": "科学",
                "grade_level": "小学",
                "region": "mainland"
            }
        },
        {
            "id": str(uuid.uuid4()),
            "content": """【PBL案例】高中生物《校园生态调查》
- 问题情境：学校计划改造校园绿化，需要了解现有生态状况。
- 任务：完成校园生物多样性调查报告，提出改造建议。
- 实施：划分区域调查，记录物种、测量环境参数、访谈师生需求。
- 成果：制作调查报告、物种图册、改造方案PPT，向校方汇报。
- 评价：同伴互评、教师评价、校方反馈相结合。

亮点：真实任务驱动，跨学科整合（生物、数学、美术、信息技术）。""",
            "metadata": {
                "type": "case",
                "title": "PBL案例：校园生态调查",
                "subject": "生物",
                "grade_level": "高中",
                "region": "mainland"
            }
        }
    ]
    
    # 合并所有参考资料
    all_references = theory_references + standard_references + case_references
    
    # 批量添加
    await rag_service.batch_add_references(all_references)
    
    # 显示统计
    stats = await rag_service.get_collection_stats()
    print(f"✅ 成功初始化 {len(all_references)} 条参考资料")
    print(f"📊 向量库总文档数: {stats['total_documents']}")

if __name__ == "__main__":
    asyncio.run(init_references())

