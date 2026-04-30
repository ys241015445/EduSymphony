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
- **RBAC**：`users.access_level` 区分管理员与普通/受限用户；管理员在 Dashboard 可查看队列任务与用户维度信息；受限用户仅保留必要入口。部署需执行 `supabase_user_access_level_migration.sql`（见下方 SQL 顺序）；**可选**在 7 步完成后追加 `supabase_safe_run.sql` 做保守加固（不自动设管理员账号）。**勿在 README、截图或 Git 中粘贴生产账号、密码或完整连接串。**
- **云端数据库**：Supabase PostgreSQL 托管存储 + 本地文件存储，asyncpg 驱动 + 连接池自适应（直连 / Transaction Pooler 自动切换）
- **系统公告 Banner**：顶部全站公告，可通过 `BANNER_TEXT` 环境变量一键配置
- **Postgres 持久化任务队列**：队列落盘至 `queue_jobs` 表（`SELECT FOR UPDATE SKIP LOCKED`），支持重启恢复、多实例横向扩展、单用户并发上限、lease/sweeper 自动回收超时任务，Socket.IO 实时推送排队位置
- **课程工具模块**：基于教案/大纲自动生成 PPT、习题、课堂练习，内置四个子工具（Outline / PPT / Exercises / Practice）。其中 PPT 走**本地两阶段豆包深度生成**：先生成 15-25 页结构化大纲，再以 8 并发为每页生成富文本 bullets + 主讲稿，最后由 `python-pptx` 用 12 种内置版式渲染（不依赖任何第三方 PPT 插件，完全可控）
- **大学年级专用页**：`/university` 专门面向大学教案，支持 1 节课 / 几周 / 一学期批量生成（Qwen）+ 可选课上练习/习题生成（DeepSeek），支持合并导出、按周打包 ZIP 导出
- **模板 AI 填写**：`/template-fill` 独立辅助工具 —— 上传 docx / pptx / xlsx / txt / md 模板 + 描述要生成的内容，Qwen 识别占位符（显式 `{{xxx}}` / `____` / `<xxx>` / `【xxx】` / `《xxx》`，否则 AI 自动识别），保留原排版填入，支持跨格式导出
- **灵活重新生成**：支持重新生成初步教案（清除后续讨论）、二次优化教案、重新生成单条专家建议（自动触发全环节重新投票）、重新生成单个教学环节
- **系列教案**：学期规划 & 下一课自动接续，教师反馈反哺后续教案
- **多格式导出**：JSON、TXT、Markdown、Word (.docx)、Excel (.xlsx)、PDF 等格式导出，支持中文文件名、合并导出与 ZIP 打包
- **后台任务不中断**：所有生成任务（教案、教学材料、排版 PDF、模板填写）均在服务端后台运行，刷新或离开页面不会中断

## 架构

