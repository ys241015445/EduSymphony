"""
一次性种子脚本：在 public.users 中创建/更新 hb01–hb15 普通账号。

权限与 dgsyz 相同：新建教案全流程 + 下载（can_export、can_next_lesson=true）；
课程工具/模板/大学/系列/珠科等模块保持关闭。
密码与用户名相同，使用 get_password_hash 写入 password_hash。

用法（在 backend 目录）：
    .\\venv\\Scripts\\python.exe scripts\\seed_hb_users.py
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.security import get_password_hash
from app.models.user import User, UserRole

QUOTA = 9999
USER_COUNT = 15


def _target_flags() -> dict:
    return {
        "access_level": "full",
        "role": UserRole.SCHOOL.value,
        "quota_remaining": QUOTA,
        "can_export": True,
        "can_course_tools": False,
        "can_template_fill": False,
        "can_university": False,
        "can_series": False,
        "can_next_lesson": True,
        "can_semester_helper": False,
    }


def _apply_flags(user: User, password: str) -> None:
    flags = _target_flags()
    user.password_hash = get_password_hash(password)
    user.access_level = flags["access_level"]
    user.role = flags["role"]
    user.quota_remaining = flags["quota_remaining"]
    user.can_export = flags["can_export"]
    user.can_course_tools = flags["can_course_tools"]
    user.can_template_fill = flags["can_template_fill"]
    user.can_university = flags["can_university"]
    user.can_series = flags["can_series"]
    user.can_next_lesson = flags["can_next_lesson"]
    user.can_semester_helper = flags["can_semester_helper"]


async def main() -> None:
    created = 0
    updated = 0

    async with async_session_maker() as session:
        for i in range(1, USER_COUNT + 1):
            username = f"hb{i:02d}"
            password = username
            email = f"{username}@edu.local"

            result = await session.execute(
                select(User).where(User.username == username)
            )
            user = result.scalar_one_or_none()

            if user:
                _apply_flags(user, password)
                updated += 1
                action = "updated"
            else:
                user = User(
                    id=str(uuid.uuid4()),
                    username=username,
                    email=email,
                )
                _apply_flags(user, password)
                session.add(user)
                created += 1
                action = "created"

            print(
                f"  [{action}] {username}  "
                f"can_export={user.can_export}  can_next_lesson={user.can_next_lesson}  "
                f"quota={user.quota_remaining}"
            )

        await session.commit()

    print(f"\nDone: {created} created, {updated} updated (total {USER_COUNT}).")


if __name__ == "__main__":
    asyncio.run(main())
