# EduSymphony - 多智能体协作教案生成平台

5 位 AI 教学专家（教案优化、学生参与、创新教学、深度学习、认知发展）围绕三大教学理论对教案进行深度讨论与投票，产出最优融合教案。

## 核心特性

- **三大教学理论融合**：5E 教学模型、BOPPPS 教学模型、PBL 项目式学习三者融合为一份完整教案，而非分开生成
- **多智能体教研讨论**：5 位 AI 专家分别对 16 个教学环节（5E×5 + BOPPPS×6 + PBL×5）独立分析、逐条互评投票、给出赞成/反对理由
- **快速生成模式**：输入主题即可直接生成初步教案，跳过多轮讨论，适合快速使用场景
- **流式实时生成**：初步教案、教研讨论、专家投票、优化教案全程流式传输，Socket.IO 推送实时更新
- **教学材料生成**：基于教案内容由**豆包两阶段**生成交互式 HTML 课程演示页——Stage A 抽取 ≥6 个知识点 JSON，Stage B 由 Python 模板壳渲染（全屏/主题/导航/折叠/思考题/进度等交互 JS 由模板保证可用）；数学立体几何/化学反应仍优先走确定性 skill 路径；失败时 fallback 为豆包单轮 HTML（`material_*_engine` 字段标注通道）
- **专家桌面宠物舞台**：教案过程页左栏「教研宠物台」——五位专家（猫头鹰/狐狸/兔子/海豚/小猫）围坐讨论，跟随 `stream_*` / 投票事件切换发言、举手、欢呼；默认 SVG，可选 Seedream 精灵（`frontend/public/pets/`，用 `backend/scripts/gen_pet_sprites.py` 离线生成）
- **当地风格排版 PDF**：基于范本格式由 AI 生成排版精美的教案 HTML，支持后台运行
- **多 AI 模型支持**：Qwen（通义千问）、Kimi（月之暗面）、Doubao（豆包）、DeepSeek、Spark（讯飞星火）五家模型分配给五位专家
- **多地区适配**：支持澳门/香港繁体中文教案生成（含教青局基本学力要求等本地化结构）
- **国际化 (i18n)**：前端支持简体中文、繁体中文、英文切换，自动根据地区切换字体与语言
- **多用户隔离**：JWT 认证，每个用户只能看到和操作自己的教案，Socket.IO 按 lesson room 隔离推送
- **RBAC**：`users.access_level` 区分管理员与普通/受限用户；管理员在 Dashboard 可查看队列任务与用户维度信息；受限用户仅保留必要入口。部署需执行 `supabase_user_access_level_migration.sql`（见下方 SQL 顺序）；**可选**在 7 步完成后追加 `supabase_safe_run.sql` 做保守加固（不自动设管理员账号）。**勿在 README、截图或 Git 中粘贴生产账号、密码或完整连接串。**
- **细粒度功能开关**：每用户 8 个 `can_*` 布尔列（`can_course_tools` / `can_template_fill` / `can_university` / `can_series` / `can_next_lesson` / `can_export` 默认 TRUE；`can_semester_helper` / `can_zhuke_materials` 默认 FALSE）；管理员页可逐项勾选/取消，后端 `require_capability(flag)` 守卫 + 前端 `CapabilityRoute` 同步校验；admin（`lzf` / `ys`）始终自动绕过所有 `can_*` 检查
- **学期材料小助手 + 珠科教案助手**：`/semester-helper` 学期材料小助手模块（hub），子模块 `/semester-helper/zhuke` 珠科教案助手 —— 上传珠科教学日历 xlsx/docx → Kimi 逐节生成教案 → 组 docx/pdf（详见该模块实现与 `supabase_semester_helper_capability.sql`）
- **珠科材料助手（工作台独立入口）**：`/zhuke-materials` —— 与珠科教案助手分离；按 skill 流水线生成**教学大纲 + 教学日历 + 教案**，并可一键由 DeepSeek 再生成**交互式教学材料 HTML + PPTX**（服务端 `python-docx` / `openpyxl` / `python-pptx`）。需 `can_zhuke_materials`（默认关）与 `DEEPSEEK_API_KEY`；模版在 `backend/templates/zhuke_materials/`；执行 `supabase_zhuke_materials_migration.sql`，已有项目表再执行 `supabase_zhuke_materials_assets_migration.sql`
- **软删除全表覆盖**：`lesson_plans` / `lesson_series` / `document_versions` / `export_records` 四张表全部走 `deleted_at` 软删除；普通用户列表默认隐藏；管理员通过 `?include_deleted=true` 仍可查看与恢复
- **完整导出留痕**：所有下载/导出按钮点击（教案 JSON/TXT/MD/DOCX/PDF、教学材料、排版 PDF、模板填写、课程工具产物、珠科教案 docx/pdf、客户端直连下载）都记入 `export_records`；管理员可在用户详情页查看、下载或删除任意用户的导出历史
- **云端数据库**：Supabase PostgreSQL 托管存储 + 本地文件存储，asyncpg 驱动 + 连接池自适应（直连 / Transaction Pooler 自动切换）
- **系统公告 Banner**：顶部全站公告，可通过 `BANNER_TEXT` 环境变量一键配置
- **Postgres 持久化任务队列**：队列落盘至 `queue_jobs` 表（`SELECT FOR UPDATE SKIP LOCKED`），支持重启恢复、多实例横向扩展、单用户并发上限、lease/sweeper 自动回收超时任务，Socket.IO 实时推送排队位置
- **课程工具模块**：基于教案/大纲自动生成 PPT、习题、课堂练习，内置多个子工具（Outline / PPT / Exercises / Practice / 知识漫画 / 英语卡片）。其中 PPT 走**本地两阶段豆包深度生成**：先生成 15-25 页结构化大纲，再以 8 并发为每页生成富文本 bullets + 主讲稿，最后由 `python-pptx` 用 12 种内置版式渲染（不依赖任何第三方 PPT 插件，完全可控）；另提供 **HTML 网页版 PPT + 在线预览**（guizang 风格多套「版式体系」主题）
- **知识漫画 & 英语学习卡片**：`知识漫画` 由 AI 产出分镜脚本并渲染为自包含交互 HTML；`英语学习卡片` 生成结构化单词卡 HTML。二者均支持**豆包 Seedream 文生图配图**（`DOUBAO_IMAGE_MODEL` 开启时按分镜/单词并发生成 base64 图片内嵌，关闭时优雅降级为纯文本）
- **导出/下载付费闸门**：普通用户导出/下载材料前需消耗导出额度（`users.export_credits`）；管理员 `lzf`/`ys` 与白名单（`export_pay_exempt`）豁免。充值走 **扫码 +「我已支付」→ 临时额度 + 邮件通知管理员确认/改额度**（详见「付费闸门」章节）
- **教案可见性分级**：除管理员 `ys`/`lzf` 外，其他用户在**优秀教案生成完成前看不到初步教案**（含快速模式），也不能导出；原初步教案位置改为展示教学环节、AI 教师意见/投票、教案信息、支架式教学，以及点击环节时的详情结果，并单独提供「专家分析」右侧详情 Tab
- **教材接地（ChinaTextbook）**：创建教案时可级联选择「学段 / 学科 / 版本 / 教材 / 章节」，作为 `lesson_plans.textbook_ref` 注入生成上下文（仅内置目录元数据 + 外链，不分发教材文件）
- **通用 AI 教师标准 + K12 + 特殊教育**：所有内容生成 agent 注入统一「AI 教师标准」基线；K12 教案叠加 K12 教学法（对齐国内课标）；识别到特教场景自动叠加特殊教育教案专项标准
- **学科增强 skill**：数学立体几何（SymPy 精确求解 + Three.js 3D 演示，支持「上传题目图片解题」多模态入口）；化学反应（确定性反应内核 + 微观 3D 反应演示）
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
│   ├── app/services/                AI 服务、PPT、模板填写、material_html_service（教学材料豆包两阶段）等
│   ├── scripts/                     运维/测试脚本
│   │   ├── smoke_all_features.py    全栈冒烟（API + 可选 Playwright UI）
│   │   └── smoke_config.example.env 冒烟环境变量示例
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
├── supabase_user_feature_flags_migration.sql 每用户 6 个 can_* 功能开关（默认 TRUE）
├── supabase_soft_delete_migration.sql 4 张表追加 deleted_at + 8 个 partial 索引（仅活跃行）
├── supabase_export_records_perf_indexes.sql admin 查询用户导出列表加速（kind/status × created_at DESC）
├── supabase_semester_helper_capability.sql 学期材料小助手开关 can_semester_helper（默认 FALSE）
├── supabase_zhuke_export_index.sql  珠科教案 /zhuke/history 查询的 partial index（可选，性能优化）
├── supabase_export_payment_migration.sql 付费闸门（users.export_credits/export_pay_exempt + payment_orders）
├── supabase_textbook_ref_migration.sql 教材接地（lesson_plans.textbook_ref）
├── supabase_zhuke_materials_migration.sql 珠科材料助手（can_zhuke_materials + zhuke_material_projects）
├── supabase_zhuke_materials_assets_migration.sql 珠科材料→HTML/PPT 列（material_html_path / ppt_path 等）
├── backend/templates/zhuke_materials/ 珠科材料助手官方模版（大纲/日历/教案）
├── deploy.ps1 / deploy.bat / deploy.sh 一键全栈部署脚本（Windows / Linux）
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
> **（可选）第 9-12 步 — 新模块/能力同步（按需追加，均幂等可重跑）**  
> 9. `supabase_user_feature_flags_migration.sql` —— 为 `users` 追加 6 个 `can_*` 布尔列（默认 TRUE），驱动管理员页的逐项功能开关  
> 10. `supabase_soft_delete_migration.sql` —— 为 `lesson_plans` / `lesson_series` / `document_versions` / `export_records` 追加 `deleted_at` + 8 个 partial 索引（仅活跃行）  
> 11. `supabase_export_records_perf_indexes.sql` —— admin 查询用户导出列表的两条加速索引（`user+source_kind+created` / `user+status+created`，仅 `deleted_at IS NULL`）  
> 12. `supabase_semester_helper_capability.sql` —— 学期材料小助手开关 `users.can_semester_helper`（默认 FALSE，仅 admin 自动绕过；其他用户需管理员手动勾选才能看到入口）  
> 13. `supabase_zhuke_export_index.sql` —— **可选**：珠科教案 `/zhuke/history` 查询的两条 partial index（按 `source_kind='zhuke_generation'` 过滤，比通用索引小 90%+），用户量大时建议执行  
> 14. `supabase_export_payment_migration.sql` —— **付费闸门**：为 `users` 追加 `export_credits`（INT，默认 0）+ `export_pay_exempt`（BOOL，默认 false），并建 `payment_orders` 订单表 + 索引  
> 15. `supabase_textbook_ref_migration.sql` —— **教材接地**：为 `lesson_plans` 追加 `textbook_ref`（VARCHAR(300)），记录所选 ChinaTextbook 教材/章节  
> 16. `supabase_zhuke_materials_migration.sql` —— **珠科材料助手**：`users.can_zhuke_materials`（默认 FALSE）+ 表 `zhuke_material_projects`  
> 17. `supabase_zhuke_materials_assets_migration.sql` —— 珠科材料「教学材料 HTML + PPT」产物列（已有第 16 步表结构时补跑）  
>
> （若从零建库直接跑最新 `supabase_schema.sql`，已含能力列、付费表与 `zhuke_material_projects`；上述迁移用于**已有库增量升级**。）  
> **升级检查**：已有库若未跑第 **16** 步，后端会因缺 `users.can_zhuke_materials` 在 startup 失败——请立刻执行 `supabase_zhuke_materials_migration.sql`。启用「生成教学材料与 PPT」前再跑第 **17** 步。  
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

