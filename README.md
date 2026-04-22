# EduSymphony - 多智能体协作教案生成平台

5 位 AI 教学专家（教案优化、学生参与、创新教学、深度学习、认知发展）围绕三大教学理论对教案进行深度讨论与投票，产出最优融合教案。

## 核心特性

- **三大教学理论融合**：5E 教学模型、BOPPPS 教学模型、PBL 项目式学习三者融合为一份完整教案，而非分开生成
- **多智能体教研讨论**：5 位 AI 专家分别对 16 个教学环节（5E×5 + BOPPPS×6 + PBL×5）独立分析、逐条互评投票、给出赞成/反对理由
- **快速生成模式**：输入主题即可直接生成初步教案，跳过多轮讨论，适合快速使用场景
- **流式实时生成**：初步教案、教研讨论、专家投票、优化教案全程流式传输，Socket.IO 推送实时更新
- **教学材料生成**：基于教案内容由 AI 生成交互式 HTML 课程演示页面，支持后台运行，刷新页面不中断
- **当地风格排版 PDF**：基于范本格式由 AI 生成排版精美的教案 HTML，支持后台运行
- **多 AI 模型支持**：Qwen（通义千问）、Kimi（月之暗面）、Doubao（豆包）、DeepSeek、Spark（讯飞星火）五家模型分配给五位专家
- **多地区适配**：支持澳门/香港繁体中文教案生成（含教青局基本学力要求等本地化结构）
- **国际化 (i18n)**：前端支持简体中文、繁体中文、英文切换，自动根据地区切换字体与语言
- **多用户隔离**：JWT 认证，每个用户只能看到和操作自己的教案，Socket.IO 按 lesson room 隔离推送
- **云端数据库**：Supabase PostgreSQL 托管存储 + 本地文件存储，asyncpg 驱动 + 连接池自适应（直连 / Transaction Pooler 自动切换）
- **系统公告 Banner**：顶部全站公告，可通过 `BANNER_TEXT` 环境变量一键配置
- **任务队列 + 并发控制**：内存队列（可 Redis 扩展）+ Semaphore 限流，Socket.IO 实时推送排队位置
- **课程工具模块**：基于教案/大纲自动生成 PPT、习题、课堂练习，内置四个子工具（Outline / PPT / Exercises / Practice）
- **灵活重新生成**：支持重新生成初步教案（清除后续讨论）、二次优化教案、重新生成单条专家建议（自动触发全环节重新投票）、重新生成单个教学环节
- **系列教案**：学期规划 & 下一课自动接续，教师反馈反哺后续教案
- **多格式导出**：JSON、TXT、Markdown、Word (.docx)、PDF 五种格式导出，支持中文文件名
- **后台任务不中断**：所有生成任务（教案、教学材料、排版 PDF）均在服务端后台运行，刷新或离开页面不会中断

## 架构

```
EduSymphony/
├── frontend/                   React 18 + TypeScript + Vite + TailwindCSS + Zustand
├── backend/                    FastAPI + SQLAlchemy 2 (async) + asyncpg + Socket.IO + APScheduler
│   ├── app/api/                REST 路由（auth / lessons / series / course_tools / system / export）
│   ├── app/tasks/              队列管理 + AI 任务编排（lesson_task / queue_manager）
│   └── database/               本地文件存储（上传 / 生成产物，不含数据表）
├── supabase_schema.sql         Supabase 建表脚本（users / lesson_plans / discussions / 等 7 张表）
├── supabase_perf_indexes.sql   Supabase 性能优化索引（复合索引 + FK 索引 + ANALYZE）
├── docker-compose.yml          Docker 一键部署
└── start.bat                   Windows 一键启动
```

**前后端完全分离**：前端通过 HTTP API 和 WebSocket 与后端通信，本地开发用 Vite 代理，Docker 用 Nginx 代理。

## 教案生成流程

### 完整模式

