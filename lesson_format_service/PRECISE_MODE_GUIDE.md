# 精确模式使用指南

## 快速开始

### 什么时候使用精确模式？

**使用精确模式的场景**：
- 需要像素级精确还原PDF格式
- 对行距、字间距、缩进有严格要求
- 正式文档、打印材料
- 格式要求极高的场景

**使用标准模式的场景**：
- 快速预览和测试
- 格式要求不高
- 对速度有要求
- 大批量处理

---

## 使用步骤

### 1. 准备材料

**PDF模板**：
- ✅ 使用文本型PDF（非扫描件）
- ✅ 结构清晰、布局规范
- ✅ 使用常见字体（微软正黑体、宋体等）

**JSON内容**：
```json
{
  "courseTitle": "旋轉對稱圖形",
  "teachingObjectives": "1. 理解旋轉對稱的概念...",
  "mainContent": "本節課主要學習...",
  "teachingMethods": "1. 講授法\n2. 討論法..."
}
```

### 2. 选择精确模式

在前端界面：
1. 选择教案
2. 上传PDF模板
3. 选择转换方案（智能选择/强制Qwen）
4. **选择精确度**：
   - ⚡ 标准模式（~1-2秒）- 基础样式
   - 🎯 **精确模式（~3-5秒）** - 像素级还原
5. 选择输出格式
6. 开始转换

### 3. 查看结果

系统会：
1. 提取PDF的精确样式（字体、字号、行距、字间距、缩进、对齐）
2. 将JSON内容映射到模板样式
3. 自动分页（如果内容超出）
4. 生成精确的HTML和其他格式

---

## 精确模式 vs 标准模式

### 样式还原对比

| 样式属性 | 标准模式 | 精确模式 |
|---------|---------|---------|
| 字体族 | ✅ | ✅ |
| 字号 | ✅ | ✅ |
| 颜色 | ✅ | ✅ |
| 对齐方式 | ✅ | ✅ |
| 行高 | 近似 | ✅ 精确 |
| 字间距 | ❌ | ✅ 精确 |
| 缩进 | 近似 | ✅ 精确 |
| 边距 | 默认 | ✅ 精确 |
| 位置坐标 | ❌ | ✅ 精确 |

### 性能对比

| 指标 | 标准模式 | 精确模式 |
|------|---------|---------|
| PDF解析 | 0.5秒 | 2秒 |
| 内容映射 | 0.5秒 | 1秒 |
| HTML生成 | 0.5秒 | 1秒 |
| 分页处理 | - | 1秒 |
| **总耗时** | **1.5秒** | **5秒** |

---

## 示例对比

### 示例1：标题样式

**PDF模板中的标题**：
- 字体：Microsoft JhengHei Bold
- 字号：24pt
- 对齐：居中
- 位置：距顶部100px

**标准模式输出**：
```html
<h1 style="font-family: Microsoft JhengHei; font-size: 24pt; text-align: center;">
    旋轉對稱圖形
</h1>
```

**精确模式输出**：
```html
<h1 style="
    font-family: 'Microsoft JhengHei', 'PMingLiU', sans-serif;
    font-size: 24pt;
    font-weight: 700;
    text-align: center;
    line-height: 28.8pt;
    letter-spacing: 0pt;
    color: rgb(0, 0, 0);
    margin-top: 100px;
">
    旋轉對稱圖形
</h1>
```

### 示例2：正文段落

**PDF模板中的段落**：
- 字体：Microsoft JhengHei
- 字号：14pt
- 行距：21pt
- 首行缩进：28pt (2字符)
- 对齐：两端对齐

**标准模式输出**：
```html
<p style="font-size: 14pt; text-align: justify; text-indent: 2em;">
    本節課主要學習旋轉對稱圖形的基本概念...
</p>
```

**精确模式输出**：
```html
<p style="
    font-family: 'Microsoft JhengHei', sans-serif;
    font-size: 14pt;
    line-height: 21pt;
    letter-spacing: 0.02pt;
    text-indent: 28pt;
    text-align: justify;
    color: rgb(0, 0, 0);
    margin-bottom: 10pt;
">
    本節課主要學習旋轉對稱圖形的基本概念...
</p>
```