```
EduSymphony/
├── frontend/                        React 18 + TypeScript + Vite + TailwindCSS + Zustand
├── backend/                         FastAPI + SQLAlchemy 2 (async) + asyncpg + Socket.IO + APScheduler
│   ├── app/api/                     REST 路由（auth / lessons / series / course_tools / system / export /
│   │                                         university / template_fill）
│   ├── app/tasks/                   队列管理 + AI 任务编排
│   │   ├── queue_manager.py         Postgres-backed 队列 + worker/sweeper
│   │   ├── job_handlers.py          kind → handler 注册表
│   │   └── lesson_task.py           教案多阶段生成流水线
│   ├── app/services/                AI 服务、PPT、模板填写等
│   └── database/                    本地文件存储（上传 / 生成产物，不含数据表）
├── supabase_schema.sql              Supabase 建表脚本（users / lesson_plans / discussions / 等核心业务表）
├── supabase_perf_indexes.sql        Supabase 性能优化索引（复合索引 + FK 索引 + ANALYZE）
├── supabase_queue_migration.sql     Postgres 持久化队列表 queue_jobs + 索引
├── supabase_university_migration.sql 大学页专用字段（lesson_series / lesson_plans 扩展列）
├── supabase_documents_migration.sql 文档版本与导出记录（document_versions / export_records）
├── supabase_course_tools_async_migration.sql 课程工具异步状态列（course_tool_results）
├── supabase_user_access_level_migration.sql RBAC（users.access_level）
├── supabase_safe_run.sql            可选：保守幂等加固 access_level + 索引（推荐生产复查）
├── supabase_admin_scope_migration.sql 可选：与管理员代管说明一致；含 RLS/PostgREST 提示与列校验
├── docker-compose.yml               本地开发双容器（backend + frontend）
├── docker-compose.coolify.yml       生产单容器（Nginx + Supervisor）
├── Dockerfile                       生产单容器 Dockerfile
├── backend/Dockerfile               后端开发镜像
└── start.bat                        Windows 一键启动
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

> **首次部署必须按顺序在 Supabase Dashboard → SQL Editor 执行**以下 SQL 脚本（幂等设计，**可重复执行**）：
> 1. `supabase_schema.sql` —— 核心业务表 + 触发器 + 教学模型种子数据
> 2. `supabase_perf_indexes.sql` —— 性能索引
> 3. `supabase_queue_migration.sql` —— 持久化任务队列 `queue_jobs`
> 4. `supabase_university_migration.sql` —— 大学页新增字段
> 5. `supabase_documents_migration.sql` —— 可编辑文档与导出记录表
> 6. `supabase_course_tools_async_migration.sql` —— 课程工具异步任务状态
> 7. `supabase_user_access_level_migration.sql` —— RBAC：`users.access_level`
>
> **（可选）第 8 步 — `access_level` 加固（二选一即可，均可重复执行）**  
> - **`supabase_safe_run.sql`（推荐）**：归一化非法值、补 CHECK/索引；**不会**批量把账号改成 `admin`。  
> - **`supabase_admin_scope_migration.sql`**：与管理员代管（应用层 `for_user_id`）对齐的说明 + 列存在校验；若库中缺少 `quota_remaining` 等会先报错，需先补齐主 schema。  
> 若已跑过第 7 步且仅需「保险再跑一遍」，优先 `supabase_safe_run.sql`。  
>
> **密钥与安全**：真实数据库连接串、AI Key、`JWT_SECRET` 等只放在部署环境的 `.env`（或密钥管理）中；仓库内 `config.py` 默认值与 `.env.example` 仅为占位。**不要将生产账号、密码或 Key 写入 README、Issue 或提交到 Git。**

### 方式一：Windows 一键启动

```bash
# 1. 安装后端环境（创建 .venv + pip install -r requirements.txt）
cd backend
setup.bat

# 2. 在 backend 目录编辑 .env，填入 AI Key 与 Supabase 连接串（勿提交到 Git）
notepad .env

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

若开发时前后端不同源或自定义 Socket 地址，可将 [`frontend/.env.example`](frontend/.env.example) 复制为 `frontend/.env` 或 `.env.local`，按需设置 `VITE_SOCKET_ORIGIN`、`VITE_DEV_BACKEND_PORT`；Docker 生产构建通常无需配置（Nginx 同源反代）。

### 方式三：Docker（本地 / 开发）

**Docker / Compose 环境要求**：

- **Docker Engine**：建议 **24+**（或 20.10+ 且已开启 **BuildKit**）。仓库根目录 [`Dockerfile`](Dockerfile) 使用 `COPY <<'EOF'` heredoc，**需要 BuildKit**；Docker Desktop 一般默认开启，Linux 可设 `DOCKER_BUILDKIT=1`。
- **Docker Compose**：使用 **V2** 插件命令 `docker compose`（非旧的独立二进制 `docker-compose`）。
- **构建资源**：前后端镜像同机构建建议预留约 **4GB+** 可用内存。
- **Windows**：推荐 Docker Desktop 并启用 **WSL2** backend。

Compose 从**仓库根目录**读取 `env_file: .env`。将根目录 [`.env.example`](.env.example) 复制为 `.env`（或与 [`backend/.env.example`](backend/.env.example) 保持相同键名），再填入占位符替换为你的真实值；**勿将填好的 `.env` 提交到版本库**。

```bash
cp .env.example .env                  # 编辑：AI Key、DATABASE_URL、JWT_SECRET 等
docker compose up -d                 # 浏览器访问前端 http://localhost:3002（映射到容器内 Nginx :80）
docker compose logs -f backend       # 后端日志（默认不对外暴露 8000，经前端反代 /api、/socket.io、/docs）
```

### 方式四：Coolify / 单容器生产部署

```bash
# 服务器上（Coolify 可视化也可）
docker compose -f docker-compose.coolify.yml up -d --build
# 单容器：Nginx + FastAPI + Supervisor，端口 80
```