```
教学信息上传
    ↓
Phase 1: 生成初步教案（融合 5E + BOPPPS + PBL 为一份完整文档）
    ↓
Phase 2: AI 教研讨论（按三大理论 × 各自环节 = 16 个阶段分别讨论）
    ├── Stage 1: 5 位专家独立分析建议（流式）
    ├── Stage 2: 5 位专家逐条互评投票 + 赞成/反对理由（流式）
    └── Stage 3: 主持人汇总投票、选出最佳建议、融合生成环节优化内容
    ↓
Phase 3: 生成优化教案（整合初步教案 + 各环节专家最佳建议为完整文档）
    ↓
可选: 生成教学材料 / 生成当地风格排版 PDF
```

### 快速模式

```
输入主题 → 生成初步教案 → 预览 → 下载 (JSON/TXT/MD/DOCX/PDF)
```

## 快速开始

> **首次部署必须先建表**：在 Supabase Dashboard → SQL Editor 执行 `supabase_schema.sql`，再执行 `supabase_perf_indexes.sql`（性能索引）。
>
> 两个脚本都是 `IF NOT EXISTS`，可重复执行。

### 方式一：Windows 一键启动

```bash
# 1. 安装后端环境（创建 .venv + pip install -r requirements.txt）
cd backend
setup.bat

# 2. 编辑 .env 填入 AI 模型 Key + Supabase 连接串
notepad backend\.env

# 3. 安装前端环境
cd ..\frontend
setup.bat

# 4. 回到根目录一键启动前后端
cd ..
start.bat
```

启动后访问（与 `frontend/vite.config.ts` 代理一致）：
- 前端：http://localhost:3000
- 后端 API / Socket.IO：http://localhost:3002
- API 文档：http://localhost:3002/docs

> 一键脚本会调用 `backend\dev_server.bat`，自动识别 **`.venv` 或 `venv`**，且必须使用 **`app.main:socket_app`** 才能启用实时进度。  
> 前端固定 **3000**（`strictPort: true`），避免 Vite 自动改用 **3002** 与后端抢端口。

### 方式二：分别启动

**后端（端口 3002）：**

```bash
cd backend
setup.bat                            # 首次运行：创建 .venv + 安装依赖
# Windows：双击 dev_server.bat，或：
.venv\Scripts\python.exe -m uvicorn app.main:socket_app --host 0.0.0.0 --port 3002 --reload
```

**前端（端口 3000，代理到 3002）：**

```bash
cd frontend
npm install                          # 首次运行
npm run dev                          # vite 固定 3000；/api 与 /socket.io 代理到 127.0.0.1:3002
```

### 方式三：Docker

```bash
cp .env.example .env                 # 编辑填入各 AI 模型的 API Key
docker compose up -d                 # 宿主机映射：前端 :3002 → 容器 80，后端 :8001 → 容器 8000
```

## 环境变量 (backend/.env)

### AI 模型（至少配置一个）

| 变量 | 说明 |
|------|------|
| `QWEN_API_KEY` / `QWEN_MODEL` | 通义千问（默认分配给「教案优化专家」） |
| `KIMI_API_KEY` / `KIMI_MODEL` | Kimi（默认分配给「学生参与专家」） |
| `DOUBAO_API_KEY` / `DOUBAO_MODEL` | 豆包（默认分配给「创新教学专家」） |
| `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` | DeepSeek（默认分配给「深度学习专家」） |
| `SPARK_API_KEY` / `SPARK_MODEL` | 讯飞星火（默认分配给「认知发展专家」） |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | OpenAI 兼容接口，可选 |

### 数据库与云服务

| 变量 | 说明 | 必填 |
|------|------|------|
| `DATABASE_URL` | Supabase PostgreSQL 连接串，支持**直连**/ **Session Pooler (5432)** / **Transaction Pooler (6543)** 三种，代码会根据 URL 自动适配 `statement_cache_size` | 是 |
| `SUPABASE_URL` | Supabase REST API base URL | 否 |
| `SUPABASE_ANON_KEY` | 匿名密钥（客户端用） | 否 |
| `SUPABASE_SERVICE_ROLE_KEY` | 服务端密钥（绕过 RLS） | 否 |

