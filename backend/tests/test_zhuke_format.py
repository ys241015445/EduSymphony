"""Regression tests for Zhuke docx text formatting."""
from __future__ import annotations

import io
import unittest
import zipfile

from app.services import zhuke_lesson as zl


class TestFormatSectionForDocx(unittest.TestCase):
    def _fmt(self, text: str) -> str:
        return zl.format_section_for_docx(text)

    def test_numbered_items_split(self):
        out = self._fmt("1. 思政目标内容。2. 知识目标内容。")
        self.assertIn("\n2.", out)

    def test_numbered_no_space(self):
        out = self._fmt("1.思政目标2.知识目标")
        self.assertIn("\n2.", out)

    def test_subsection_21(self):
        out = self._fmt("讲解环节。2.1 子节A 2.2 子节B")
        self.assertIn("\n2.1", out)
        self.assertIn("\n2.2", out)

    def test_chinese_enumeration(self):
        out = self._fmt("一、知识基础；二、能力特点；三、思想特点。")
        self.assertIn("\n二、", out)
        self.assertIn("\n三、", out)

    def test_parenthetical_blocks(self):
        out = self._fmt("（一）教材引用（二）网络资料")
        self.assertIn("\n（二）", out)

    def test_teaching_focus_lines(self):
        out = self._fmt("主要内容描述。教学重点：A  教学难点：B")
        self.assertIn("\n教学重点：", out)
        self.assertIn("\n教学难点：", out)

    def test_checkbox_methods(self):
        out = self._fmt("项目教学法 ☑ 讨论法☑")
        self.assertIn("项目教学法☑", out)
        self.assertIn("讨论法☑", out)

    def test_no_double_blank_lines(self):
        out = self._fmt("1. A\n\n\n2. B")
        self.assertNotIn("\n\n", out)
        self.assertIn("\n2.", out)

    def test_leading_blank_from_enum_split_removed(self):
        out = self._fmt("一、知识基础；二、能力特点")
        self.assertFalse(out.startswith("\n"))

    def test_checkbox_media(self):
        out = self._fmt("教材 ☑ 多媒体☑ AI 工具 ☑")
        self.assertIn("教材☑", out)
        self.assertIn("多媒体☑", out)
        self.assertIn("AI 工具☑", out)

    def test_strip_markdown_bold(self):
        out = self._fmt("**重点**内容")
        self.assertEqual(out, "重点内容")

    def test_strip_markdown_list(self):
        out = self._fmt("- 条目一\n- 条目二")
        self.assertIn("条目一", out)
        self.assertNotIn("- 条目", out)

    def test_chinese_comma_numbering(self):
        out = self._fmt("1、第一项\n2、第二项")
        self.assertIn("1. 第一项", out)

    def test_paren_arabic_numbering(self):
        out = self._fmt("(1) 第一项 (2) 第二项")
        self.assertIn("\n2.", out)

    def test_empty_input(self):
        self.assertEqual(self._fmt(""), "")
        self.assertEqual(self._fmt("   "), "")

    def test_normalize_sections_alias(self):
        secs = zl.normalize_sections({"教学目标": "1. A 2. B"})
        self.assertIn("\n2.", secs["教学目标"])

    def test_fmt_section_value_none(self):
        self.assertIsNone(zl._fmt_section_value(None))
        self.assertIsNone(zl._fmt_section_value("   "))

    def test_reference_joins_broken_lines(self):
        raw = (
            "(一)教材\n"
            "李沐等. 动手学深度学习[M]. 北京: 人民邮电出版社,\n"
            "2023.\n"
            "(二)参考资料\n"
            "[1] Radford A, et al. Learning visual models[C]//ICML. PMLR, 2021: 8748-\n"
            "8763."
        )
        out = zl.format_section_for_docx(raw, reference=True)
        self.assertIn("出版社, 2023.", out)
        self.assertIn("8748-8763.", out)
        self.assertNotIn("出版社,\n2023", out)
        self.assertIn("[M]", out)
        self.assertIn("[C]", out)

    def test_reference_section_headers_on_own_lines(self):
        raw = "(一)教材\n书[M]. 2023.\n(二)参考资料\n[1] A[J]. B, 2022."
        out = zl.format_section_for_docx(raw, reference=True)
        lines = [ln for ln in out.split("\n") if ln.strip()]
        self.assertEqual(lines[0], "(一)教材")
        self.assertEqual(lines[2], "(二)参考资料")
        self.assertTrue(lines[3].startswith("[1]"))

    def test_reference_halfwidth_punctuation(self):
        out = zl.format_section_for_docx(
            "作者。书名[M]。北京：出版社，2023。",
            reference=True,
        )
        self.assertIn("作者.书名[M].", out)
        self.assertNotIn("。", out)