**部署注意**：
- 必须先在 Supabase 按顺序跑完上述 **7** 个 SQL 脚本（见上方快速开始）；**建议**再执行一次可选的 **`supabase_safe_run.sql`** 做 `access_level` 保守加固（见第 8 步说明）
- 单容器构建见根目录 `Dockerfile`：需 **BuildKit**；Coolify / CI 失败时可 `DOCKER_BUILDKIT=1 docker compose -f docker-compose.coolify.yml build --no-cache`
- `DATABASE_URL` 推荐 Transaction Pooler (端口 6543) 以获得最佳并发
- 多实例横向扩容时，`queue_jobs` 表自动在实例间分派任务（`SELECT FOR UPDATE SKIP LOCKED`），无需额外配置
- Coolify 更新镜像失败时，使用「Force rebuild (no cache)」避免 pip 层缓存

## 环境变量 (`.env`)

本地从 `backend/` 启动时，配置写在 [`backend/.env`](backend/.env.example)（可自 [.env.example](.env.example) / [`backend/.env.example`](backend/.env.example) 复制）。使用 **docker compose** 时，Compose 读取**仓库根目录**的 [`.env`](.env.example)，键名与后端一致。前端本地开发可选变量见 [`frontend/.env.example`](frontend/.env.example)。

### AI 模型（至少配置一个）

| 变量 | 说明 |
|------|------|
| `QWEN_API_KEY` / `QWEN_MODEL` | 通义千问（默认分配给「教案优化专家」） |
| `KIMI_API_KEY` / `KIMI_MODEL` | Kimi（默认分配给「学生参与专家」） |
| `DOUBAO_API_KEY` / `DOUBAO_MODEL` | 豆包 Chat（默认分配给「创新教学专家」，同时驱动课程工具的大纲/PPT/风格分析；PPT 走两阶段深度思考链路） |
| ~~`DOUBAO_PPT_BOT_ID` / `DOUBAO_PPT_BOT_TIMEOUT`~~ | **已弃用**。早期火山方舟 PPT 智能体路线已由本地两阶段豆包深度生成取代；该变量保留只为兼容现有 `.env`，配了也不会被读取 |
| ~~`COZE_API_KEY` / `COZE_BOT_ID` / `COZE_BASE_URL` / `COZE_PPT_TIMEOUT` / `COZE_POLL_INTERVAL`~~ | **已弃用**。Coze Bot 内置的 aippt 等第三方 PPT 插件返回的是营销页面 URL（不是真 .pptx 二进制），实测无法落地课堂可用文件，已从 `_do_ppt` 调用链中移除；保留环境变量字段仅为兼容已部署实例的 `.env`，配置不会再生效。未来如改走 Coze **Workflow** API（不是 Bot），会另起独立配置 |
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
| `APP_ENV` / `APP_DEBUG` / `LOG_LEVEL` | 运行环境与日志级别（可选，见 `.env.example`） | development / true / INFO |
| `PDF_CJK_FONT_PATH` | PDF 导出用 CJK 字体绝对路径（可选） | 空 |

### 队列与并发（Postgres-backed）

| 变量 | 说明 | 默认 |
|------|------|------|
| `MAX_CONCURRENT_TASKS` | 单进程内 worker 协程数 = 全局最大并发 AI 任务数 | 8（compose 本地默认 5） |
| `MAX_PER_USER_TASKS` | 单用户并发任务数上限（防刷屏） | 3 |
| `TASK_TIMEOUT_SEC` | 单任务最长执行秒数（超时强制结束并释放名额） | 1200 |
| `WORKER_LEASE_SEC` | worker 租约秒数（crash 后 sweeper 回队重跑） | 1800 |
| `QUEUE_POLL_INTERVAL_MS` | 队列轮询间隔（毫秒），空闲时指数退避至 3s | 1000 |
| `QUEUE_SWEEP_INTERVAL_SEC` | sweeper 扫描周期（秒）—— 回收超时 lease + GC | 30 |
| `QUEUE_GC_DAYS` | 完成/失败 job 保留天数（超过被 sweeper 删除） | 7 |

### 数据库连接池（可选覆盖，留空使用代码自适应）