> **生产推荐**使用 Transaction Pooler (端口 6543)：每次 commit 后服务端连接立即归还，最适合长 AI 任务 + 高并发。切换只需改 `DATABASE_URL` 一行，代码无需任何修改。

### 应用配置

| 变量 | 说明 | 默认 |
|------|------|------|
| `JWT_SECRET` | JWT 签名密钥（生产环境必须更改） | — |
| `BANNER_TEXT` | 系统公告文本（留空不显示） | 空 |
| `MAX_CONCURRENT_TASKS` | 最大并发 AI 任务数 | 5 |

## 预置账号

系统启动时会自动创建以下账号（不开放注册）：

| 用户名 | 密码 |
|--------|------|
| lzf | lzf122406 |
| ys | yellowsea |
| zhkj | zhkj1234 |
| zhkj123 | zhkj123 |
| zhkj456 | zhkj456 |

## 并发、队列与数据库性能

- **Supabase PostgreSQL + Pooler**：默认 10 主池 + 10 溢出；Pooler 模式下扩展到 20 + 30。`pool_recycle=1800s` 自动回收、`pool_pre_ping` 检测僵死连接
- **服务端硬限制**：`statement_timeout=60s` 防慢查询、`idle_in_transaction_session_timeout=5min` 防空闲事务占连
- **任务队列**：内存队列管理器（`backend/app/tasks/queue_manager.py`），Semaphore 限制最多 `MAX_CONCURRENT_TASKS`（默认 5）个 AI 任务同时执行，超出自动排队
- **队列状态推送**：通过 Socket.IO `queue_position` 事件实时推送排队位置
- **APScheduler**：线程池扩容至 10 workers，`misfire_grace_time=300s`
- **性能索引**：`supabase_perf_indexes.sql` 新增 10 个复合索引 + FK 专属索引，覆盖 user/status/created_at、lesson/stage、course_tool 等高频查询
- **游标分页**：`GET /api/v1/lessons?cursor=<ISO 时间>` 性能恒定 O(limit)，替代大 OFFSET 深分页
- **Docker**：Uvicorn 4 workers，支持 20+ 并发用户

## 环境要求

- Python 3.11+
- Node.js 18+
- 一个 Supabase 项目（免费版即可）
- 至少配置一个 AI 模型的 API Key

## 数据库

### 建表与索引

1. **表结构**：在 Supabase Dashboard → SQL Editor 执行 `supabase_schema.sql`
   - 建立 7 张业务表：`users` / `lesson_plans` / `discussions` / `annotations` / `lesson_series` / `course_tool_results` / `teaching_models`
   - 内置 `teaching_models` 3 条种子数据（5E / BOPPPS / PBL）
   - `updated_at` 自动更新触发器

2. **性能索引**：再执行 `supabase_perf_indexes.sql`
   - 10 个复合索引（user+created、user+status+created、lesson+stage+created 等）
   - FK 专属部分索引（仅索引非 NULL 值）
   - 活跃状态部分索引（仅队列/处理中）
   - `ANALYZE` 刷新统计

两个脚本都是 `CREATE ... IF NOT EXISTS`，可**重复执行**，不会报错。

### 查看数据

- **Supabase Dashboard → Table Editor**：可视化浏览/编辑所有表
- **Supabase Dashboard → SQL Editor**：跑自定义 SQL、看执行计划
- **Supabase Dashboard → Reports → Query Performance**：慢查询与查询统计
- **Supabase Dashboard → Logs → Postgres Logs**：实时日志
- **Supabase Dashboard → Database → Pooler**：连接池监控

### 连接模式切换

代码自动检测 `DATABASE_URL`：

