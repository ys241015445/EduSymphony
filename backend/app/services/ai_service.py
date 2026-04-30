import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, List, AsyncGenerator
from openai import AsyncOpenAI
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import settings
from loguru import logger


@dataclass
class AIProvider:
    name: str
    client: AsyncOpenAI
    model: str


class AIService:
    def __init__(self):
        self.providers: Dict[str, AIProvider] = {}
        self._init_providers()
        self.provider_order: List[str] = []
        self._build_order()

    def _init_providers(self):
        provider_configs = [
            ("qwen", settings.QWEN_API_KEY, settings.QWEN_BASE_URL, settings.QWEN_MODEL),
            ("kimi", settings.KIMI_API_KEY, settings.KIMI_BASE_URL, settings.KIMI_MODEL),
            ("doubao", settings.DOUBAO_API_KEY, settings.DOUBAO_BASE_URL, settings.DOUBAO_MODEL),
            ("deepseek", settings.DEEPSEEK_API_KEY, settings.DEEPSEEK_BASE_URL, settings.DEEPSEEK_MODEL),
            ("spark", settings.SPARK_API_KEY, settings.SPARK_BASE_URL, settings.SPARK_MODEL),
        ]

        if settings.OPENAI_API_KEY:
            provider_configs.append(
                ("openai", settings.OPENAI_API_KEY, settings.OPENAI_BASE_URL, "gpt-4o")
            )

        for name, api_key, base_url, model in provider_configs:
            if api_key and api_key not in ("", "your-qwen-api-key", "your-kimi-api-key",
                                            "your-doubao-api-key", "your-deepseek-api-key",
                                            "your-spark-api-key"):
                try:
                    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
                    self.providers[name] = AIProvider(name=name, client=client, model=model)
                    logger.info(f"AI provider initialized: {name} (model: {model})")
                except Exception as e:
                    logger.warning(f"Failed to init provider {name}: {e}")

    def _build_order(self):
        preferred = ["qwen", "kimi", "doubao", "deepseek", "spark", "openai"]
        self.provider_order = [p for p in preferred if p in self.providers]
        if not self.provider_order:
            logger.warning("No AI providers configured!")

    def get_available_providers(self) -> List[str]:
        return list(self.provider_order)

    def get_provider(self, name: str) -> Optional[AIProvider]:
        return self.providers.get(name)

    def assign_providers_to_agents(self, agent_count: int = 5) -> List[str]:
        """Assign different AI providers to agents in round-robin."""
        available = self.provider_order
        if not available:
            return ["none"] * agent_count
        return [available[i % len(available)] for i in range(agent_count)]

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError)),
    )
    async def generate(
        self,
        prompt: str,
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 4000,
        system_message: Optional[str] = None,
    ) -> str:
        if provider_name and provider_name in self.providers:
            provider = self.providers[provider_name]
            try:
                return await self._call(
                    provider.client, prompt,
                    model or provider.model,
                    temperature, max_tokens, system_message
                )
            except Exception as e:
                logger.warning(f"{provider_name} failed: {e}, trying fallback...")

        for fallback_name in self.provider_order:
            if fallback_name == provider_name:
                continue
            provider = self.providers[fallback_name]
            try:
                logger.info(f"Trying fallback: {fallback_name}")
                return await self._call(
                    provider.client, prompt,
                    provider.model,
                    temperature, max_tokens, system_message
                )
            except Exception as e:
                logger.warning(f"Fallback {fallback_name} also failed: {e}")
                continue

        raise Exception("所有AI模型均调用失败，请检查 .env 中的 API Key 配置")

    def _resolve_provider(self, provider_name: Optional[str] = None) -> AIProvider:
        if provider_name and provider_name in self.providers:
            return self.providers[provider_name]
        if self.provider_order:
            return self.providers[self.provider_order[0]]
        raise Exception("No AI providers available")

    async def generate_stream(
        self,
        prompt: str,
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 4000,
        system_message: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Yield text chunks as they arrive from the AI model."""
        tried_providers = []

        if provider_name and provider_name in self.providers:
            tried_providers.append(provider_name)
            try:
                async for chunk in self._call_stream(
                    self.providers[provider_name].client, prompt,
                    model or self.providers[provider_name].model,
                    temperature, max_tokens, system_message
                ):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"Stream {provider_name} failed: {e}, trying fallback...")

        for fallback_name in self.provider_order:
            if fallback_name in tried_providers:
                continue
            try:
                logger.info(f"Stream fallback: {fallback_name}")
                async for chunk in self._call_stream(
                    self.providers[fallback_name].client, prompt,
                    self.providers[fallback_name].model,
                    temperature, max_tokens, system_message
                ):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"Stream fallback {fallback_name} failed: {e}")
                continue

        raise Exception("所有AI模型流式调用均失败")

    async def _call_stream(
        self, client: AsyncOpenAI, prompt: str, model: str,
        temperature: float, max_tokens: int, system_message: Optional[str]
    ) -> AsyncGenerator[str, None]:
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _call(
        self, client: AsyncOpenAI, prompt: str, model: str,
        temperature: float, max_tokens: int, system_message: Optional[str]
    ) -> str:
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    # ──────────────────────────────────────────────────────────────
    # 文档修订（"我的文档" 模块用）— 优先 Qwen，回落其它 provider
    # ──────────────────────────────────────────────────────────────

    REVISE_DOC_SYSTEM = (
        "你是一名严谨细致的教学文档编辑助理。"
        "用户会给你一份 Markdown 教学文档与修改要求。"
        "请按要求修改全文，输出**完整的、可直接覆盖原文的 Markdown**。"
        "硬性约束：\n"
        "1) 保留原文整体结构（章节标题、列表、代码块、图片引用），除非用户明确要求增删；\n"
        "2) 不要输出修改说明、不要 markdown 代码块包裹整篇；\n"
        "3) 中文教学场景，语言保持自然通顺；\n"
        "4) 不要丢失内容，除非用户明确要求精简或删除。"
    )

    REVISE_PARA_SYSTEM = (
        "你是一名严谨细致的教学文档编辑助理。"
        "用户会给你一段 Markdown 文本和修改要求。"
        "请按要求修改这一段，**只输出修改后的段落本身**，不要任何解释、引号或代码块包裹。"
        "保持原段落的语义层级（如果是标题就仍是标题，是列表就仍是列表）。"
    )

    async def revise_document_stream(
        self,
        full_markdown: str,
        instruction: str,
        provider_name: Optional[str] = "qwen",
        temperature: float = 0.3,
        max_tokens: int = 8000,
    ) -> AsyncGenerator[str, None]:
        """整篇文档修订（流式）。"""
        prompt = (
            f"【用户的修改要求】\n{instruction.strip()}\n\n"
            f"【当前 Markdown 全文】\n{full_markdown}\n\n"
            f"请输出修改后的完整 Markdown："
        )
        async for chunk in self.generate_stream(
            prompt=prompt,
            provider_name=provider_name,
            temperature=temperature,
            max_tokens=max_tokens,
            system_message=self.REVISE_DOC_SYSTEM,
        ):
            yield chunk

    async def revise_paragraph_stream(
        self,
        paragraph: str,
        instruction: str,
        context_before: str = "",
        context_after: str = "",
        provider_name: Optional[str] = "qwen",
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> AsyncGenerator[str, None]:
        """段落级修订（流式）。可选传入前后上下文以保持连贯。"""
        ctx_before = context_before.strip()
        ctx_after = context_after.strip()
        ctx_block = ""
        if ctx_before:
            ctx_block += f"【上文（仅供参考，不要输出）】\n{ctx_before}\n\n"
        if ctx_after:
            ctx_block += f"【下文（仅供参考，不要输出）】\n{ctx_after}\n\n"

        prompt = (
            f"{ctx_block}"
            f"【需要修改的段落】\n{paragraph}\n\n"
            f"【用户的修改要求】\n{instruction.strip()}\n\n"
            f"请输出修改后的段落："
        )
        async for chunk in self.generate_stream(
            prompt=prompt,
            provider_name=provider_name,
            temperature=temperature,
            max_tokens=max_tokens,
            system_message=self.REVISE_PARA_SYSTEM,
        ):
            yield chunk
