"""
AI服务
集成多个AI模型提供商（OpenAI, Qwen等）
实现重试和降级机制
"""
import asyncio
from typing import Optional, List, Dict
from openai import AsyncOpenAI
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from app.core.config import settings
from loguru import logger

class AIService:
    """AI服务类"""
    
    def __init__(self):
        # OpenAI客户端
        self.openai_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL
        ) if settings.OPENAI_API_KEY else None
        
        # Qwen API配置
        self.qwen_api_key = settings.QWEN_API_KEY
        self.qwen_base_url = settings.QWEN_BASE_URL
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError))
    )
    async def generate(
        self,
        prompt: str,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        system_message: Optional[str] = None
    ) -> str:
        """
        生成AI响应（带重试机制）
        
        Args:
            prompt: 用户提示词
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数
            system_message: 系统消息
        
        Returns:
            AI生成的文本
        """
        try:
            # 优先使用OpenAI
            if self.openai_client and model.startswith("gpt"):
                return await self._call_openai(
                    prompt, model, temperature, max_tokens, system_message
                )
            
            # 降级到Qwen
            elif self.qwen_api_key:
                return await self._call_qwen(
                    prompt, temperature, max_tokens, system_message
                )
            
            else:
                raise Exception("未配置任何可用的AI模型")
                
        except Exception as e:
            logger.error(f"AI生成失败: {str(e)}")
            # 尝试降级
            if model.startswith("gpt") and self.qwen_api_key:
                logger.info("降级到Qwen模型")
                return await self._call_qwen(
                    prompt, temperature, max_tokens, system_message
                )
            raise
    
    async def _call_openai(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_message: Optional[str]
    ) -> str:
        """调用OpenAI API"""
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        response = await self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return response.choices[0].message.content
    
    async def _call_qwen(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        system_message: Optional[str]
    ) -> str:
        """调用通义千问API"""
        import dashscope
        from dashscope import Generation
        
        dashscope.api_key = self.qwen_api_key
        
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        response = Generation.call(
            model='qwen-max',
            messages=messages,
            result_format='message',
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            raise Exception(f"Qwen API错误: {response.message}")
    
    async def batch_generate(
        self,
        prompts: List[str],
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        system_message: Optional[str] = None
    ) -> List[str]:
        """
        批量生成AI响应
        
        Args:
            prompts: 提示词列表
            其他参数同generate方法
        
        Returns:
            AI生成的文本列表
        """
        tasks = [
            self.generate(prompt, model, temperature, max_tokens, system_message)
            for prompt in prompts
        ]
        
        return await asyncio.gather(*tasks)
    
    async def generate_with_context(
        self,
        prompt: str,
        context: str,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """
        带上下文的生成
        
        Args:
            prompt: 用户提示词
            context: 上下文信息
            其他参数同generate方法
        
        Returns:
            AI生成的文本
        """
        full_prompt = f"上下文信息：\n{context}\n\n任务：\n{prompt}"
        
        return await self.generate(
            full_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    async def structured_generate(
        self,
        prompt: str,
        schema: Dict,
        model: str = "gpt-4",
        temperature: float = 0.7
    ) -> Dict:
        """
        结构化生成（返回JSON）
        
        Args:
            prompt: 用户提示词
            schema: 期望的JSON结构说明
            其他参数同generate方法
        
        Returns:
            结构化的字典数据
        """
        import json
        
        system_message = f"你是一个专业的教学设计专家。请严格按照以下JSON结构返回结果：\n{json.dumps(schema, ensure_ascii=False, indent=2)}"
        
        response = await self.generate(
            prompt,
            model=model,
            temperature=temperature,
            max_tokens=3000,
            system_message=system_message
        )
        
        # 尝试解析JSON
        try:
            # 提取JSON（可能包含在markdown代码块中）
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response
            
            return json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning(f"JSON解析失败，返回原始文本: {response}")
            return {"raw_response": response}