| 模式 | URL 特征 | 说明 |
|------|---------|------|
| 直连 | `db.xxx.supabase.co:5432` | 开发/单实例，连接数受 Supabase 项目上限 |
| Session Pooler | `pooler.supabase.com:5432` | 用户名格式 `postgres.PROJECT_REF`，保留 prepared statements |
| Transaction Pooler | `pooler.supabase.com:6543` | **生产推荐**，代码自动关闭 `statement_cache_size`，commit 后连接立即归还 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18, TypeScript, Vite 5, TailwindCSS 3, Zustand, Socket.IO Client, Framer Motion, Lucide Icons |
| 后端 | FastAPI, SQLAlchemy 2 (async), python-socketio, APScheduler, Pydantic 2 |
| 数据库 | Supabase PostgreSQL + asyncpg 驱动，自适应 Transaction Pooler |
| AI 模型 | Qwen / Kimi / Doubao / DeepSeek / Spark / OpenAI (OpenAI SDK 兼容接口) |
| 实时通信 | Socket.IO (WebSocket + 长轮询回退) |
| 认证 | JWT (PyJWT) + PBKDF2 密码哈希 |
| 导出 | python-docx, python-pptx, xhtml2pdf, pdfplumber |
| 部署 | Docker Compose (Nginx + Uvicorn 4 workers) |

## 前端页面

| 页面 | 路径 | 说明 |
|------|------|------|
| 首页 | `/` | 产品介绍，登录后显示快速生成入口 |
| 登录 | `/login` | 用户名 + 密码登录（无注册） |
| 教案列表 | `/dashboard` | 查看、删除已有教案，入口：快速生成 / 新建教案 / 课程工具 / 系列教案 |
| 创建教案 | `/lesson/new` | 填写教学信息（学科、年级、主题、地区、学生类别、需避免的问题等） |
| 快速生成 | `/quick-generate` | 输入主题直接生成初步教案，支持预览和多格式下载 |
| 教案生成过程 | `/lesson/:id/process` | 两栏布局：左侧教学环节状态与教案文档，右侧 AI 专家讨论与投票 |
| 教案结果 | `/lesson/:id/result` | 查看完整教案，导出多种格式 |
| 课程工具 | `/course-tools/:lessonId?` | 基于教案/大纲生成 PPT、习题、课堂练习、教学大纲四类内容 |
| 系列教案 | `/series` | 学期规划 & 批量生成同一课程系列 |

右上角有 **语言切换器** (zh-CN / zh-TW / en)，所有 UI 文案 + AI 生成内容均会跟随切换；顶部有**系统公告 Banner**。

## API 端点

本地开发：后端在 3002 时访问 `http://localhost:3002/docs` 查看 Swagger；Docker 映射为 `http://localhost:8001/docs`。

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/login` | 用户名 + 密码登录 |
| GET | `/api/v1/auth/me` | 当前用户信息 |

### 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/system/banner` | 获取系统公告 |
| GET | `/api/v1/system/queue` | 获取任务队列状态 |

### 教学模型

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/teaching-models` | 教学模型列表 |
| GET | `/api/v1/teaching-models/:id` | 教学模型详情 |

### 教案

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/lessons` | 创建教案并触发生成（支持 `mode=quick` 快速模式 / `generation_mode=semi_auto`） |
| GET | `/api/v1/lessons?limit=&offset=&cursor=` | 教案列表，推荐用 `cursor`（ISO 时间戳）分页 |
| GET | `/api/v1/lessons/:id` | 教案详情（含 final_content） |
| DELETE | `/api/v1/lessons/:id` | 删除教案 |
| POST | `/api/v1/lessons/:id/regenerate-draft` | 重新生成初步教案（清除讨论与优化） |
| POST | `/api/v1/lessons/:id/regenerate-optimized` | 二次优化教案 |
| POST | `/api/v1/lessons/:id/stages/:key/regenerate` | 重新生成单个教学环节 |
| POST | `/api/v1/lessons/:id/confirm-step` | 半自动模式：确认当前步骤继续下一阶段 |
| POST | `/api/v1/lessons/:id/feedback` | 提交教师反馈（供下一课使用） |
| POST | `/api/v1/lessons/:id/next-lesson` | 基于当前教案生成下一课教案 |