class TestLintSectionsFormat(unittest.TestCase):
    def test_clean_after_normalize(self):
        secs = zl.normalize_sections({"教学目标": "1. A\n2. B"})
        self.assertEqual(zl.lint_sections_format(secs), [])

    def test_inline_numbering_now_clean(self):
        # 2026-05: inline numbering is fully repaired by format_section_for_docx,
        # so lint no longer flags it — saving a 60-180s Kimi layout review call.
        issues = zl.lint_sections_format({"教学目标": "1. A。2. B"})
        self.assertEqual(issues, [])

    def test_detect_markdown(self):
        issues = zl.lint_sections_format({"学情分析": "**重点**内容"})
        self.assertTrue(any("Markdown" in i for i in issues))

    def test_detect_checkbox_space(self):
        issues = zl.lint_sections_format({"教学方法": "项目教学法 ☑ 讨论法☑"})
        self.assertTrue(any("空格" in i for i in issues))

    def test_focus_inline_now_clean(self):
        # Normalizer already splits 教学重点：/ 教学难点： onto their own lines.
        issues = zl.lint_sections_format({"主要教学内容": "描述。教学重点：A  教学难点：B"})
        self.assertEqual(issues, [])

    def test_detect_missing_gb7714_type(self):
        issues = zl.lint_sections_format({"参考资料": "(一)教材\n某书. 2023."})
        self.assertTrue(any("文献类型" in i for i in issues))

    def test_gb7714_type_clean(self):
        issues = zl.lint_sections_format(
            {"参考资料": "[1] Author. Title[J]. Journal, 2022, 1(2): 1-10."}
        )
        self.assertEqual(issues, [])


class TestFinalizeLessonSectionsPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_skip_ai_skips_review(self):
        from app.tasks import zhuke_task as zt

        out = await zt._finalize_lesson_sections(
            {"教学目标": "1. A。2. B"},
            skip_ai=True,
            lesson_idx=0,
            total=1,
        )
        self.assertIn("\n2.", out.get("教学目标", ""))

    async def test_clean_sections_skip_kimi_review(self):
        from unittest.mock import patch
        from app.tasks import zhuke_task as zt

        clean = zl.normalize_sections({"教学目标": "1. A\n2. B"})
        with patch.object(zl, "layout_review_always_enabled", return_value=False):
            with patch.object(zl, "LayoutReviewAgent") as mock_cls:
                out = await zt._finalize_lesson_sections(
                    clean,
                    skip_ai=False,
                    lesson_idx=0,
                    total=1,
                )
                mock_cls.assert_not_called()
        self.assertEqual(out, clean)

    async def test_always_review_calls_kimi(self):
        from unittest.mock import MagicMock, patch
        from app.tasks import zhuke_task as zt

        clean = zl.normalize_sections({"教学目标": "1. A\n2. B"})
        mock_agent = MagicMock()
        mock_agent.review_sections.return_value = clean
        with patch.object(zl, "layout_review_always_enabled", return_value=True):
            with patch.object(zl, "LayoutReviewAgent", return_value=mock_agent):
                out = await zt._finalize_lesson_sections(
                    clean,
                    skip_ai=False,
                    lesson_idx=0,
                    total=1,
                )
        mock_agent.review_sections.assert_called_once()
        self.assertEqual(out, clean)

    async def test_lint_issues_skip_kimi_when_on_lint_disabled(self):
        from unittest.mock import patch
        from app.tasks import zhuke_task as zt

        messy = {"教学目标": "1. A。2. B"}
        with patch.object(zl, "layout_review_on_lint_enabled", return_value=False):
            with patch.object(zl, "layout_review_always_enabled", return_value=False):
                with patch.object(zl, "LayoutReviewAgent") as mock_cls:
                    out = await zt._finalize_lesson_sections(
                        messy,
                        skip_ai=False,
                        lesson_idx=0,
                        total=1,
                    )
                    mock_cls.assert_not_called()
        self.assertIn("教学目标", out)


