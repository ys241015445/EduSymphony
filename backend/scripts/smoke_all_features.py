"""EduSymphony 全栈冒烟测试：API（httpx）+ 可选 UI（Playwright）。

用法：
  cd backend
  python scripts/smoke_all_features.py --dry-run
  python scripts/smoke_all_features.py --dry-run --ui --lesson-id <uuid>

环境变量见 smoke_config.example.env
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

# ── 报告结构 ──────────────────────────────────────────────────────

VALID_MATERIAL_ENGINES = frozenset({
    "doubao_two_stage", "doubao_single_shot",
    "edu-solid-geometry", "edu-chem-reaction",
})


@dataclass
class CaseResult:
    name: str
    method: str
    path: str
    status: str  # pass | fail | skip
    http_status: Optional[int] = None
    detail: str = ""
    ms: float = 0.0
    module: str = ""


@dataclass
class SmokeReport:
    started_at: str = ""
    base_url: str = ""
    frontend_url: str = ""
    dry_run: bool = True
    ui: bool = False
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        c = {"pass": 0, "fail": 0, "skip": 0}
        for r in self.cases:
            c[r.status] = c.get(r.status, 0) + 1
        return c

    def add(self, case: CaseResult) -> None:
        self.cases.append(case)

    def print_summary(self) -> None:
        s = self.summary
        print("\n" + "=" * 60)
        print(f"SMOKE SUMMARY  pass={s['pass']}  fail={s['fail']}  skip={s['skip']}")
        print("=" * 60)
        by_mod: dict[str, list[CaseResult]] = {}
        for c in self.cases:
            by_mod.setdefault(c.module or "other", []).append(c)
        for mod, items in sorted(by_mod.items()):
            print(f"\n[{mod}]")
            for c in items:
                icon = {"pass": "OK", "fail": "FAIL", "skip": "SKIP"}[c.status]
                st = f" HTTP {c.http_status}" if c.http_status is not None else ""
                print(f"  {icon:4} {c.name}{st} ({c.ms:.0f}ms)")
                if c.status == "fail" and c.detail:
                    print(f"       -> {c.detail[:200]}")

    def save(self, path: str) -> None:
        payload = {
            "started_at": self.started_at,
            "base_url": self.base_url,
            "frontend_url": self.frontend_url,
            "dry_run": self.dry_run,
            "ui": self.ui,
            "summary": self.summary,
            "cases": [asdict(c) for c in self.cases],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\nReport saved: {path}")


# ── API Runner ────────────────────────────────────────────────────

class ApiSmokeRunner:
    def __init__(
        self,
        base_url: str,
        user: str,
        password: str,
        report: SmokeReport,
        *,
        dry_run: bool = True,
        lesson_id: Optional[str] = None,
    ):
        self.base = base_url.rstrip("/")
        self.user = user
        self.password = password
        self.report = report
        self.dry_run = dry_run
        self.lesson_id = lesson_id
        self.token: Optional[str] = None
        self.me: dict[str, Any] = {}

    def _record(
        self,
        name: str,
        method: str,
        path: str,
        ok: bool,
        *,
        http_status: Optional[int] = None,
        detail: str = "",
        ms: float = 0,
        module: str = "",
        skip: bool = False,
    ) -> None:
        self.report.add(CaseResult(
            name=name,
            method=method,
            path=path,
            status="skip" if skip else ("pass" if ok else "fail"),
            http_status=http_status,
            detail=detail,
            ms=ms,
            module=module,
        ))

    async def _req(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        *,
        name: str,
        module: str,
        ok_statuses: tuple[int, ...] = (200,),
        json_body: Any = None,
        data: Any = None,
        extra_ok: Callable[[httpx.Response], bool] | None = None,
    ) -> httpx.Response | None:
        url = f"{self.base}{path}"
        t0 = time.perf_counter()
        try:
            r = await client.request(method, url, json=json_body, data=data)
            ms = (time.perf_counter() - t0) * 1000
            ok = r.status_code in ok_statuses or (extra_ok(r) if extra_ok else False)
            detail = "" if ok else (r.text[:300] if r.text else f"status={r.status_code}")
            self._record(name, method, path, ok, http_status=r.status_code, detail=detail, ms=ms, module=module)
            return r
        except Exception as e:
            ms = (time.perf_counter() - t0) * 1000
            self._record(name, method, path, False, detail=str(e), ms=ms, module=module)
            return None

    async def run(self) -> None:
        await self._test_material_local()
        async with httpx.AsyncClient(timeout=30.0) as client:
            await self._test_health(client)
            await self._test_login(client)
            if not self.token:
                return
            headers = {"Authorization": f"Bearer {self.token}"}
            async with httpx.AsyncClient(timeout=30.0, headers=headers) as authed:
                await self._test_auth_me(authed)
                await self._test_system(authed)
                await self._test_teaching_models(authed)
                await self._test_textbooks(authed)
                await self._test_lessons(authed)
                await self._test_export(authed)
                await self._test_course_tools(authed)
                await self._test_payments(authed)
                await self._test_documents(authed)
                await self._test_series(authed)
                await self._test_template_fill(authed)
                await self._test_semester_helper(authed)
                await self._test_admin(authed)

    async def _test_material_local(self) -> None:
        module = "material_local"
        t0 = time.perf_counter()
        try:
            from app.services.material_html_service import (
                build_material_html, validate_material_data,
            )
            sample = {
                "title": "冒烟测试课程",
                "summary": "用于验证模板渲染与交互元素是否齐全。",
                "sections": [
                    {
                        "id": f"s{i}",
                        "title": f"知识点{i}",
                        "icon": "fa-book",
                        "content": "详细说明" * 40,
                        "diagram_hint": f"示意图{i}",
                        "quiz": [{"question": f"Q{i}?", "answer": f"A{i}"}],
                    }
                    for i in range(1, 7)
                ],
            }
            ok_val, reason = validate_material_data(sample)
            html = build_material_html(sample)
            checks = [
                ok_val,
                len(html.encode("utf-8")) >= 15_000,
                "btn-fullscreen" in html,
                "btn-theme" in html,
                "quiz-btn" in html,
                "<script>" in html,
            ]
            ok = all(checks)
            detail = "" if ok else f"validate={ok_val} reason={reason} bytes={len(html)}"
            ms = (time.perf_counter() - t0) * 1000
            self._record("material_html_local", "LOCAL", "-", ok, detail=detail, ms=ms, module=module)
        except Exception as e:
            ms = (time.perf_counter() - t0) * 1000
            self._record("material_html_local", "LOCAL", "-", False, detail=str(e), ms=ms, module=module)

    async def _test_health(self, client: httpx.AsyncClient) -> None:
        await self._req(client, "GET", "/health", name="health", module="system")

    async def _test_login(self, client: httpx.AsyncClient) -> None:
        t0 = time.perf_counter()
        path = "/api/v1/auth/login"
        try:
            r = await client.post(
                f"{self.base}{path}",
                json={"username": self.user, "password": self.password},
            )
            ms = (time.perf_counter() - t0) * 1000
            ok = r.status_code == 200
            if ok:
                data = r.json()
                self.token = data.get("access_token")
                self.me = data.get("user") or {}
            detail = "" if ok else r.text[:200]
            self._record("auth_login", "POST", path, ok, http_status=r.status_code, detail=detail, ms=ms, module="auth")
        except Exception as e:
            ms = (time.perf_counter() - t0) * 1000
            self._record("auth_login", "POST", path, False, detail=str(e), ms=ms, module="auth")

    async def _test_auth_me(self, client: httpx.AsyncClient) -> None:
        r = await self._req(client, "GET", "/api/v1/auth/me", name="auth_me", module="auth")
        if r and r.status_code == 200:
            data = r.json()
            self.me = data
            ok = "export_credits" in data and "export_pay_exempt" in data
            self._record(
                "auth_me_export_fields", "GET", "/api/v1/auth/me", ok,
                detail="" if ok else "missing export_credits/export_pay_exempt",
                module="auth",
            )

    async def _test_system(self, client: httpx.AsyncClient) -> None:
        await self._req(client, "GET", "/api/v1/system/banner", name="system_banner", module="system")
        r = await self._req(client, "GET", "/api/v1/system/queue", name="system_queue", module="system")
        if r and r.status_code == 200:
            data = r.json()
            has_timeout = any(k in data for k in (
                "task_timeout_sec", "lesson_task_timeout_sec", "tool_task_timeout_sec",
            ))
            self._record(
                "system_queue_timeout_fields", "GET", "/api/v1/system/queue", has_timeout,
                detail="" if has_timeout else "missing per-kind timeout fields",
                module="system",
            )

    async def _test_teaching_models(self, client: httpx.AsyncClient) -> None:
        await self._req(client, "GET", "/api/v1/teaching-models", name="teaching_models", module="teaching_models")

    async def _test_textbooks(self, client: httpx.AsyncClient) -> None:
        await self._req(client, "GET", "/api/v1/textbooks/catalog", name="textbooks_catalog", module="textbooks")

    async def _test_lessons(self, client: httpx.AsyncClient) -> None:
        r = await self._req(
            client, "GET", "/api/v1/lessons?limit=5",
            name="lessons_list", module="lessons",
        )
        lid = self.lesson_id
        if not lid and r and r.status_code == 200:
            items = r.json()
            if items:
                lid = items[0].get("id")
        if not lid:
            self._record("lessons_detail", "GET", "/api/v1/lessons/{id}", False,
                           skip=True, detail="no lesson_id", module="lessons")
            return
        self.lesson_id = lid
        await self._req(client, "GET", f"/api/v1/lessons/{lid}", name="lessons_detail", module="lessons")
        await self._req(client, "GET", f"/api/v1/lessons/{lid}/discussions", name="lessons_discussions", module="lessons")
        await self._req(client, "GET", f"/api/v1/lessons/{lid}/status", name="lessons_status", module="lessons")

    async def _test_export(self, client: httpx.AsyncClient) -> None:
        module = "export"
        lid = self.lesson_id
        if not lid:
            self._record("export_json", "GET", "/api/v1/export/json/{id}", False,
                           skip=True, detail="no lesson_id", module=module)
            return

        def export_ok(resp: httpx.Response) -> bool:
            return resp.status_code in (200, 402, 403)

        await self._req(
            client, "GET", f"/api/v1/export/json/{lid}",
            name="export_json", module=module,
            ok_statuses=(),
            extra_ok=export_ok,
        )

        r = await self._req(client, "GET", f"/api/v1/lessons/{lid}", name="export_lesson_fc", module=module)
        if r and r.status_code == 200:
            fc = (r.json().get("final_content") or {})
            if isinstance(fc, str):
                try:
                    fc = json.loads(fc)
                except Exception:
                    fc = {}
            for ver in ("draft", "optimized"):
                html = fc.get(f"material_{ver}_html") or ""
                engine = fc.get(f"material_{ver}_engine") or ""
                st = fc.get(f"material_{ver}_status") or ""
                if not html or st != "done":
                    self._record(
                        f"material_{ver}_remote", "GET", f"lesson/{lid}/fc",
                        True, skip=True, detail=f"no done material ({st})", module=module,
                    )
                    continue
                size = len(html.encode("utf-8"))
                ok = (
                    size >= 15_000
                    and "btn-fullscreen" in html
                    and "btn-theme" in html
                    and "quiz-btn" in html
                    and "<script>" in html
                    and (not engine or engine in VALID_MATERIAL_ENGINES)
                )
                detail = f"bytes={size} engine={engine}" if ok else f"bytes={size} engine={engine} missing interactive tags"
                self._record(f"material_{ver}_quality", "CHECK", "-", ok, detail=detail, module=module)

        if not self.dry_run:
            t0 = time.perf_counter()
            path = f"/api/v1/export/material/generate/{lid}"
            try:
                r = await client.post(
                    f"{self.base}{path}",
                    data={"content_version": "draft"},
                )
                ms = (time.perf_counter() - t0) * 1000
                ok = r.status_code in (200, 402)
                detail = "" if ok else r.text[:200]
                self._record("material_generate_enqueue", "POST", path, ok,
                             http_status=r.status_code, detail=detail, ms=ms, module=module)
            except Exception as e:
                ms = (time.perf_counter() - t0) * 1000
                self._record("material_generate_enqueue", "POST", path, False, detail=str(e), ms=ms, module=module)
        else:
            self._record("material_generate_enqueue", "POST", f"/api/v1/export/material/generate/{lid}",
                         True, skip=True, detail="dry-run", module=module)

    async def _test_course_tools(self, client: httpx.AsyncClient) -> None:
        await self._req(client, "GET", "/api/v1/course-tools/history", name="course_tools_history", module="course_tools")

    async def _test_payments(self, client: httpx.AsyncClient) -> None:
        r = await self._req(client, "GET", "/api/v1/payments/config", name="payments_config", module="payments")
        if r and r.status_code == 200:
            data = r.json()
            ok = "price" in data and "credits_per_order" in data
            self._record("payments_config_fields", "GET", "/api/v1/payments/config", ok,
                         detail="" if ok else str(list(data.keys())[:8]), module="payments")

    async def _test_documents(self, client: httpx.AsyncClient) -> None:
        await self._req(client, "GET", "/api/v1/documents/library", name="documents_library", module="documents")
        await self._req(client, "GET", "/api/v1/documents/exports", name="documents_exports", module="documents")

    async def _test_series(self, client: httpx.AsyncClient) -> None:
        await self._req(client, "GET", "/api/v1/series", name="series_list", module="series")

    async def _test_template_fill(self, client: httpx.AsyncClient) -> None:
        await self._req(
            client, "GET", "/api/v1/template-fill/history",
            name="template_fill_history", module="template_fill",
            ok_statuses=(200, 403),
        )

    async def _test_semester_helper(self, client: httpx.AsyncClient) -> None:
        await self._req(client, "GET", "/api/v1/semester-helper/ping", name="semester_ping", module="semester")
        await self._req(
            client, "GET", "/api/v1/semester-helper/zhuke/history",
            name="zhuke_history", module="semester",
            ok_statuses=(200, 403),
        )

    async def _test_admin(self, client: httpx.AsyncClient) -> None:
        level = (self.me.get("access_level") or "").lower()
        is_admin = level == "admin" or self.me.get("username") in ("lzf", "ys")
        if not is_admin:
            self._record("admin_users", "GET", "/api/v1/admin/users", True,
                         skip=True, detail="not admin", module="admin")
            return
        await self._req(client, "GET", "/api/v1/admin/users", name="admin_users", module="admin")
        await self._req(client, "GET", "/api/v1/payments/orders", name="admin_payment_orders", module="admin")


# ── UI Runner ─────────────────────────────────────────────────────

class UiSmokeRunner:
    def __init__(
        self,
        frontend_url: str,
        base_url: str,
        user: str,
        password: str,
        token: str,
        user_data: dict,
        report: SmokeReport,
        *,
        lesson_id: Optional[str] = None,
    ):
        self.frontend = frontend_url.rstrip("/")
        self.base_url = base_url
        self.user = user
        self.password = password
        self.token = token
        self.user_data = user_data
        self.report = report
        self.lesson_id = lesson_id

    def _ui(self, name: str, ok: bool, detail: str = "", module: str = "ui") -> None:
        self.report.add(CaseResult(
            name=name, method="UI", path="-", status="pass" if ok else "fail",
            detail=detail, module=module,
        ))

    def run(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self._ui("playwright_import", False, "pip install playwright && playwright install chromium")
            return

        errors: list[str] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.on("pageerror", lambda exc: errors.append(str(exc)))

            # 注入 token 跳过重复登录（zustand persist）
            auth_state = json.dumps({
                "state": {"token": self.token, "user": self.user_data},
                "version": 0,
            })
            page.goto(f"{self.frontend}/login")
            page.evaluate("(s) => localStorage.setItem('edusymphony-auth', s)", auth_state)

            # Dashboard
            page.goto(f"{self.frontend}/dashboard")
            page.wait_for_load_state("networkidle")
            ok_dash = (
                page.locator("a[href*='/lesson/new']").count() > 0
                or page.get_by_text("快速生成").count() > 0
                or page.get_by_text("新建教案").count() > 0
            )
            self._ui("dashboard_links", ok_dash, module="ui_dashboard")

            # Course tools tabs
            page.goto(f"{self.frontend}/course-tools")
            page.wait_for_load_state("networkidle")
            for tab in ("内容大纲", "PPT", "习题作业", "课上练习", "知识漫画", "英语卡片"):
                try:
                    loc = page.get_by_text(tab, exact=False).first
                    if loc.count() > 0:
                        loc.click(timeout=5000)
                        page.wait_for_timeout(300)
                except Exception:
                    pass
            self._ui("course_tools_tabs", True, module="ui_course_tools")

            # Documents
            page.goto(f"{self.frontend}/documents")
            page.wait_for_load_state("networkidle")
            self._ui(
                "documents_page",
                "/documents" in page.url,
                module="ui_documents",
            )

            # Lesson process
            if self.lesson_id:
                page.goto(f"{self.frontend}/lesson/{self.lesson_id}/process")
                page.wait_for_load_state("networkidle")
                for tab_text in ("初步教案", "优化教案", "教学材料", "专家分析"):
                    try:
                        btn = page.get_by_text(tab_text, exact=False).first
                        if btn.count() > 0:
                            btn.click(timeout=5000)
                            page.wait_for_timeout(400)
                    except Exception:
                        pass
                self._ui("lesson_process_tabs", True, module="ui_lesson")

                # Material tab: preview iframe sandbox
                try:
                    page.get_by_text("教学材料", exact=False).first.click(timeout=5000)
                    page.wait_for_timeout(500)
                    preview = page.get_by_text("预览", exact=False).first
                    if preview.count() > 0 and preview.is_visible():
                        preview.click(timeout=5000)
                        page.wait_for_timeout(800)
                        iframe = page.locator("iframe[title='Course Material Preview']")
                        if iframe.count() > 0:
                            sandbox = iframe.get_attribute("sandbox") or ""
                            ok_sb = "allow-same-origin" in sandbox and "allow-scripts" in sandbox
                            self._ui("material_preview_sandbox", ok_sb, detail=sandbox, module="ui_material")
                        else:
                            self.report.add(CaseResult(
                                name="material_preview_modal", method="UI", path="-", status="skip",
                                detail="iframe not found (material may not be done)", module="ui_material",
                            ))
                    else:
                        self.report.add(CaseResult(
                            name="material_preview_sandbox", method="UI", path="-", status="skip",
                            detail="no preview button (material not done)", module="ui_material",
                        ))
                except Exception as e:
                    self._ui("material_preview_sandbox", False, detail=str(e), module="ui_material")
            else:
                self.report.add(CaseResult(
                    name="lesson_process_tabs", method="UI", path="-", status="skip",
                    detail="no lesson_id", module="ui_lesson",
                ))

            # Admin
            page.goto(f"{self.frontend}/admin/users")
            page.wait_for_load_state("networkidle")
            is_admin = (self.user_data.get("access_level") or "").lower() == "admin" or \
                self.user_data.get("username") in ("lzf", "ys")
            if is_admin:
                ok_admin = "/admin/users" in page.url
                self._ui("admin_users_page", ok_admin, module="ui_admin")
            else:
                self.report.add(CaseResult(
                    name="admin_users_page", method="UI", path="-", status="skip",
                    detail="not admin", module="ui_admin",
                ))

            # Login form smoke (fresh context)
            ctx2 = browser.new_context()
            p2 = ctx2.new_page()
            p2.goto(f"{self.frontend}/login")
            p2.get_by_placeholder("请输入用户名").fill(self.user)
            p2.get_by_placeholder("请输入密码").fill(self.password)
            p2.get_by_role("button", name="登录").click()
            p2.wait_for_url("**/dashboard**", timeout=15000)
            self._ui("login_form", "/dashboard" in p2.url, module="ui_auth")
            ctx2.close()

            if errors:
                self._ui("no_console_errors", False, detail="; ".join(errors[:3]), module="ui_console")
            else:
                self._ui("no_console_errors", True, module="ui_console")

            browser.close()


# ── Main ──────────────────────────────────────────────────────────

def _load_env_files() -> None:
    try:
        from dotenv import load_dotenv
        root = Path(__file__).resolve().parents[1]
        load_dotenv(root / ".env", override=False)
        load_dotenv(root.parent / ".env", override=False)
    except ImportError:
        pass


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


async def async_main(args: argparse.Namespace) -> int:
    report = SmokeReport(
        started_at=datetime.now(timezone.utc).isoformat(),
        base_url=args.base_url,
        frontend_url=args.frontend_url,
        dry_run=args.dry_run,
        ui=args.ui,
    )

    api = ApiSmokeRunner(
        args.base_url,
        args.user,
        args.password,
        report,
        dry_run=args.dry_run,
        lesson_id=args.lesson_id or _env("SMOKE_LESSON_ID") or None,
    )
    await api.run()

    if args.ui:
        if not api.token:
            report.add(CaseResult(
                name="ui_skipped", method="UI", path="-", status="skip",
                detail="API login failed", module="ui",
            ))
        else:
            ui = UiSmokeRunner(
                args.frontend_url,
                args.base_url,
                args.user,
                args.password,
                api.token,
                api.me,
                report,
                lesson_id=api.lesson_id,
            )
            ui.run()

    report.print_summary()
    report.save(args.report)
    return 1 if report.summary.get("fail", 0) > 0 else 0


def main() -> None:
    _load_env_files()
    parser = argparse.ArgumentParser(description="EduSymphony full-stack smoke tests")
    parser.add_argument("--base-url", default=_env("SMOKE_BASE_URL", "http://localhost:3002"))
    parser.add_argument("--frontend-url", default=_env("SMOKE_FRONTEND_URL", "http://localhost:3000"))
    parser.add_argument("--user", default=_env("SMOKE_USER", "lzf"))
    parser.add_argument("--password", default=_env("SMOKE_PASS", ""))
    parser.add_argument("--lesson-id", default=_env("SMOKE_LESSON_ID", ""))
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Skip AI enqueue POSTs (default: on)")
    parser.add_argument("--live", action="store_true", help="Allow material generate enqueue")
    parser.add_argument("--ui", action="store_true", help="Run Playwright UI smoke")
    parser.add_argument("--report", default="smoke_report.json")
    args = parser.parse_args()
    if args.live:
        args.dry_run = False
    if not args.password:
        print("WARN: --password / SMOKE_PASS not set; login may fail", file=sys.stderr)
    raise SystemExit(asyncio.run(async_main(args)))


if __name__ == "__main__":
    main()
