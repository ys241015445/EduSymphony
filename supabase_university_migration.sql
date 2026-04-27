-- ============================================================
-- EduSymphony — 大学教案专属页面 数据库迁移
-- 生成时间：2026-04-08
-- 说明：为 lesson_series / lesson_plans 增加大学年级所需字段
-- 可在 Supabase SQL Editor 中直接执行（幂等，重复执行不会报错）
-- ============================================================

-- 1) lesson_series 新增字段
ALTER TABLE lesson_series
  ADD COLUMN IF NOT EXISTS education_level      VARCHAR(20) NOT NULL DEFAULT 'k12',
  ADD COLUMN IF NOT EXISTS major                VARCHAR(200),
  ADD COLUMN IF NOT EXISTS course_type          VARCHAR(20),
  ADD COLUMN IF NOT EXISTS course_nature        VARCHAR(20),
  ADD COLUMN IF NOT EXISTS schedule_text        TEXT,
  ADD COLUMN IF NOT EXISTS outline_text         TEXT,
  ADD COLUMN IF NOT EXISTS special_requirements TEXT;

-- 2) lesson_plans 同步 education_level（供 LessonTaskHandler 直接读取）
ALTER TABLE lesson_plans
  ADD COLUMN IF NOT EXISTS education_level VARCHAR(20) NOT NULL DEFAULT 'k12';

-- 3) 方便按层级筛选的辅助索引
CREATE INDEX IF NOT EXISTS idx_lesson_series_education_level ON lesson_series (education_level);
CREATE INDEX IF NOT EXISTS idx_lesson_plans_education_level  ON lesson_plans  (education_level);

-- 4) 校验（可选）
-- SELECT column_name, data_type, column_default
-- FROM information_schema.columns
-- WHERE table_name IN ('lesson_series','lesson_plans')
--   AND column_name IN ('education_level','major','course_type','course_nature','schedule_text','outline_text','special_requirements')
-- ORDER BY table_name, column_name;