---

## 自动分页示例

当JSON内容超过一页时，精确模式会自动分页：

```html
<div class="page">
    <h1>旋轉對稱圖形</h1>
    <h2>教學目標</h2>
    <p>1. 理解旋轉對稱的概念...</p>
    <p>2. 能夠識別...</p>
    <div class="page-break"></div> <!-- 自动插入分页符 -->
</div>

<div class="page">
    <h2>教學內容</h2>
    <p>本節課主要學習...</p>
</div>
```

---

## API使用示例

### JavaScript

```javascript
const response = await fetch('http://localhost:8000/api/convert', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        lesson_plan_id: "lesson-123",
        template_pdf: pdfBase64,
        output_formats: ["pdf", "docx"],
        method: "auto",
        precision: "precise"  // 使用精确模式
    })
});

const result = await response.json();
console.log(result.message); // "转换成功（使用pdf_parse_precise方案）"
```

### Python

```python
import requests
import base64

# 读取PDF
with open("template.pdf", "rb") as f:
    pdf_base64 = base64.b64encode(f.read()).decode()

# 调用API
response = requests.post(
    "http://localhost:8000/api/convert",
    json={
        "lesson_plan_id": "lesson-123",
        "template_pdf": pdf_base64,
        "output_formats": ["pdf", "docx"],
        "method": "auto",
        "precision": "precise"  # 使用精确模式
    }
)

result = response.json()
print(f"转换ID: {result['conversion_id']}")
```

---

## 常见问题

### Q1: 精确模式为什么这么慢？

**A**: 精确模式需要：
1. 提取PDF的每个字符位置和样式（~2秒）
2. 分析文本块的详细属性（~1秒）
3. 智能映射JSON内容到模板（~1秒）
4. 计算和应用自动分页（~1秒）

总共约5秒，是标准模式的3-4倍。

### Q2: 什么情况下精确模式会失败？

**A**: 以下情况可能失败，会自动降级到Qwen或标准模式：
- 扫描件PDF（无文本信息）
- 手写PDF
- 图片型PDF
- 加密或损坏的PDF

### Q3: 如何验证精确度？

**A**: 对比方法：
1. 打开原PDF和生成的PDF
2. 使用放大镜工具放大到200%
3. 对比字体、行距、缩进等细节
4. 精确模式应达到99%还原度

### Q4: 可以强制使用精确模式吗？

**A**: 是的，在前端选择：
- **转换方案**: 智能选择（推荐）
- **精确度**: 精确模式

如果PDF解析失败，系统会自动尝试Qwen AI。

### Q5: 精确模式支持哪些字体？

**A**: 支持所有系统已安装的字体，包括：
- 中文：微软正黑体、宋体、PMingLiU、黑体等
- 英文：Arial、Times New Roman、Calibri等
- 如果字体不存在，会降级到系统默认字体

---

## 最佳实践

### 1. PDF模板准备

✅ **推荐做法**：
- 使用Word等工具创建规范的教案模板
- 导出为PDF（文本型，非图片）
- 保持简洁的布局
- 使用常见字体

❌ **避免做法**：
- 使用扫描件
- 过于复杂的布局
- 使用稀有字体
- 包含大量图片和特效

### 2. JSON内容准备

✅ **推荐结构**：
```json
{
  "courseTitle": "课程标题",
  "teachingObjectives": "1. 目标1\n2. 目标2",
  "mainContent": "主要内容...",
  "teachingMethods": "教学方法...",
  "assessment": "评估方式..."
}
```

### 3. 性能优化

- 批量处理时使用标准模式
- 最终版本使用精确模式
- 利用缓存避免重复转换

### 4. 质量检查

转换后检查：
1. ✅ 字体是否正确
2. ✅ 行距是否合适
3. ✅ 缩进是否准确
4. ✅ 分页是否合理
5. ✅ 内容是否完整

---

## 技术支持

遇到问题？

1. 查看后端日志: `python run.py` 的输出
2. 检查PDF是否为文本型
3. 尝试使用标准模式
4. 如果仍然失败，会自动使用Qwen AI

---

**版本**: 2.0.0  
**更新日期**: 2026-02-12
