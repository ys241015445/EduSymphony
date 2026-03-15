# 教案格式转换服务

将教案JSON转换为多种格式（HTML/DOCX/MD/TXT/PDF）

## 功能特点

- 接收教案JSON数据
- 基于PDF模版和Qwen API生成格式化HTML
- 支持导出多种格式：JSON、DOCX、Markdown、TXT、PDF
- 内存存储，无需数据库
- CORS支持，可跨域访问

## 安装依赖

```bash
pip install -r requirements.txt
```

注意：PDF转换需要额外的系统依赖：
- WeasyPrint需要GTK+、Pango、Cairo等库
- Windows用户可参考：https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows

## 配置

1. 复制 `.env.example` 为 `.env`
2. 填入Qwen API密钥：
   ```
   QWEN_API_KEY=sk-your-api-key
   ```

## 启动服务

```bash
python run.py
```

或

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

服务将在 http://localhost:8000 启动

## API端点

### 1. 接收教案

**POST** `/api/lesson-plans`

```json
{
  "metadata": {
    "type": "初步教案",
    "generatedAt": "2025-02-13T...",
    "generatedAtReadable": "2025/2/13 16:00:00",
    "courseTitle": "课程名称"
  },
  "content": "教案内容..."
}
```

### 2. 获取教案列表

**GET** `/api/lesson-plans`

### 3. 转换教案

**POST** `/api/convert`

```json
{
  "lesson_plan_id": "uuid",
  "template_pdf": "base64编码的PDF",
  "output_formats": ["json", "docx", "md", "txt", "pdf"]
}
```

### 4. 下载文件

**GET** `/api/download/{format}/{conversion_id}`

format可选：json、docx、md、txt、pdf

## 项目结构

```
lesson_format_service/
├── app/
│   ├── main.py              # FastAPI主应用
│   ├── models.py            # 数据模型
│   ├── services/
│   │   ├── qwen_service.py  # Qwen API调用
│   │   ├── converter.py     # 格式转换
│   │   └── storage.py       # 数据存储
│   └── routes/
│       ├── lesson_plans.py  # 教案路由
│       └── convert.py       # 转换路由
├── config.py                # 配置
├── run.py                   # 启动脚本
└── requirements.txt         # 依赖
```

## 开发者

黄海博士 • 钟丽霞博士 • 梁展帆团队
