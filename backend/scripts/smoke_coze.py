"""Smoke test: 确认 Coze PAT + bot_id 能成功提交 /v3/chat。

跑法：  backend>  .\venv\Scripts\python.exe scripts\smoke_coze.py
预期：  看到  [coze] chat submitted chat_id=xxxx… conv=xxxx…
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.services.coze_ppt_service import _coze_base, _coze_headers, _submit_chat  # noqa: E402


async def main() -> int:
    if not (settings.COZE_API_KEY and settings.COZE_BOT_ID):
        print("[smoke] COZE_API_KEY / COZE_BOT_ID 未配置，跳过。")
        return 1
    print(f"[smoke] base={_coze_base()}  bot_id={settings.COZE_BOT_ID}")
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=True) as client:
        ids = await _submit_chat(
            client, user_id="smoke-test",
            user_msg="你好，请简短自我介绍。（这是连通性测试，不需要生成 PPT）",
        )
        if not ids:
            print("[smoke] submit FAILED — 检查 PAT 是否有 chat/Bot 权限、bot_id 是否正确、base_url 是否为 api.coze.cn")
            return 2
        chat_id, conv_id = ids
        print(f"[smoke] OK  chat_id={chat_id}  conversation_id={conv_id}")
        # 清理：尝试取消，免得白烧额度
        try:
            cancel_url = f"{_coze_base()}/v3/chat/cancel"
            await client.post(cancel_url, json={"chat_id": chat_id, "conversation_id": conv_id}, headers=_coze_headers())
            print("[smoke] canceled.")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