@unittest.skipUnless(zl.template_exists(), "zhuke template missing")
class TestBuildDocxFormat(unittest.TestCase):
    _FIXTURE_SECTIONS = {
        "学情分析": "一、知识基础；二、能力特点；三、思想特点。",
        "教学目标": "1. 思政目标。2. 知识目标。3. 能力目标。4. 素质目标。",
        "主要教学内容": "本节介绍核心概念。教学重点：概念理解  教学难点：应用迁移",
        "教学方法": "项目教学法 ☑ 讲授法☑",
        "教学媒体": "教材☑ 多媒体☑",
        "教学过程设计": "1. 场景导入（15分钟）2. 讲解（70分钟）2.1 子节一 2.2 子节二 3. 小结（5分钟）",
        "作业布置": "1. 思考题一 2. 实践任务二",
        "参考资料": "[1] Author. Title[J]. Journal, 2022, 1(2): 1-10.",
        "评估与反馈": "1. 课堂评估 2. 反馈机制",
    }

    def _build(self, lessons):
        return zl.build_docx(
            cover={
                "college": "测试学院",
                "major": "测试专业",
                "class_name": "测试班",
                "course_type": "理论",
                "course_name": "测试课程",
                "teacher": "测试教师",
            },
            lesson_contents=lessons,
            semester_label="2025～2026 学年第 2 学期",
        )

    def test_build_contains_fangsong_eastasia(self):
        data = self._build([
            {
                "title": "第1课",
                "topic": "授课内容原文",
                "week": "1",
                "time_label": "第 1 周 星期一  第 3、4 节",
                "hours": "2 学时",
                "sections": self._FIXTURE_SECTIONS,
            },
        ])
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        self.assertIn("eastAsia", xml)
        self.assertIn("仿宋", xml)

    def test_build_table_full_width(self):
        data = self._build([
            {
                "title": "第1课",
                "topic": "授课内容原文",
                "week": "1",
                "time_label": "第 1 周 星期一  第 3、4 节",
                "hours": "2 学时",
                "sections": self._FIXTURE_SECTIONS,
            },
        ])
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        self.assertIn('w:type="pct"', xml)
        self.assertIn("firstLineChars", xml)

    def test_week_pagination_page_break(self):
        data = self._build([
            {"title": "L1", "topic": "T1", "week": "1", "time_label": "", "hours": "2", "sections": self._FIXTURE_SECTIONS},
            {"title": "L2", "topic": "T2", "week": "1", "time_label": "", "hours": "2", "sections": self._FIXTURE_SECTIONS},
            {"title": "L3", "topic": "T3", "week": "2", "time_label": "", "hours": "2", "sections": self._FIXTURE_SECTIONS},
        ])
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        self.assertEqual(xml.count('w:type="page"'), 1)
        self.assertEqual(xml.count("珠海科技学院教学设计"), 2)

    def test_omitted_section_row_removed(self):
        sections = dict(self._FIXTURE_SECTIONS)
        sections.pop("教学媒体", None)
        data = self._build([
            {
                "title": "第1课",
                "topic": "授课内容原文",
                "week": "1",
                "time_label": "第 1 周 星期一  第 3、4 节",
                "hours": "2 学时",
                "sections": sections,
            },
        ])
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        self.assertNotIn("教学媒体（有助于", xml)

    def test_process_design_drops_continuation_table(self):
        data = self._build([
            {
                "title": "第1课",
                "topic": "授课内容原文",
                "week": "1",
                "time_label": "",
                "hours": "2 学时",
                "sections": self._FIXTURE_SECTIONS,
            },
        ])
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        # Template T2 continuation fragment — must not leak when 教学过程设计 is filled.
        self.assertNotIn("2. 讲解具体实现方式", xml)

    def test_focus_folded_into_main_content_removes_template_row(self):
        data = self._build([
            {
                "title": "第1课",
                "topic": "授课内容原文",
                "week": "1",
                "time_label": "",
                "hours": "2 学时",
                "sections": self._FIXTURE_SECTIONS,
            },
        ])
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        self.assertNotIn("Transformer的直观理解", xml)


if __name__ == "__main__":
    unittest.main()