### 系列教案

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/series` | 创建学期课程系列 |
| GET | `/api/v1/series` | 列出全部系列 |
| GET | `/api/v1/series/:id` | 系列详情（含大纲） |
| POST | `/api/v1/series/:id/generate-syllabus` | 触发 AI 生成学期大纲 |
| POST | `/api/v1/series/:id/batch-generate` | 按大纲批量生成教案 |

### 课程工具

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/course-tools/outline` | 生成课程大纲（学期 / 单课时） |
| POST | `/api/v1/course-tools/ppt` | 生成 PPT（Doubao + python-pptx） |
| POST | `/api/v1/course-tools/exercises` | 生成习题 / 日常作业 |
| POST | `/api/v1/course-tools/practice` | 生成课堂练习 / 实操 |
| GET | `/api/v1/course-tools/history` | 历史记录列表 |
| GET | `/api/v1/course-tools/:id/download` | 下载生成文件 |

### 讨论

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/lessons/:id/discussions` | 专家讨论记录（含投票详情） |
| POST | `/api/v1/lessons/:id/discussions/:did/regenerate` | 重新生成单条建议并触发环节重新投票 |

### 批注

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/lessons/:id/annotations` | 添加批注 |
| GET | `/api/v1/lessons/:id/annotations` | 批注列表 |

### 导出

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/export/json/:id` | 导出 JSON |
| GET | `/api/v1/export/txt/:id` | 导出 TXT 纯文本 |
| GET | `/api/v1/export/markdown/:id` | 导出 Markdown |
| GET | `/api/v1/export/docx/:id` | 导出 Word 文档 (.docx) |
| GET | `/api/v1/export/pdf/:id` | 导出 PDF 文档 |
| POST | `/api/v1/export/styled-pdf/generate/:id` | 启动当地风格排版 PDF 生成（后台任务） |
| POST | `/api/v1/export/styled-pdf/html-to-pdf` | HTML 转 PDF 下载 |
| POST | `/api/v1/export/material/generate/:id` | 启动教学材料生成（后台任务） |

## Socket.IO 事件

| 事件 | 方向 | 说明 |
|------|------|------|
| `join_lesson` | 客户端→服务端 | 加入教案房间 |
| `leave_lesson` | 客户端→服务端 | 离开教案房间 |
| `progress_update` | 服务端→客户端 | 生成进度更新（阶段、百分比） |
| `stream_start` | 服务端→客户端 | 流式输出开始（phase: full_draft / analysis / expert_vote / vote_result / finalize / full_optimized） |
| `stream_chunk` | 服务端→客户端 | 流式文本片段 |
| `stream_end` | 服务端→客户端 | 流式输出完成 |
| `all_drafts_ready` | 服务端→客户端 | 初步教案生成完毕 |
| `discussion_update` | 服务端→客户端 | 投票完成通知（含 agree/disagree 计数） |
| `votes_saved` | 服务端→客户端 | 投票详情已保存至数据库 |
| `lesson_completed` | 服务端→客户端 | 教案生成全部完成 |
| `bg_task_complete` | 服务端→客户端 | 后台任务完成（教学材料 / 排版 PDF） |
| `queue_position` | 服务端→客户端 | 任务排队位置更新（position, status, running, queued） |

## AI 专家角色

| 专家 | 专长 | 默认模型 |
|------|------|----------|
| 教案优化专家 | 教学流程设计、目标对齐、教学方法优化 | Qwen |
| 学生参与专家 | 学生参与度、互动设计、学习体验提升 | Kimi |
| 创新教学专家 | 创新教学方法、项目式学习、现代教学技术 | Doubao |
| 深度学习专家 | 概念理解、知识迁移、深层次学习能力 | DeepSeek |
| 认知发展专家 | 认知发展规律、学习心理、差异化教学 | Spark |

所有专家均精通 5E、BOPPPS、PBL 三种教学理论。

## 讨论环节（16 个教学阶段）

| 理论 | 环节 |
|------|------|
| 5E 教学模型 | 引入(Engage)、探索(Explore)、解释(Explain)、拓展(Extend)、评价(Evaluate) |
| BOPPPS 教学模型 | 导入(Bridge-in)、目标(Objective)、前测(Pre-assessment)、参与式学习(Participatory)、后测(Post-assessment)、总结(Summary) |
| PBL 教学模型 | 问题情境、任务设计、实施过程、成果展示、反思评价 |
