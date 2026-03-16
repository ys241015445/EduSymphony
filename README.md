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
- **本地数据存储**：SQLite 数据库 + 本地文件存储，无需外部数据库服务
- **灵活重新生成**：支持重新生成初步教案（清除后续讨论）、二次优化教案、重新生成单条专家建议（自动触发全环节重新投票）、重新生成单个教学环节
- **多格式导出**：JSON、TXT、Markdown、Word (.docx)、PDF 五种格式导出，支持中文文件名
- **后台任务不中断**：所有生成任务（教案、教学材料、排版 PDF）均在服务端后台运行，刷新或离开页面不会中断

## 架构

```
EduSymphony_learningplan/
├── frontend/          React 18 + TypeScript + Vite + TailwindCSS + Zustand
├── backend/           FastAPI + SQLAlchemy (async) + Socket.IO + APScheduler
├── data/              本地持久化数据 (SQLite + 上传文件)
├── docker-compose.yml Docker 一键部署
└── start.bat          Windows 一键启动
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

### 方式一：Windows 一键启动

```bash
# 1. 安装后端环境
cd backend
setup.bat

# 2. 编辑 .env 填入各 AI 模型的 API Key
notepad backend\.env

# 3. 安装前端环境
cd frontend
setup.bat

# 4. 一键启动前后端
start.bat
```

启动后访问：
- 前端：http://localhost:3002
- 后端 API：http://localhost:8001
- API 文档：http://localhost:8001/docs

### 方式二：分别启动

**后端（端口 8001）：**

```bash
cd backend
setup.bat                            # 首次运行：创建 venv + 安装依赖
.venv\Scripts\python.exe -m uvicorn app.main:application --host 0.0.0.0 --port 8001 --reload
```

**前端（端口 3002）：**

```bash
cd frontend
npm install                          # 首次运行
npm run dev                          # 启动开发服务器（自动代理到后端 8001）
```

### 方式三：Docker

```bash
cp .env.example .env                 # 编辑填入各 AI 模型的 API Key
docker compose up -d                 # 前端 :3002，后端 :8001
```

## 环境变量 (.env)

| 变量 | 说明 | 必填 |
|------|------|------|
| `QWEN_API_KEY` | 通义千问 API Key | 至少填一个 |
| `QWEN_MODEL` | Qwen 模型名（默认 qwen-plus） | 否 |
| `KIMI_API_KEY` | Kimi（月之暗面）API Key | 至少填一个 |
| `KIMI_MODEL` | Kimi 模型名 | 否 |
| `DOUBAO_API_KEY` | 豆包 API Key | 至少填一个 |
| `DOUBAO_MODEL` | 豆包模型名 | 否 |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | 至少填一个 |
| `DEEPSEEK_MODEL` | DeepSeek 模型名 | 否 |
| `SPARK_API_KEY` | 讯飞星火 API Key | 至少填一个 |
| `SPARK_MODEL` | 星火模型名 | 否 |
| `OPENAI_API_KEY` | OpenAI API Key（可选） | 否 |
| `OPENAI_BASE_URL` | OpenAI 兼容 API 地址 | 否 |
| `JWT_SECRET` | JWT 签名密钥（生产环境必须更改） | 是 |

> 五个 AI 模型分别分配给五位专家。至少需要配置一个 API Key 才能使用。

## 环境要求

- Python 3.11+
- Node.js 18+
- 至少配置一个 AI 模型的 API Key

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18, TypeScript, Vite 5, TailwindCSS 3, Zustand, Socket.IO Client, Framer Motion, Lucide Icons |
| 后端 | FastAPI, SQLAlchemy 2 (async), python-socketio, APScheduler, Pydantic 2 |
| 数据库 | SQLite (aiosqlite) — 本地文件存储 |
| AI 模型 | Qwen / Kimi / Doubao / DeepSeek / Spark / OpenAI (OpenAI SDK 兼容接口) |
| 实时通信 | Socket.IO (WebSocket + 长轮询回退) |
| 认证 | JWT (PyJWT) + PBKDF2 密码哈希 |
| 导出 | python-docx, xhtml2pdf, pdfplumber |
| 部署 | Docker Compose (Nginx + Uvicorn) |

## 前端页面

| 页面 | 路径 | 说明 |
|------|------|------|
| 首页 | `/` | 产品介绍，登录后显示快速生成入口 |
| 登录/注册 | `/login` | JWT 认证 |
| 教案列表 | `/dashboard` | 查看、删除已有教案，快速生成 / 新建教案入口 |
| 创建教案 | `/lesson/new` | 填写教学信息（学科、年级、主题、地区、学生类别、需避免的问题等） |
| 快速生成 | `/quick-generate` | 输入主题直接生成初步教案，支持预览和多格式下载 |
| 教案生成过程 | `/lesson/:id/process` | 三栏布局：左侧教学环节状态、中间教案文档（初步/优化/教学材料）、右侧 AI 讨论与投票 |
| 教案结果 | `/lesson/:id/result` | 查看完整教案，导出多种格式 |

## API 端点

后端启动后访问 `http://localhost:8001/docs` 查看 Swagger 文档。

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册 |
| POST | `/api/v1/auth/login` | 登录 |
| GET | `/api/v1/auth/me` | 当前用户信息 |

### 教学模型

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/teaching-models` | 教学模型列表 |
| GET | `/api/v1/teaching-models/:id` | 教学模型详情 |

### 教案

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/lessons` | 创建教案并触发生成（支持 `mode=quick` 快速模式） |
| GET | `/api/v1/lessons` | 教案列表 |
| GET | `/api/v1/lessons/:id` | 教案详情（含 final_content） |
| DELETE | `/api/v1/lessons/:id` | 删除教案 |
| POST | `/api/v1/lessons/:id/regenerate-draft` | 重新生成初步教案（清除讨论与优化） |
| POST | `/api/v1/lessons/:id/regenerate-optimized` | 二次优化教案 |
| POST | `/api/v1/lessons/:id/stages/:key/regenerate` | 重新生成单个教学环节 |

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
