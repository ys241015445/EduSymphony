-- EduSymphony 数据库初始化脚本
-- MySQL 8.0

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ========== 用户表 ==========
CREATE TABLE IF NOT EXISTS `users` (
  `id` CHAR(36) NOT NULL PRIMARY KEY COMMENT '用户ID（UUID）',
  `username` VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
  `email` VARCHAR(100) NOT NULL UNIQUE COMMENT '邮箱',
  `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希',
  `role` ENUM('free', 'personal', 'school') DEFAULT 'free' COMMENT '用户角色',
  `quota_remaining` INT DEFAULT 10 COMMENT '剩余配额',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  INDEX `idx_email` (`email`),
  INDEX `idx_role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ========== 教学模型表 ==========
CREATE TABLE IF NOT EXISTS `teaching_models` (
  `id` CHAR(36) NOT NULL PRIMARY KEY COMMENT '模型ID（UUID）',
  `name` VARCHAR(100) NOT NULL COMMENT '模型名称',
  `name_en` VARCHAR(100) COMMENT '英文名称',
  `description` TEXT COMMENT '模型描述',
  `type` ENUM('builtin', 'custom') DEFAULT 'builtin' COMMENT '模型类型',
  `config` JSON NOT NULL COMMENT '模型配置（stages等）',
  `applicable_subjects` JSON COMMENT '适用学科',
  `applicable_grades` JSON COMMENT '适用学段',
  `is_active` BOOLEAN DEFAULT TRUE COMMENT '是否启用',
  `usage_count` INT DEFAULT 0 COMMENT '使用次数',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  INDEX `idx_type` (`type`),
  INDEX `idx_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='教学模型表';

-- ========== 教案表 ==========
CREATE TABLE IF NOT EXISTS `lesson_plans` (
  `id` CHAR(36) NOT NULL PRIMARY KEY COMMENT '教案ID（UUID）',
  `user_id` CHAR(36) NOT NULL COMMENT '用户ID',
  `title` VARCHAR(200) NOT NULL COMMENT '教案标题',
  `subject` VARCHAR(50) NOT NULL COMMENT '学科',
  `grade_level` VARCHAR(50) NOT NULL COMMENT '学段',
  `specific_grade` VARCHAR(50) COMMENT '具体年级',
  `region` ENUM('mainland', 'hongkong', 'macau', 'taiwan') DEFAULT 'mainland' COMMENT '地区',
  `teaching_model_id` CHAR(36) NOT NULL COMMENT '教学模型ID',
  
  -- 任务状态
  `status` ENUM('draft', 'queued', 'processing', 'completed', 'failed') DEFAULT 'queued' COMMENT '任务状态',
  `progress` INT DEFAULT 0 COMMENT '进度（0-100）',
  `current_stage` INT DEFAULT 0 COMMENT '当前阶段（1,2,3）',
  `error_message` TEXT COMMENT '错误信息',
  
  -- 内容
  `source_type` ENUM('upload', 'manual') NOT NULL COMMENT '来源类型',
  `source_content` TEXT COMMENT '原始内容',
  `parsed_content` TEXT COMMENT '解析后内容',
  `final_content` JSON COMMENT '最终教案（结构化）',
  
  -- 时间戳
  `started_at` TIMESTAMP NULL COMMENT '开始时间',
  `completed_at` TIMESTAMP NULL COMMENT '完成时间',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`teaching_model_id`) REFERENCES `teaching_models`(`id`),
  INDEX `idx_user_status` (`user_id`, `status`),
  INDEX `idx_status` (`status`),
  INDEX `idx_subject_grade` (`subject`, `grade_level`),
  INDEX `idx_created_at` (`created_at` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='教案表';

-- ========== 讨论记录表 ==========
CREATE TABLE IF NOT EXISTS `discussions` (
  `id` CHAR(36) NOT NULL PRIMARY KEY COMMENT '讨论ID（UUID）',
  `lesson_plan_id` CHAR(36) NOT NULL COMMENT '教案ID',
  `stage` INT NOT NULL COMMENT '阶段（1,2,3）',
  `round` INT NOT NULL COMMENT '讨论轮次',
  `topic` VARCHAR(200) COMMENT '讨论主题',
  `agent_role` VARCHAR(100) NOT NULL COMMENT '专家角色',
  `opinion` TEXT NOT NULL COMMENT '观点内容',
  `votes` JSON COMMENT '投票结果 {"agree": 4, "disagree": 1, "details": [...]}',
  `pass_rate` DECIMAL(5,2) COMMENT '通过率',
  `is_accepted` BOOLEAN DEFAULT FALSE COMMENT '是否采纳',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  
  FOREIGN KEY (`lesson_plan_id`) REFERENCES `lesson_plans`(`id`) ON DELETE CASCADE,
  INDEX `idx_lesson_stage` (`lesson_plan_id`, `stage`, `round`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='讨论记录表';

-- ========== 参考资料表 ==========
CREATE TABLE IF NOT EXISTS `reference_materials` (
  `id` CHAR(36) NOT NULL PRIMARY KEY COMMENT '资料ID（UUID）',
  `title` VARCHAR(200) NOT NULL COMMENT '资料标题',
  `type` ENUM('theory', 'standard', 'case') NOT NULL COMMENT '资料类型',
  `subject` VARCHAR(50) COMMENT '学科',
  `grade_level` VARCHAR(50) COMMENT '学段',
  `region` VARCHAR(50) COMMENT '地区',
  `content` TEXT NOT NULL COMMENT '资料内容',
  `metadata` JSON COMMENT '元数据（作者、来源、标签等）',
  `is_public` BOOLEAN DEFAULT TRUE COMMENT '是否公开',
  `reference_count` INT DEFAULT 0 COMMENT '引用次数',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  
  INDEX `idx_type_subject_region` (`type`, `subject`, `region`),
  INDEX `idx_public` (`is_public`),
  FULLTEXT INDEX `idx_content` (`title`, `content`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='参考资料表';

-- ========== 地区配置表 ==========
CREATE TABLE IF NOT EXISTS `region_configs` (
  `id` CHAR(36) NOT NULL PRIMARY KEY COMMENT '配置ID（UUID）',
  `region_code` ENUM('mainland', 'hongkong', 'macau', 'taiwan') UNIQUE COMMENT '地区代码',
  `region_name` VARCHAR(50) COMMENT '地区名称',
  `language` VARCHAR(10) COMMENT '语言代码（zh-CN, zh-HK, zh-TW）',
  `use_traditional` BOOLEAN DEFAULT FALSE COMMENT '是否使用繁体字',
  `grade_levels` JSON COMMENT '学段命名',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='地区配置表';

-- ========== 地区案例表 ==========
CREATE TABLE IF NOT EXISTS `regional_cases` (
  `id` CHAR(36) NOT NULL PRIMARY KEY COMMENT '案例ID（UUID）',
  `region_code` VARCHAR(20) COMMENT '地区代码',
  `title` VARCHAR(200) COMMENT '案例标题',
  `description` TEXT COMMENT '案例描述',
  `content` TEXT COMMENT '案例内容',
  `subject` VARCHAR(50) COMMENT '学科',
  `grade_level` VARCHAR(50) COMMENT '学段',
  `teaching_model` VARCHAR(50) COMMENT '教学模型',
  `highlights` JSON COMMENT '亮点特色',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  
  INDEX `idx_region_subject` (`region_code`, `subject`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='地区案例表';

-- ========== 任务日志表 ==========
CREATE TABLE IF NOT EXISTS `task_logs` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '日志ID',
  `lesson_plan_id` CHAR(36) NOT NULL COMMENT '教案ID',
  `stage` INT COMMENT '阶段',
  `log_level` ENUM('INFO', 'WARNING', 'ERROR') DEFAULT 'INFO' COMMENT '日志级别',
  `message` TEXT NOT NULL COMMENT '日志消息',
  `details` JSON COMMENT '详细信息',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  
  FOREIGN KEY (`lesson_plan_id`) REFERENCES `lesson_plans`(`id`) ON DELETE CASCADE,
  INDEX `idx_lesson_created` (`lesson_plan_id`, `created_at` DESC),
  INDEX `idx_level` (`log_level`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务日志表';

-- ========== 插入初始数据 ==========

-- 插入地区配置
INSERT INTO `region_configs` (`id`, `region_code`, `region_name`, `language`, `use_traditional`, `grade_levels`) VALUES
(UUID(), 'mainland', '中国大陆', 'zh-CN', FALSE, '["小学", "初中", "高中", "大学"]'),
(UUID(), 'hongkong', '香港', 'zh-HK', TRUE, '["小一至小六", "中一至中六"]'),
(UUID(), 'macau', '澳门', 'zh-MO', TRUE, '["小学", "初中", "高中"]'),
(UUID(), 'taiwan', '台湾', 'zh-TW', TRUE, '["国小", "国中", "高中"]');

-- 插入内置教学模型（5E模型）
INSERT INTO `teaching_models` (`id`, `name`, `name_en`, `type`, `description`, `config`, `applicable_subjects`, `applicable_grades`) VALUES
('5e-model-001', '5E教学模型', '5E Instructional Model', 'builtin', 
 '基于建构主义学习理论的五阶段教学模式，适合理科教学',
 '{
   "stages": [
     {"key": "engage", "name": "引入阶段", "icon": "🎯", "color": "#1890ff", "duration_range": [5, 10]},
     {"key": "explore", "name": "探究阶段", "icon": "🔬", "color": "#52c41a", "duration_range": [15, 20]},
     {"key": "explain", "name": "解释阶段", "icon": "💡", "color": "#faad14", "duration_range": [10, 15]},
     {"key": "extend", "name": "拓展阶段", "icon": "🚀", "color": "#722ed1", "duration_range": [10, 15]},
     {"key": "evaluate", "name": "评价阶段", "icon": "✅", "color": "#eb2f96", "duration_range": [5, 10]}
   ]
 }',
 '["物理", "化学", "生物", "科学"]',
 '["小学", "初中", "高中"]');

-- 插入PBL模型
INSERT INTO `teaching_models` (`id`, `name`, `name_en`, `type`, `description`, `config`, `applicable_subjects`, `applicable_grades`) VALUES
('pbl-model-001', '项目式学习', 'Project-Based Learning', 'builtin',
 '以项目为导向的学习模式，强调学生主动探究和实践',
 '{
   "stages": [
     {"key": "problem", "name": "问题提出", "icon": "❓", "color": "#1890ff", "duration_range": [10, 15]},
     {"key": "plan", "name": "计划制定", "icon": "📋", "color": "#52c41a", "duration_range": [15, 20]},
     {"key": "practice", "name": "探究实践", "icon": "🛠️", "color": "#faad14", "duration_range": [25, 30]},
     {"key": "present", "name": "成果展示", "icon": "🎤", "color": "#722ed1", "duration_range": [15, 20]},
     {"key": "reflect", "name": "反思评价", "icon": "🤔", "color": "#eb2f96", "duration_range": [10, 15]}
   ]
 }',
 '["信息技术", "综合实践", "STEAM"]',
 '["初中", "高中"]');

-- 插入探究式学习模型
INSERT INTO `teaching_models` (`id`, `name`, `name_en`, `type`, `description`, `config`, `applicable_subjects`, `applicable_grades`) VALUES
('inquiry-model-001', '探究式学习', 'Inquiry-Based Learning', 'builtin',
 '以科学探究为核心的学习模式，培养学生的科学思维',
 '{
   "stages": [
     {"key": "question", "name": "提出问题", "icon": "❓", "color": "#1890ff", "duration_range": [5, 10]},
     {"key": "hypothesis", "name": "猜想假设", "icon": "💭", "color": "#52c41a", "duration_range": [10, 15]},
     {"key": "design", "name": "设计实验", "icon": "📐", "color": "#faad14", "duration_range": [15, 20]},
     {"key": "collect", "name": "收集数据", "icon": "📊", "color": "#722ed1", "duration_range": [20, 25]},
     {"key": "conclude", "name": "得出结论", "icon": "🎯", "color": "#eb2f96", "duration_range": [10, 15]}
   ]
 }',
 '["物理", "化学", "生物"]',
 '["初中", "高中"]');

SET FOREIGN_KEY_CHECKS = 1;

-- 完成初始化
SELECT '✅ 数据库初始化完成！' AS message;