> **珠科教案长任务**：`--reload` 会在保存 backend 代码时 kill 正在跑的 worker，导致任务卡在「排队中」。测试完整 16 节生成时建议不加 `--reload`：
> `uvicorn app.main:socket_app --host 0.0.0.0 --port 3002`

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
- 必须先在 Supabase 按「快速开始」跑完 SQL（至少核心 1–7 步）；**已有库升级务必执行第 16 步** `supabase_zhuke_materials_migration.sql`（缺 `can_zhuke_materials` 会导致后端无法启动）
- **建议**再执行一次可选的 **`supabase_safe_run.sql`** 做 `access_level` 保守加固（见第 8 步说明）
- 单容器构建见根目录 `Dockerfile`：需 **BuildKit**；Coolify / CI 失败时可 `DOCKER_BUILDKIT=1 docker compose -f docker-compose.coolify.yml build --no-cache`
- `DATABASE_URL` 推荐 Transaction Pooler (端口 6543) 以获得最佳并发
- 多实例横向扩容时，`queue_jobs` 表自动在实例间分派任务（`SELECT FOR UPDATE SKIP LOCKED`），无需额外配置
- Coolify 更新镜像失败时，使用「Force rebuild (no cache)」避免 pip 层缓存

### 方式五：一键全栈部署脚本

