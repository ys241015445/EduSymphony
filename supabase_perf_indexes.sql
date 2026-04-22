-- ============================================================
-- EduSymphony — Supabase 性能优化索引
-- 使用方法：在 Supabase SQL Editor 执行，或通过 psql 运行
-- 安全性：全部使用 CREATE INDEX IF NOT EXISTS + CONCURRENTLY，不锁表
-- 生成时间：2026-04-08
-- ============================================================

-- ------------------------------------------------------------
-- 1. 复合索引（高频组合查询）
--    lessons.py 的 list_lessons 总是 user_id + created_at DESC
--    status 过滤也高频 (队列/处理中)
-- ------------------------------------------------------------

-- 替代 idx_lesson_plans_user_id，用于 WHERE user_id=? ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_lesson_plans_user_created
    ON lesson_plans (user_id, created_at DESC);

-- 用于 WHERE user_id=? AND status=? ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_lesson_plans_user_status_created
    ON lesson_plans (user_id, status, created_at DESC);

-- discussions 按 lesson + stage 查询（投票、续写均用到）
CREATE INDEX IF NOT EXISTS idx_discussions_lesson_stage_created
    ON discussions (lesson_plan_id, stage, created_at);

-- annotations 按 lesson + user 查询
CREATE INDEX IF NOT EXISTS idx_annotations_lesson_user
    ON annotations (lesson_plan_id, user_id, created_at);

-- course_tool_results 按 user + type + time 倒序
CREATE INDEX IF NOT EXISTS idx_course_tool_user_type_created
    ON course_tool_results (user_id, tool_type, created_at DESC);

-- ------------------------------------------------------------
-- 2. 外键专属索引（DELETE/JOIN 性能）
--    parent_lesson_id、teaching_model_id、sequence_id 都是 FK，必须独立索引
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_lesson_plans_parent
    ON lesson_plans (parent_lesson_id)
    WHERE parent_lesson_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_lesson_plans_teaching_model
    ON lesson_plans (teaching_model_id)
    WHERE teaching_model_id IS NOT NULL;

-- 替代 idx_lesson_plans_sequence，支持按序列排序
CREATE INDEX IF NOT EXISTS idx_lesson_plans_sequence_order
    ON lesson_plans (sequence_id, sequence_order)
    WHERE sequence_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_course_tool_lesson_type
    ON course_tool_results (lesson_id, tool_type)
    WHERE lesson_id IS NOT NULL;

-- ------------------------------------------------------------
-- 3. 状态/队列索引（后台任务调度常用）
-- ------------------------------------------------------------

-- 仅索引活跃状态，避免冷数据浪费空间
CREATE INDEX IF NOT EXISTS idx_lesson_plans_active_status
    ON lesson_plans (status, created_at)
    WHERE status IN ('queued', 'processing', 'awaiting_confirmation');

-- ------------------------------------------------------------
-- 4. 清理冗余索引（被复合索引覆盖后可删）
--    注意：DROP INDEX 需要手动确认是否不再使用，安全起见这里注释掉
-- ------------------------------------------------------------

-- 以下索引被新复合索引完全覆盖，可手动删除以减少写入开销：
-- DROP INDEX IF EXISTS idx_lesson_plans_user_id;      -- 被 idx_lesson_plans_user_created 覆盖
-- DROP INDEX IF EXISTS idx_lesson_plans_sequence;     -- 被 idx_lesson_plans_sequence_order 覆盖
-- DROP INDEX IF EXISTS idx_discussions_lesson;        -- 被 idx_discussions_lesson_stage_created 覆盖
-- DROP INDEX IF EXISTS idx_annotations_lesson;        -- 被 idx_annotations_lesson_user 覆盖

-- ------------------------------------------------------------
-- 5. 完成后建议执行，更新统计信息以让规划器使用新索引
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