| 变量 | 说明 | 默认 |
|------|------|------|
| `DB_POOL_SIZE` | 主连接池大小 | Pooler 15 / 直连 10，或 `max(workers*2+5)` |
| `DB_MAX_OVERFLOW` | 池满时的弹性溢出数 | Pooler 20 / 直连 10 |
| `DB_POOL_TIMEOUT` | 检出连接的最长等待秒数 | 30 |
| `DB_POOL_RECYCLE` | 连接回收秒数（避免 Supabase 超时断链） | 1800 |
| `DB_STATEMENT_TIMEOUT_MS` | 服务端单条 SQL 超时（毫秒） | 120000 |
| `DB_IDLE_TX_TIMEOUT_MS` | 事务空闲超时（毫秒） | 300000 |
| `DB_COMMAND_TIMEOUT_SEC` | asyncpg 客户端单命令超时（秒） | 180 |



## 并发、队列与数据库性能

- **Supabase PostgreSQL + Pooler**：连接池大小依据 `MAX_CONCURRENT_TASKS` 自适应（Pooler 模式默认 15+20，直连默认 10+10）。`pool_recycle=1800s` 自动回收、`pool_pre_ping` 检测僵死连接
- **服务端硬限制**：`statement_timeout` 与 `idle_in_transaction_session_timeout` 可通过 `DB_STATEMENT_TIMEOUT_MS` / `DB_IDLE_TX_TIMEOUT_MS` 环境变量调整
- **Postgres 持久化队列** (`backend/app/tasks/queue_manager.py`)：
  - 任务写入 `queue_jobs` 表，`SELECT FOR UPDATE SKIP LOCKED` 抢锁，天然支持**多进程 / 多实例共享**
  - 全局并发 `MAX_CONCURRENT_TASKS` + 单用户限流 `MAX_PER_USER_TASKS`
  - `WORKER_LEASE_SEC` + sweeper 循环自动回收 crashed worker 名额、GC 过期 job
  - 重启后进行中的任务会被自动重新拉起（lease 过期后回到 queued）
- **队列状态推送**：Socket.IO `queue_position` 事件实时推送排队位置与运行 / 排队数量
- **APScheduler**：线程池扩容至 10 workers，`misfire_grace_time=300s`
- **性能索引**：`supabase_perf_indexes.sql` + `supabase_queue_migration.sql` 覆盖 user/status/created_at、lesson/stage、course_tool、queue_jobs 等高频查询
- **游标分页**：`GET /api/v1/lessons?cursor=<ISO 时间>` 性能恒定 O(limit)，替代大 OFFSET 深分页
- **横向扩容**：队列已持久化到 Supabase，直接启动多个后端容器/实例即可共享任务，无需 Redis

## 环境要求

- Python 3.11+（推荐 Conda 独立环境；`pip` 可使用阿里云等国内镜像加速，与 [`backend/requirements.txt`](backend/requirements.txt) 一致）
- Node.js 18+
- 一个 Supabase 项目（免费版即可）
- 至少配置一个 AI 模型的 API Key
- **Docker（可选，用于方式三 / 四）**：Docker Engine **24+**（或旧版需开启 **BuildKit**）、**Compose V2**（`docker compose`）；镜像构建建议 **4GB+** 内存；Windows 推荐 Docker Desktop + **WSL2**

## 数据库

### 建表与索引

在 Supabase Dashboard → SQL Editor 按顺序执行：

1. **表结构** —— `supabase_schema.sql`
   - 建立 7 张业务表：`users` / `lesson_plans` / `discussions` / `annotations` / `lesson_series` / `course_tool_results` / `teaching_models`
   - 内置 `teaching_models` 3 条种子数据（5E / BOPPPS / PBL）
   - `updated_at` 自动更新触发器

2. **性能索引** —— `supabase_perf_indexes.sql`
   - 复合索引（user+created、user+status+created、lesson+stage+created 等）
   - FK 专属部分索引（仅索引非 NULL 值）
   - 活跃状态部分索引（仅队列/处理中）
   - `ANALYZE` 刷新统计

3. **持久化队列** —— `supabase_queue_migration.sql`
   - 建表 `queue_jobs`（kind / target_id / user_id / status / priority / lease_expires_at 等）
   - 唯一部分索引（同一活跃 kind+target_id 去重）
   - 抢锁索引 `idx_queue_jobs_pick` 支持 `SELECT FOR UPDATE SKIP LOCKED`
   - 自动 VACUUM/ANALYZE 调优

