-- =============================================================================
-- 珠科材料助手：教学材料 HTML + PPT 派生字段（增量迁移）
-- 幂等，可重复执行。
-- =============================================================================

ALTER TABLE zhuke_material_projects
  ADD COLUMN IF NOT EXISTS material_html_path VARCHAR(512);

ALTER TABLE zhuke_material_projects
  ADD COLUMN IF NOT EXISTS ppt_path VARCHAR(512);

ALTER TABLE zhuke_material_projects
  ADD COLUMN IF NOT EXISTS material_json TEXT;

ALTER TABLE zhuke_material_projects
  ADD COLUMN IF NOT EXISTS ppt_json TEXT;

COMMENT ON COLUMN zhuke_material_projects.material_html_path IS
  'Relative path under FILES_DIR/zhuke_materials/{id}/ for interactive course HTML';
COMMENT ON COLUMN zhuke_material_projects.ppt_path IS
  'Relative path for generated PPTX from DeepSeek ppt_deck';
