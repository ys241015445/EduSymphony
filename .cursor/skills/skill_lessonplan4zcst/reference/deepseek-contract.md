# DeepSeek 调用约定

正文一律由 DeepSeek 生成；本文件定义模型、提示要点与输出 JSON schema。Agent 只消费 JSON 并写入模版。

## API

| 项 | 值 |
|---|---|
| Base URL | `https://api.deepseek.com`（OpenAI 兼容 `/v1/chat/completions`） |
| 默认模型 | `deepseek-v4-pro`（当前最新旗舰；版本随官方滚动，调用 ID 不变即可用最新） |
| 备选 | `deepseek-v4-flash`（更快更省；设 `DEEPSEEK_MODEL`） |
| 密钥 | 环境变量 `DEEPSEEK_API_KEY`；可写入技能包旁本地 `.env`（勿提交仓库） |
| 输出 | 要求 **纯 JSON**（可开 `response_format: json_object`）；thinking 默认开启以提升结构质量 |

已废弃、勿再使用：`deepseek-chat`、`deepseek-reasoner`。

## 通用 system 约束（每次请求附上）

你是珠海科技学院教学材料撰写助手。只输出一个 JSON 对象，不要 Markdown 围栏，不要解释。内容须：

1. 与人培中的课名、学分、学时、目标口径一致；不得编造与人培冲突的学分/学时。
2. 语言为简体中文；教学用语规范，适合本科教案/大纲。
3. 学时切分自洽：章节学时之和 = 理论学时（或实验学时，按任务）；总学时 = 理论 + 实验。
4. 不生成教学日历「图片」正文；周次只给文字教学内容要点。
5. 教案过程须分时段（导入/精讲/演示/练习/小结等），详略达到可直接上课的粒度，勿空话套话。

## 任务与 schema

### `syllabus` — 教学大纲结构化正文

**输入上下文（user JSON）示例字段：** `course_name`, `course_code`, `credits`, `total_hours`, `theory_hours`, `lab_hours`, `training_plan_excerpt`, `textbook_toc`（可选）, `existing_outline_excerpt`（模式 A）, `template_hints`（附件3/4 字段名列表）

**输出：**

```json
{
  "course_name": "",
  "course_code": "",
  "credits": 0,
  "total_hours": 0,
  "theory_hours": 0,
  "lab_hours": 0,
  "course_nature": "",
  "applicable_major": "",
  "prerequisites": "",
  "course_objectives": ["", ""],
  "course_intro": "",
  "teaching_methods": "",
  "assessment": {
    "usual_percent": 0,
    "lab_percent": 0,
    "final_percent": 0,
    "notes": ""
  },
  "chapters": [
    {
      "no": 1,
      "title": "",
      "hours": 0,
      "theory_or_lab": "theory",
      "objectives": "",
      "content": "",
      "key_points": "",
      "difficulties": "",
      "methods_note": ""
    }
  ],
  "textbooks": [],
  "references": [],
  "other_notes": ""
}
```

字段名可按附件3/4 实际栏位微调，但 Agent 写入前须能映射到 `field-map.md`。

### `weeks` — 进度 / 日历周次教学内容

**输入：** 大纲 JSON 摘要、`theory_weeks` / `lab_weeks`、用户确认的上课时间、班级/课码等。

**输出：**

```json
{
  "meta": {
    "course_name": "",
    "course_code": "",
    "class_name": "",
    "schedule": "周X 第Y–Z节"
  },
  "theory_weeks": [
    {
      "week": 1,
      "hours": 2,
      "teaching_content": "",
      "chapter_ref": ""
    }
  ],
  "lab_weeks": [
    {
      "week": 1,
      "hours": 2,
      "teaching_content": "",
      "experiment_name": ""
    }
  ]
}
```

`teaching_content` 写入日历对应单元格；不要输出图片描述当作已填内容。

### `lessons` — 教案课次数组

**输入：** 某一批课次的日历格（周次、教学内容、学时、上课时间）、大纲目标、详略样板摘要（`quality-bar.md` 要点）。

**输出：**

```json
{
  "lessons": [
    {
      "unit_index": 1,
      "week": 1,
      "title": "",
      "class_hours": 2,
      "schedule_text": "",
      "learning_situation": "",
      "objectives": "",
      "key_points": "",
      "difficulties": "",
      "methods_and_means": "",
      "process": [
        {
          "phase": "导入",
          "minutes": 5,
          "teacher_activity": "",
          "student_activity": "",
          "intent": ""
        }
      ],
      "homework": "",
      "reflection": "",
      "materials": ""
    }
  ]
}
```

一次请求课次过多时可分批；`unit_index` 全局递增，与日历逐格对齐。

## CLI

```bash
python scripts/deepseek_generate.py --task syllabus --context context.json --out syllabus.json
python scripts/deepseek_generate.py --task weeks --context context.json --out weeks.json
python scripts/deepseek_generate.py --task lessons --context context.json --out lessons.json
```

缺少密钥时脚本以非零退出码失败并打印明确错误，供 Agent 原样转告用户。