仓库根目录提供一键脚本，自动起「前端 + 后端」全栈：

```bash
# Windows：双击 deploy.bat，或 PowerShell 执行
./deploy.ps1        # 自动检测并启动 Docker Desktop → docker compose up -d --build → 健康检查 → 打印访问地址

# Linux / 公网服务器
bash deploy.sh      # docker compose -f docker-compose.coolify.yml up -d --build → 等待就绪 → 打印地址
```

> 付费闸门无需额外服务：配置静态收款码 `ALIPAY_QR` / `WECHAT_QR` 与 SMTP，用户「我已支付」后邮件通知管理员确认额度即可。

## 环境变量 (`.env`)

本地从 `backend/` 启动时，配置写在 [`backend/.env`](backend/.env.example)（可自 [.env.example](.env.example) / [`backend/.env.example`](backend/.env.example) 复制）。使用 **docker compose** 时，Compose 读取**仓库根目录**的 [`.env`](.env.example)，键名与后端一致。前端本地开发可选变量见 [`frontend/.env.example`](frontend/.env.example)。

### AI 模型（至少配置一个）

| 变量 | 说明 |
|------|------|
| `QWEN_API_KEY` / `QWEN_MODEL` | 通义千问（默认分配给「教案优化专家」；默认 `qwen3.8-max`） |
| `QWEN_VL_MODEL` | 视觉/多模态模型（立体几何「上传题目图片解题」入口用），走同一 DashScope 兼容通道；默认 `qwen3.7-plus` |
| `DOUBAO_IMAGE_MODEL` | 文生图模型（英语卡片 / 知识漫画配图）。**留空 = 关闭配图**（仅出文本）；填 Seedream 模型 id 开启（已验证 `doubao-seedream-4-0-250828`），走豆包方舟 `/images/generations` 返回 base64 内嵌进 HTML |
| `KIMI_API_KEY` / `KIMI_MODEL` | Kimi（默认分配给「学生参与专家」；默认 `kimi-k2.6`） |
| `KIMI_K2_MODEL` | 珠科教案助手专用 Kimi 模型（默认回退 `KIMI_MODEL` / `kimi-k2.6`），与 `KIMI_API_KEY` 共用密钥 |
| `KIMI_K2_CONCURRENCY` | 珠科 `zhuke_lesson_single` 单用户并行 Kimi SubAgent 上限（默认 4，可在 `.env` 调高） |
| `KIMI_K2_TIMEOUT_SEC` | 珠科 Kimi 单次 API 超时（秒，默认 120） |
| `ZHUKE_LAYOUT_REVIEW_ON_LINT` | lint 失败时是否走 Kimi 排版质检（默认关） |
| `ZHUKE_LAYOUT_REVIEW_ALWAYS` | 强制每节都走排版质检（默认关；开启后 API 调用量翻倍） |
| `ZHUKE_LESSON_LEASE_SEC` | 珠科单课租约下限（秒）；实际取 `max(此值, TASK_TIMEOUT_SEC)`，默认 600 |
| `SOFFICE_PATH` | LibreOffice `soffice` 绝对路径（裸机 Windows/macOS；Docker 已内置，自动探测） |
| `DOUBAO_API_KEY` / `DOUBAO_MODEL` | 豆包 Chat（默认分配给「创新教学专家」，默认 `doubao-seed-2-1-pro-260628`；同时驱动课程工具的大纲/PPT/风格分析；PPT 走两阶段深度思考链路） |
| ~~`DOUBAO_PPT_BOT_ID` / `DOUBAO_PPT_BOT_TIMEOUT`~~ | **已弃用**。早期火山方舟 PPT 智能体路线已由本地两阶段豆包深度生成取代；该变量保留只为兼容现有 `.env`，配了也不会被读取 |
| ~~`COZE_API_KEY` / `COZE_BOT_ID` / `COZE_BASE_URL` / `COZE_PPT_TIMEOUT` / `COZE_POLL_INTERVAL`~~ | **已弃用**。Coze Bot 内置的 aippt 等第三方 PPT 插件返回的是营销页面 URL（不是真 .pptx 二进制），实测无法落地课堂可用文件，已从 `_do_ppt` 调用链中移除；保留环境变量字段仅为兼容已部署实例的 `.env`，配置不会再生效。未来如改走 Coze **Workflow** API（不是 Bot），会另起独立配置 |
| `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` | DeepSeek（默认分配给「深度学习专家」；默认 `deepseek-v4-pro`；珠科材料助手正文亦依赖此密钥） |
| `ZHUKE_MATERIALS_DEEPSEEK_MODEL` | 珠科材料助手专用模型（默认 `deepseek-v4-pro`；可用 flash 等覆盖） |
| `SPARK_API_KEY` / `SPARK_MODEL` | 讯飞星火（默认分配给「认知发展专家」；默认 `4.0Ultra`；若账号密钥鉴权不兼容可回退 `generalv3.5`） |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | OpenAI 兼容接口，可选 |

