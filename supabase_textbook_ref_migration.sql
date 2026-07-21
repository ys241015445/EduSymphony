-- =============================================================================
-- 教材接地（ChinaTextbook）：为 lesson_plans 增加 textbook_ref 列
-- 存教师所选的"版本/册次/章节"紧凑串（仅元数据，不含 PDF/正文）。
-- 幂等，可重复执行。
--   Supabase Dashboard -> SQL Editor 粘贴运行。
-- =============================================================================

ALTER TABLE lesson_plans
  ADD COLUMN IF NOT EXISTS textbook_ref varchar(300);