4. **大学年级扩展** —— `supabase_university_migration.sql`
   - 为 `lesson_series` / `lesson_plans` 新增大学专用字段（专业、必修/选修、教学进度等）

5. **文档与导出** —— `supabase_documents_migration.sql`
   - `document_versions`、`export_records` 等（可编辑教案文档、导出记录）

6. **课程工具异步状态** —— `supabase_course_tools_async_migration.sql`
   - 为 `course_tool_results` 增加 `status` / `error_message` / `updated_at` 等

7. **RBAC** —— `supabase_user_access_level_migration.sql`
   - 为 `users` 增加 `access_level`（如管理员与普通/受限角色），与应用内权限判断一致

8. **（可选）`access_level` 加固** —— 与上方「快速开始」第 8 步相同：推荐 **`supabase_safe_run.sql`**；或 **`supabase_admin_scope_migration.sql`**（含代管/RLS 说明与校验）

所有脚本都是 `CREATE ... IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`，可**重复执行**，不会报错。

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
| 队列 | Supabase Postgres 持久化队列（`SELECT FOR UPDATE SKIP LOCKED`） |
| 导出 | python-docx, python-pptx, openpyxl, xhtml2pdf, pdfplumber, PyPDF2, html2text |
| 部署 | Docker Compose (本地双容器) / Coolify 单容器 (Nginx + Supervisor + Uvicorn) |

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
| 大学教案 | `/university` | 大学专用：单节/多周/整学期教案（Qwen）+ 可选习题实操（DeepSeek）+ 合并/分 ZIP 导出 |
| 模板 AI 填写 | `/template-fill` | 上传 docx/pptx/xlsx/txt/md 模板 + 描述内容，Qwen 识别占位符后填入，保留原排版，支持跨格式导出 |

右上角有 **语言切换器** (zh-CN / zh-TW / en)，所有 UI 文案 + AI 生成内容均会跟随切换；顶部有**系统公告 Banner**。

## API 端点

本地开发：后端在 3002 时访问 `http://localhost:3002/docs` 查看 Swagger。Docker Compose 双容器模式下，前端 Nginx 反代 `/docs` 到后端，请使用 `http://localhost:3002/docs`（与对外端口一致）；若单独暴露后端端口，再在宿主机选用自定义端口访问。

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/login` | 用户名 + 密码登录 |
| GET | `/api/v1/auth/me` | 当前用户信息 |

### 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/system/banner` | 获取系统公告 |
| GET | `/api/v1/system/queue` | 获取任务队列状态（运行中 / 排队 / 总并发上限） |
| GET | `/api/v1/system/queue/jobs` | 查看队列中所有 job（管理员） |
| GET | `/api/v1/system/queue/jobs/{target_id}` | 单个 job 状态详情 |
| GET | `/health` | 健康检查（含 DB 连接池状态 + 队列状态） |

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
| GET | `/api/v1/series/:id/export-merged` | 合并导出整个系列（单文件） |
| GET | `/api/v1/series/:id/export-zip` | 按周打包 ZIP 导出 |

### 模板 AI 填写

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/template-fill/analyze` | 上传模板并识别占位符 |
| POST | `/api/v1/template-fill/generate` | 依据用户意图调用 Qwen 生成并回填模板 |
| GET | `/api/v1/template-fill/history` | 查看最近填写历史 |
| GET | `/api/v1/template-fill/:result_id/download?fmt=docx\|pptx\|xlsx\|txt\|md\|pdf` | 以指定格式下载填好的文件 |

### 课程工具

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/course-tools/outline` | 生成课程大纲（学期 / 单课时） |
| POST | `/api/v1/course-tools/ppt/analyze-style/stream` | SSE 流式风格分析，返回 3 个模板候选（palette + layout_style + typography + cover_style） |
| POST | `/api/v1/course-tools/ppt` | 生成 PPT（**本地两阶段豆包深度生成**：① 第一阶段调用豆包 Chat 产出 15-25 页 PPT 大纲骨架，含每页布局/标题/聚焦点；② 第二阶段以 `_PPT_PAGE_CONCURRENCY=8` 并发为每一页深度生成富文本要点（25-50 字/条）+ 80-200 字主讲稿，再用 `python-pptx` 的 12 种内置版式本地渲染。`_engine` 字段标注通道：`doubao_two_stage` / `doubao_single_shot`（两阶段失败时回退） |
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
