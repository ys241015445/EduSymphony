-- ============================================================
-- EduSymphony — Supabase 性能优化索引 (v2)
-- 使用方法：在 Supabase SQL Editor 执行，或通过 psql 运行
-- 安全性：全部使用 CREATE INDEX IF NOT EXISTS，幂等可重复执行
-- 生成时间：2026-04-08 (v2 refreshed)
-- ============================================================

-- ------------------------------------------------------------
-- 1. 复合索引（高频组合查询）
--    lessons.py 的 list_lessons 总是 user_id + created_at DESC
--    status 过滤也高频 (队列/处理中)
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_lesson_plans_user_created
    ON lesson_plans (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_lesson_plans_user_status_created
    ON lesson_plans (user_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_discussions_lesson_stage_created
    ON discussions (lesson_plan_id, stage, created_at);

CREATE INDEX IF NOT EXISTS idx_annotations_lesson_user
    ON annotations (lesson_plan_id, user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_course_tool_user_type_created
    ON course_tool_results (user_id, tool_type, created_at DESC);

-- ------------------------------------------------------------
-- 2. 外键专属索引（DELETE/JOIN 性能）
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_lesson_plans_parent
    ON lesson_plans (parent_lesson_id)
    WHERE parent_lesson_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_lesson_plans_teaching_model
    ON lesson_plans (teaching_model_id)
    WHERE teaching_model_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_lesson_plans_sequence_order
    ON lesson_plans (sequence_id, sequence_order)
    WHERE sequence_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_course_tool_lesson_type
    ON course_tool_results (lesson_id, tool_type)
    WHERE lesson_id IS NOT NULL;

-- ------------------------------------------------------------
-- 3. 状态/队列索引（后台任务调度 & 恢复常用）
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_lesson_plans_active_status
    ON lesson_plans (status, created_at)
    WHERE status IN ('queued', 'processing', 'awaiting_confirmation');

-- 系列状态索引：SeriesDashboard 频繁按 user + status 轮询
CREATE INDEX IF NOT EXISTS idx_lesson_series_user_status
    ON lesson_series (user_id, status, created_at DESC);

-- 系列 → 课程的批量查询（/series/:id/lessons）
CREATE INDEX IF NOT EXISTS idx_lesson_plans_sequence_status
    ON lesson_plans (sequence_id, status)
    WHERE sequence_id IS NOT NULL;

-- ------------------------------------------------------------
-- 4. 层级筛选索引（大学教案新增）
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_lesson_series_education_level
    ON lesson_series (education_level);

CREATE INDEX IF NOT EXISTS idx_lesson_plans_education_level
    ON lesson_plans (education_level);

-- ------------------------------------------------------------
-- 5. 清理冗余索引（被复合索引覆盖后可删）
--    注意：DROP INDEX 需要手动确认是否不再使用，这里默认注释
-- ------------------------------------------------------------

-- DROP INDEX IF EXISTS idx_lesson_plans_user_id;      -- 被 idx_lesson_plans_user_created 覆盖
-- DROP INDEX IF EXISTS idx_lesson_plans_sequence;     -- 被 idx_lesson_plans_sequence_order 覆盖
-- DROP INDEX IF EXISTS idx_discussions_lesson;        -- 被 idx_discussions_lesson_stage_created 覆盖
-- DROP INDEX IF EXISTS idx_annotations_lesson;        -- 被 idx_annotations_lesson_user 覆盖

-- ------------------------------------------------------------
-- 6. 建议服务端参数（Supabase → Project Settings → Database → Custom settings）
--    对应代码里的 statement_timeout / idle_in_transaction_session_timeout
--    连接串里已 per-connection 注入，无须改项目级设置
-- ------------------------------------------------------------

-- ------------------------------------------------------------
-- 7. 执行完后更新统计信息
-- ------------------------------------------------------------

ANALYZE lesson_plans;
ANALYZE discussions;
ANALYZE annotations;
ANALYZE course_tool_results;
ANALYZE users;
ANALYZE lesson_series;

-- ============================================================
-- Done
-- ============================================================