**模型默认值一览**（与 `config.py`、`.env.example`、`docker-compose*.yml` 的 `${VAR:-default}` 一致）：

| 变量 | 默认 |
|------|------|
| `QWEN_MODEL` | `qwen3.8-max` |
| `QWEN_VL_MODEL` | `qwen3.7-plus` |
| `KIMI_MODEL` / `KIMI_K2_MODEL` | `kimi-k2.6` |
| `DOUBAO_MODEL` | `doubao-seed-2-1-pro-260628` |
| `DEEPSEEK_MODEL` / `ZHUKE_MATERIALS_DEEPSEEK_MODEL` | `deepseek-v4-pro` |
| `SPARK_MODEL` | `4.0Ultra` |

Compose 会显式透传上表默认；仅填 API Key、不写模型名时也会落到这些 ID。无 V免签 / 无第三方自动支付服务。

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

> 未设置 env 时，代码按 Pooler/直连自适应默认值；Docker compose 见 `docker-compose.yml` / `docker-compose.coolify.yml` 中的 `${VAR:-default}`。

| 变量 | 说明 | 默认 |
|------|------|------|
| `MAX_CONCURRENT_TASKS` | 单进程内 worker 协程数 = 全局最大并发 AI 任务数 | 代码：Pooler **4** / 直连 **10**；compose **6** |
| `KIMI_K2_CONCURRENCY` | 珠科 `zhuke_lesson_single` 单用户并行 Kimi SubAgent 上限 | **4** |
| `MAX_PER_USER_TASKS` | 单用户并发任务数上限（防刷屏） | 代码：Pooler **2** / 直连 **3**；compose **4** |
| `TASK_TIMEOUT_SEC` | **默认档**单任务超时（秒）：export / material / styled_pdf 等 | 1200 |
| `LESSON_TASK_TIMEOUT_SEC` | **教案家族**超时（秒） | 3600 |
| `TOOL_TASK_TIMEOUT_SEC` | **课程工具**超时（秒） | 600 |
| `WORKER_LEASE_SEC` | worker 租约秒数；教案家族租约自动取 `max(WORKER_LEASE_SEC, LESSON_TASK_TIMEOUT_SEC+300)` | 1800 |
| `QUEUE_POLL_INTERVAL_MS` | 队列轮询间隔（毫秒），空闲时指数退避至 3s | 代码：Pooler **2000** / 直连 **1000**；compose **800** |
| `QUEUE_SWEEP_INTERVAL_SEC` | sweeper 扫描周期（秒） | 30 |
| `QUEUE_GC_DAYS` | 完成/失败 job 保留天数 | 代码 **7**；本地 compose **7**；Coolify compose **3** |

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

