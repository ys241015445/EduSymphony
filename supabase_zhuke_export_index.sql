-- ============================================================
-- 珠科教案生成的 export_records 查询优化
-- 用于 /api/v1/semester-helper/zhuke/history 和 「我的珠科教案」页面
--
-- 现有 idx_export_records_user_created 已覆盖通用 user × created_at 查询，
-- 这里再加一个针对 source_kind='zhuke_generation' 的 PARTIAL INDEX：
--   - 只索引活跃（未软删）的珠科生成行，比通用索引小 90%+
--   - 命中 /zhuke/history 端点的 WHERE user_id=:uid AND source_kind=...
--     AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 200 查询路径
--   - 同时覆盖 admin /zhuke/admin/cleanup-missing 全表扫描
--
-- 完全幂等（IF NOT EXISTS），随时可重复执行。
-- 部署到 Supabase Dashboard → SQL Editor。
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_export_records_zhuke_user_created
    ON export_records (user_id, created_at DESC)
    WHERE source_kind = 'zhuke_generation' AND deleted_at IS NULL;

-- admin cleanup / 后端 startup sweep 的 "全表按 source_kind 扫" 也加速
CREATE INDEX IF NOT EXISTS idx_export_records_zhuke_status
    ON export_records (source_kind, status, updated_at)
    WHERE source_kind = 'zhuke_generation' AND deleted_at IS NULL;

-- 让 query planner 即时知道新索引存在
ANALYZE export_records;
