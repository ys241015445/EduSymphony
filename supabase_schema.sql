-- ============================================================
-- EduSymphony — Supabase (PostgreSQL) 完整建表脚本
-- 生成时间：2026-04-08
-- 说明：按依赖顺序建表，先建无外键的表，再建有外键的表
-- ============================================================

-- 启用 uuid 扩展（Supabase 默认已启用，保险起见加上）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 1. users — 用户表
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id          VARCHAR(36)  PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    username    VARCHAR(50)  NOT NULL,
    email       VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role        VARCHAR(20)  NOT NULL DEFAULT 'free',       -- free / personal / school
    quota_remaining INTEGER  NOT NULL DEFAULT 100,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email    UNIQUE (email)
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_users_email    ON users (email);

-- ============================================================
-- 2. teaching_models — 教学模型/理论表
-- ============================================================
CREATE TABLE IF NOT EXISTS teaching_models (
    id                  VARCHAR(36)  PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    name_en             VARCHAR(100),
    description         TEXT,
    model_type          VARCHAR(20)  NOT NULL DEFAULT 'builtin',  -- builtin / custom
    config              JSONB        DEFAULT '{}',
    applicable_subjects JSONB        DEFAULT '[]',
    applicable_grades   JSONB        DEFAULT '[]',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ============================================================
-- 3. lesson_plans — 教案表
-- ============================================================
CREATE TABLE IF NOT EXISTS lesson_plans (
    id                VARCHAR(36)  PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    user_id           VARCHAR(36)  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title             VARCHAR(200) NOT NULL,
    subject           VARCHAR(50)  NOT NULL,
    grade_level       VARCHAR(50)  NOT NULL,
    specific_grade    VARCHAR(50),
    region            VARCHAR(20)  DEFAULT 'mainland',
    teaching_model_id VARCHAR(36),
    topic             TEXT,
    avoid_issues      TEXT,
    student_type      VARCHAR(200),

    mode              VARCHAR(20)  NOT NULL DEFAULT 'full_auto',     -- full_auto / semi_auto
    status            VARCHAR(20)  NOT NULL DEFAULT 'queued',        -- draft / queued / processing / awaiting_confirmation / completed / failed
    progress          INTEGER      NOT NULL DEFAULT 0,
    current_stage     INTEGER      NOT NULL DEFAULT 0,
    current_phase     VARCHAR(50)  DEFAULT '',
    error_message     TEXT,

    parent_lesson_id  VARCHAR(36),
    teacher_feedback  TEXT,
    locale            VARCHAR(10)  NOT NULL DEFAULT 'zh-CN',
    sequence_id       VARCHAR(36),
    sequence_order    INTEGER,

    source_type       VARCHAR(20)  NOT NULL,                         -- text / file / url
    source_content    TEXT,
    parsed_content    TEXT,
    final_content     JSONB        DEFAULT '{}',

    started_at        TIMESTAMPTZ,
    completed_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lesson_plans_user_id   ON lesson_plans (user_id);
CREATE INDEX IF NOT EXISTS idx_lesson_plans_status    ON lesson_plans (status);
CREATE INDEX IF NOT EXISTS idx_lesson_plans_sequence  ON lesson_plans (sequence_id);

-- ============================================================
-- 4. discussions — 专家讨论/投票记录
-- ============================================================
CREATE TABLE IF NOT EXISTS discussions (
    id              VARCHAR(36)  PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    lesson_plan_id  VARCHAR(36)  NOT NULL REFERENCES lesson_plans(id) ON DELETE CASCADE,
    stage           INTEGER      NOT NULL,
    round           INTEGER      NOT NULL,
    topic           VARCHAR(200),
    agent_role      VARCHAR(100) NOT NULL,
    opinion         TEXT         NOT NULL,
    votes           JSONB        DEFAULT '{}',
    pass_rate       DOUBLE PRECISION,
    is_accepted     BOOLEAN      NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_discussions_lesson ON discussions (lesson_plan_id);

-- ============================================================
-- 5. lesson_series — 系列教案/学期规划
-- ============================================================
CREATE TABLE IF NOT EXISTS lesson_series (
    id               VARCHAR(36)  PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    user_id          VARCHAR(36)  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title            VARCHAR(200) NOT NULL,
    subject          VARCHAR(50)  NOT NULL,
    grade_level      VARCHAR(50)  NOT NULL,
    specific_grade   VARCHAR(50),
    region           VARCHAR(20)  DEFAULT 'mainland',
    total_weeks      INTEGER      NOT NULL DEFAULT 16,
    lessons_per_week INTEGER      NOT NULL DEFAULT 2,
    objectives       TEXT,
    quality_goals    TEXT,
    book_content     TEXT,
    syllabus         JSONB        DEFAULT '{}',
    status           VARCHAR(20)  NOT NULL DEFAULT 'draft',
    mode             VARCHAR(20)  NOT NULL DEFAULT 'full_auto',
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lesson_series_user ON lesson_series (user_id);

-- ============================================================
-- 6. annotations — 用户对教案章节的批注
-- ============================================================
CREATE TABLE IF NOT EXISTS annotations (
    id                 VARCHAR(36)  PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    lesson_plan_id     VARCHAR(36)  NOT NULL REFERENCES lesson_plans(id) ON DELETE CASCADE,
    user_id            VARCHAR(36)  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    section_key        VARCHAR(100) NOT NULL,
    content            TEXT         NOT NULL,
    request_regenerate BOOLEAN      NOT NULL DEFAULT false,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_annotations_lesson ON annotations (lesson_plan_id);

-- ============================================================
-- 7. course_tool_results — 课程工具生成记录（大纲/PPT/习题/练习）
-- ============================================================
CREATE TABLE IF NOT EXISTS course_tool_results (
    id          VARCHAR(36)  PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    user_id     VARCHAR(36)  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id   VARCHAR(36)  REFERENCES lesson_plans(id) ON DELETE SET NULL,
    tool_type   VARCHAR(20)  NOT NULL,                   -- outline / ppt / exercises / practice
    params      JSONB        DEFAULT '{}',
    result      JSONB        DEFAULT '{}',
    file_path   TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_course_tool_user    ON course_tool_results (user_id);
CREATE INDEX IF NOT EXISTS idx_course_tool_lesson  ON course_tool_results (lesson_id);
CREATE INDEX IF NOT EXISTS idx_course_tool_type    ON course_tool_results (tool_type);

-- ============================================================
-- 8. 预置种子数据 — 5 个初始账号
--    密码由应用层 PBKDF2 生成，这里留占位 hash，
--    实际部署时请用后端 seed 脚本或替换为真实 hash
-- ============================================================
-- INSERT INTO users (id, username, email, password_hash, role, quota_remaining)
-- VALUES
--   (uuid_generate_v4()::text, 'lzf',     'lzf@edu.local',     '<hash_lzf122406>',  'school', 9999),
--   (uuid_generate_v4()::text, 'ys',      'ys@edu.local',      '<hash_yellowsea>',  'school', 9999),
--   (uuid_generate_v4()::text, 'zhkj',    'zhkj@edu.local',    '<hash_zhkj1234>',   'school', 9999),
--   (uuid_generate_v4()::text, 'zhkj123', 'zhkj123@edu.local', '<hash_zhkj123>',    'school', 9999),
--   (uuid_generate_v4()::text, 'zhkj456', 'zhkj456@edu.local', '<hash_zhkj456>',    'school', 9999);

-- ============================================================
-- 9. 预置种子数据 — 内置教学模型
-- ============================================================
INSERT INTO teaching_models (id, name, name_en, description, model_type, config, applicable_subjects, applicable_grades)
VALUES
  ('tm-5e',     '5E教学模型',    '5e',     'Engage-Explore-Explain-Extend-Evaluate五阶段探究式教学',
   'builtin',
   '{"stages":["engage","explore","explain","extend","evaluate"],"agents":5,"discussion_rounds":3,"vote_threshold":0.6}',
   '["science","math","general"]',
   '["primary","middle","high"]'),

  ('tm-boppps', 'BOPPPS教学模型', 'boppps', 'Bridge-Objective-Pre-assessment-Participatory-Post-assessment-Summary六步教学法',
   'builtin',
   '{"stages":["bridge","objective","pre_assessment","participatory","post_assessment","summary"],"agents":5,"discussion_rounds":3,"vote_threshold":0.6}',
   '["general"]',
   '["primary","middle","high","college"]'),

  ('tm-pbl',    'PBL项目式学习',  'pbl',    'Problem-Based Learning项目式学习模型',
   'builtin',
   '{"stages":["problem_context","task_design","implementation","presentation","reflection"],"agents":5,"discussion_rounds":3,"vote_threshold":0.6}',
   '["general","stem"]',
   '["middle","high","college"]')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 10. updated_at 自动更新触发器
-- ============================================================
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER trg_lesson_plans_updated
    BEFORE UPDATE ON lesson_plans
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER trg_lesson_series_updated
    BEFORE UPDATE ON lesson_series
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- ============================================================
-- 11. Supabase RLS（行级安全）— 可选，按需开启
-- ============================================================
-- ALTER TABLE users              ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE lesson_plans       ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE discussions        ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE lesson_series      ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE annotations        ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE course_tool_results ENABLE ROW LEVEL SECURITY;

-- 示例策略：用户只能访问自己的教案
-- CREATE POLICY "users_own_lessons" ON lesson_plans
--   FOR ALL USING (user_id = auth.uid()::text);

-- ============================================================
-- Done. 共 7 张业务表 + 3 个触发器 + 种子数据
-- ============================================================