### 导出/下载付费闸门（扫码 + 邮件补额）

普通用户每次**导出/下载任何材料**前需消耗 1 次导出额度；管理员（`lzf` / `ys`）与被管理员标记 `export_pay_exempt=true` 的白名单账号**完全豁免**。到账方式见下方「付费闸门」章节。

| 变量 | 说明 | 默认 |
|------|------|------|
| `EXPORT_PRICE` | 单次订单金额（元） | 5 |
| `EXPORT_CREDITS_PER_ORDER` | 管理员确认后每笔订单补足到的正式额度 | 1 |
| `EXPORT_ORDER_TIMEOUT_SEC` | 前端提示用超时秒数 | 300 |
| `EXPORT_TEMP_CREDITS` | 「我已支付」后先发放的**临时额度**（等待人工核对） | 1 |
| `ALIPAY_QR` / `WECHAT_QR` | 支付宝 / 微信收款码内容（前端展示静态码） | 空 |
| `ADMIN_PAYMENT_EMAIL` | 「我已支付」后通知人工补额的收件邮箱 | `778636011@qq.com` |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` | 发件 SMTP（留空 = 跳过邮件，仅发临时额度） | `smtp.qq.com` / `465` / 空 / 空 |



## 付费闸门（导出/下载收费）

**谁需要付费**：普通用户。**豁免**：管理员 `lzf` / `ys`；以及管理员在用户管理页勾选 `export_pay_exempt` 的白名单账号。额度以 `users.export_credits` 记账，每次导出/下载扣 1；额度不足时后端返回 `402 Payment Required`，前端全局拦截并弹出 `PaymentModal`。

**到账流程**：前端展示静态收款码（`ALIPAY_QR` / `WECHAT_QR`）→ 用户支付后点「我已支付」→ `POST /payments/claim` 创建 `pending_review` 订单并立即发放 `EXPORT_TEMP_CREDITS` 临时额度，同时给 `ADMIN_PAYMENT_EMAIL` 发邮件 → 管理员核对后 `POST /payments/{id}/confirm` 或在用户管理里改 `export_credits`。同一用户存在未确认 `pending_review` 订单时不再重复发放。

**相关表/列**：`users.export_credits`、`users.export_pay_exempt`、`payment_orders`（执行 `supabase_export_payment_migration.sql`）。



## 并发、队列与数据库性能

- **Supabase PostgreSQL + Pooler**：连接池大小依据 `MAX_CONCURRENT_TASKS` 自适应（Pooler 模式默认 15+20，直连默认 10+10）。`pool_recycle=1800s` 自动回收、`pool_pre_ping` 检测僵死连接
- **服务端硬限制**：`statement_timeout` 与 `idle_in_transaction_session_timeout` 可通过 `DB_STATEMENT_TIMEOUT_MS` / `DB_IDLE_TX_TIMEOUT_MS` 环境变量调整
- **Postgres 持久化队列** (`backend/app/tasks/queue_manager.py`)：
  - 任务写入 `queue_jobs` 表，`SELECT FOR UPDATE SKIP LOCKED` 抢锁，天然支持**多进程 / 多实例共享**
  - 全局并发 `MAX_CONCURRENT_TASKS` + 单用户限流 `MAX_PER_USER_TASKS`
  - **按任务类型分档超时**：`_timeout_for_kind(kind)` 让教案家族用 `LESSON_TASK_TIMEOUT_SEC`（默认 3600s，防长任务误杀）、课程工具用 `TOOL_TASK_TIMEOUT_SEC`（默认 600s，快恢复）、其余用 `TASK_TIMEOUT_SEC`（1200s）
  - **租约 ≥ 超时**：认领 SQL 对教案家族取 `max(WORKER_LEASE_SEC, LESSON_TASK_TIMEOUT_SEC+300)` 作为 lease，避免 sweeper 在长教案仍在跑时提前回收导致重复执行
  - **worker claim 过滤**：只认领本实例已注册 handler 的 `kind`（`kind = ANY(:kinds)`），避免旧实例抢走新类型任务后报 no handler
  - **自恢复**：`WORKER_LEASE_SEC` + sweeper 循环自动回收 crashed worker 名额、GC 过期 job；启动 `_cleanup_stale_tasks_on_boot` 清僵尸；sweeper 每 30s 同步 `lesson_plans` / `course_tool_results`（pending/running 但队列已失败的行标失败），并跑 zhuke watchdog
  - **手动兜底**：`backend/scripts/clear_stuck_queue.py` 可一次性清理卡死的队列 job（覆盖 lesson 家族 + tool_* 含 comic/cards）
  - 重启后进行中的任务会被自动重新拉起（lease 过期后回到 queued）
  - `GET /api/v1/system/queue`（含 `get_stats`）返回各档超时与租约，便于排查
- **队列状态推送**：Socket.IO `queue_position` 事件实时推送排队位置与运行 / 排队数量
- **APScheduler**：线程池扩容至 10 workers，`misfire_grace_time=300s`
- **性能索引**：`supabase_perf_indexes.sql` + `supabase_queue_migration.sql` 覆盖 user/status/created_at、lesson/stage、course_tool、queue_jobs 等高频查询
- **游标分页**：`GET /api/v1/lessons?cursor=<ISO 时间>` 性能恒定 O(limit)，替代大 OFFSET 深分页
- **横向扩容**：队列已持久化到 Supabase，直接启动多个后端容器/实例即可共享任务，无需 Redis

## 冒烟测试（API + 可选 UI）

仓库提供全栈冒烟脚本 [`backend/scripts/smoke_all_features.py`](backend/scripts/smoke_all_features.py)，默认 **dry-run**（不触发 AI 长任务入队），覆盖主要 API 路由与教学材料 HTML 质量校验；加 `--ui` 时用 Playwright 点击各页面关键按钮。

配置示例见 [`backend/scripts/smoke_config.example.env`](backend/scripts/smoke_config.example.env)（可复制到 `backend/` 旁或通过环境变量注入）。

```bash
cd backend

