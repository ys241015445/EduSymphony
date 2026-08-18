# 默认人培 / 模版 / 样例路径

Agent / 后端执行前确认文件存在；若用户上传新文件则覆盖下列默认值。

本仓库内模版根目录（相对 EduSymphony 项目根）：

```
backend/templates/zhuke_materials/
```

## 人培

用户上传优先。仓库不强制内置默认人培；未上传时 DeepSeek 上下文中的 `training_plan_excerpt` 可为空，由用户在向导中补课名/学时。

## 教学大纲模版

理论（可含实验章节）：

```
backend/templates/zhuke_materials/syllabus_theory.docx
```

纯实验：

```
backend/templates/zhuke_materials/syllabus_lab.docx
```

## 教学日历样例

理论：

```
backend/templates/zhuke_materials/calendar_theory.xlsx
```

实验：

```
backend/templates/zhuke_materials/calendar_lab.xlsx
```

## 教案

参考模版（复制用）：

```
backend/templates/zhuke_materials/lesson_plan.docx
```

详略样板说明见同目录 `README.md`（质量条对齐 `reference/quality-bar.md`）。

## DeepSeek

| 项 | 默认 |
|---|---|
| 模型 | `deepseek-v4-pro`（可用环境变量 `DEEPSEEK_MODEL` 覆盖） |
| 密钥 | `DEEPSEEK_API_KEY`（EduSymphony `backend/.env`） |
| 约定 | `reference/deepseek-contract.md` |
| 客户端 | 网页：`backend/app/services/zhuke_materials/deepseek_client.py`；CLI：`scripts/deepseek_generate.py` |

## 建议交付根目录

网页产物写入服务端用户数据目录（`DATA_DIR/files/zhuke_materials/<project_id>/`），经 `/api/v1/zhuke-materials/projects/{id}/download` 打包下载。

本地 Agent 交付可选：

```
<workspace>/zhuke_materials_out/<课名简写>/
```
