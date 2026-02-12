"""
RAG检索服务
基于Chroma向量数据库的检索增强生成
"""
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
from loguru import logger

from app.core.config import settings as app_settings

class RAGService:
    """RAG检索服务类"""
    
    def __init__(self):
        # 初始化Chroma客户端
        try:
            self.client = chromadb.HttpClient(
                host=app_settings.CHROMA_HOST,
                port=app_settings.CHROMA_PORT,
                settings=Settings(anonymized_telemetry=False)
            )
            
            # 获取或创建集合
            self.collection = self.client.get_or_create_collection(
                name="educational_references",
                metadata={"description": "教育参考资料库"}
            )
            
            logger.info("✅ Chroma向量库连接成功")
        except Exception as e:
            logger.error(f"❌ Chroma向量库连接失败: {str(e)}")
            self.client = None
            self.collection = None
    
    async def add_reference(
        self,
        doc_id: str,
        content: str,
        metadata: Dict
    ):
        """
        添加参考资料到向量库
        
        Args:
            doc_id: 文档ID
            content: 文档内容
            metadata: 元数据（包含type, subject, region等）
        """
        if not self.collection:
            logger.warning("向量库未初始化")
            return
        
        try:
            self.collection.add(
                documents=[content],
                metadatas=[metadata],
                ids=[doc_id]
            )
            logger.info(f"✅ 添加参考资料: {doc_id}")
        except Exception as e:
            logger.error(f"❌ 添加参考资料失败: {str(e)}")
    
    async def search_references(
        self,
        query: str,
        subject: Optional[str] = None,
        region: Optional[str] = None,
        ref_type: Optional[str] = None,
        n_results: int = 5
    ) -> List[Dict]:
        """
        检索相关参考资料
        
        Args:
            query: 查询文本
            subject: 学科过滤
            region: 地区过滤
            ref_type: 类型过滤（theory/standard/case）
            n_results: 返回结果数
        
        Returns:
            检索到的参考资料列表
        """
        if not self.collection:
            logger.warning("向量库未初始化，返回空结果")
            return []
        
        try:
            # 构建where条件
            where = {}
            if subject:
                where["subject"] = subject
            if region:
                where["region"] = region
            if ref_type:
                where["type"] = ref_type
            
            # 执行检索
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where if where else None
            )
            
            # 格式化结果
            references = []
            if results and results['documents']:
                for i, doc in enumerate(results['documents'][0]):
                    ref = {
                        "id": results['ids'][0][i],
                        "content": doc,
                        "metadata": results['metadatas'][0][i],
                        "distance": results['distances'][0][i] if 'distances' in results else None
                    }
                    references.append(ref)
            
            logger.info(f"✅ 检索到 {len(references)} 条参考资料")
            return references
            
        except Exception as e:
            logger.error(f"❌ 检索失败: {str(e)}")
            return []
    
    async def enhance_prompt_with_rag(
        self,
        prompt: str,
        subject: str,
        region: str,
        n_results: int = 3
    ) -> str:
        """
        使用RAG增强提示词
        
        Args:
            prompt: 原始提示词
            subject: 学科
            region: 地区
            n_results: 检索结果数
        
        Returns:
            增强后的提示词
        """
        # 检索相关资料
        references = await self.search_references(
            query=prompt,
            subject=subject,
            region=region,
            n_results=n_results
        )
        
        if not references:
            return prompt
        
        # 构建增强提示词
        enhanced_prompt = f"{prompt}\n\n**参考资料**：\n"
        
        for i, ref in enumerate(references):
            metadata = ref['metadata']
            ref_type_map = {
                "theory": "教学理论",
                "standard": "课程标准",
                "case": "优秀案例"
            }
            ref_type_name = ref_type_map.get(metadata.get('type', ''), '参考')
            
            enhanced_prompt += f"\n{i+1}. [{ref_type_name}] {metadata.get('title', '无标题')}\n"
            enhanced_prompt += f"   {ref['content'][:200]}...\n"
        
        enhanced_prompt += "\n请结合以上参考资料，提供更专业、更符合实际的教学设计。"
        
        return enhanced_prompt
    
    async def batch_add_references(self, references: List[Dict]):
        """
        批量添加参考资料
        
        Args:
            references: 参考资料列表，每项包含id, content, metadata
        """
        if not self.collection:
            logger.warning("向量库未初始化")
            return
        
        try:
            ids = [ref['id'] for ref in references]
            documents = [ref['content'] for ref in references]
            metadatas = [ref['metadata'] for ref in references]
            
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            
            logger.info(f"✅ 批量添加 {len(references)} 条参考资料")
        except Exception as e:
            logger.error(f"❌ 批量添加失败: {str(e)}")
    
    async def delete_reference(self, doc_id: str):
        """删除参考资料"""
        if not self.collection:
            return
        
        try:
            self.collection.delete(ids=[doc_id])
            logger.info(f"✅ 删除参考资料: {doc_id}")
        except Exception as e:
            logger.error(f"❌ 删除失败: {str(e)}")
    
    async def get_collection_stats(self) -> Dict:
        """获取向量库统计信息"""
        if not self.collection:
            return {"total_documents": 0}
        
        try:
            count = self.collection.count()
            return {
                "total_documents": count,
                "collection_name": self.collection.name
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {str(e)}")
            return {"total_documents": 0, "error": str(e)}