# 仅 API（约 30 秒，需后端 3002 已启动）
python scripts/smoke_all_features.py --dry-run --password YOUR_PASS

# API + UI 按钮（需前端 3000 + Playwright）
pip install playwright
playwright install chromium
python scripts/smoke_all_features.py --dry-run --ui --password YOUR_PASS --lesson-id <uuid>

# 输出 smoke_report.json；有任何 FAIL 时 exit code = 1
```

也可通过环境变量：`SMOKE_BASE_URL`、`SMOKE_FRONTEND_URL`、`SMOKE_USER`、`SMOKE_PASS`、`SMOKE_LESSON_ID`。

## 环境要求

- Python 3.11+（推荐 Conda 独立环境；`pip` 可使用阿里云等国内镜像加速，与 [`backend/requirements.txt`](backend/requirements.txt) 一致）
- Node.js 18+
- 一个 Supabase 项目（免费版即可）
- 至少配置一个 AI 模型的 API Key
- **Docker（可选，用于方式三 / 四）**：Docker Engine **24+**（或旧版需开启 **BuildKit**）、**Compose V2**（`docker compose`）；镜像构建建议 **4GB+** 内存；Windows 推荐 Docker Desktop + **WSL2**
- **LibreOffice（珠科教案 PDF 必须）**：珠科教案助手的 docx → pdf 真格式转换需要系统 `soffice` 可执行文件。**Docker 用户无需操作** —— `docker compose build` 时 `backend/Dockerfile` 和根 `Dockerfile` 会通过 apt 自动安装 `libreoffice-writer` + 中文字体 3 件套，并在构建期执行 `soffice --version` 校验（装不上则 build 失败）；部署后可 `curl /health` 确认 `"libreoffice": true`。**仅本地裸跑 Windows / macOS** 需手动装（详见 [`backend/requirements.txt`](backend/requirements.txt) 顶部系统依赖说明）：
  - Windows (winget，推荐): `winget install --id TheDocumentFoundation.LibreOffice --accept-package-agreements --accept-source-agreements`
  - Windows (手动): 从 https://www.libreoffice.org/download/ 下载 LibreOffice Community 安装包（约 350MB），默认安装到 `C:\Program Files\LibreOffice\`，后端 `_find_soffice()` 会自动检测；装完不需重启后端，下次 PDF 请求即生效
  - macOS: `brew install --cask libreoffice`
  - Linux: `apt install libreoffice-writer fonts-wqy-zenhei fonts-noto-cjk`
  - 非默认路径：设置环境变量 `SOFFICE_PATH` 指向 `soffice` 可执行文件
  - 未装时 `/zhuke/{rid}/download?format=pdf` 返 503 + 中文 actionable 提示，前端 toast 原样显示；用户仍可下载 docx 后用 Word 自己另存为 PDF

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
| 学期材料小助手 | `/semester-helper` | 学期材料小助手 hub（受 `can_semester_helper` 控制；admin 默认绕过，其他用户需管理员勾选才显示） |
| 珠科教案助手 | `/semester-helper/zhuke` | 上传珠科教学日历 xlsx/docx → 解析封面+逐节主题 → Kimi K2.6 生成教学目标/重难点/教学过程 → 按珠科模板组装 docx/pdf 下载 |

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
| POST | `/api/v1/course-tools/comic` | 生成知识漫画（分镜脚本 → HTML；`with_images` 开启豆包配图） |
| POST | `/api/v1/course-tools/cards` | 生成英语学习卡片（结构化单词卡 HTML；`with_images` 开启豆包配图） |
| GET | `/api/v1/course-tools/history` | 历史记录列表 |
| GET | `/api/v1/course-tools/:id/download` | 下载生成文件（受付费闸门保护） |

### 付费/额度

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/payments/config` | 获取付费参数（金额、额度、收款码内容） |
| GET | `/api/v1/payments/:id/status` | 查询订单状态 |
| POST | `/api/v1/payments/claim` | 「我已支付」：发放临时额度 + 邮件通知人工补额 |
| POST | `/api/v1/payments/:id/confirm` | 管理员确认订单（人工补额） |
| POST | `/api/v1/payments/consume` | 前端客户端直连下载时消耗 1 次导出额度 |
| GET | `/api/v1/payments/orders` | 订单列表（管理员） |

### 珠科材料助手（工作台）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/zhuke-materials/ping` | 权限与 DeepSeek 配置心跳 |
| POST | `/api/v1/zhuke-materials/detect-mode` | 按文件名启发式判模式 A/B/C |
| POST | `/api/v1/zhuke-materials/projects` | 创建项目（课名 + 可选附件） |
| GET | `/api/v1/zhuke-materials/projects/:id` | 项目状态 / JSON 预览 |
| POST | `/api/v1/zhuke-materials/projects/:id/syllabus` | DeepSeek 大纲 + 填 docx |
| POST | `/api/v1/zhuke-materials/projects/:id/schedule` | 上课时间门禁（周几+节次） |
| POST | `/api/v1/zhuke-materials/projects/:id/calendar` | DeepSeek 周次 + 填 xlsx |
| POST | `/api/v1/zhuke-materials/projects/:id/lessons` | DeepSeek 教案 + 填 docx |
| GET | `/api/v1/zhuke-materials/projects/:id/download` | ZIP 三件套（受付费闸门） |

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
