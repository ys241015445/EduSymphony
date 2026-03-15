# 使用指南 - 教案格式转换完整流程

## 完整工作流程

```
步骤1: 生成教案
update_lesson_plan.html
   ↓
保存JSON到本地 + 推送到后端
   ↓
步骤2: 转换格式
format_converter.html
   ↓
下载多种格式文件
```

## 详细步骤

### 一、启动后端服务

```bash
# 进入服务目录
cd lesson_format_service

# 首次使用：安装依赖
pip install -r requirements.txt

# 配置API密钥（复制并编辑.env文件）
copy .env.example .env
# 编辑.env，填入: QWEN_API_KEY=sk-your-key

# 启动服务
python run.py
```

看到 "Uvicorn running on http://0.0.0.0:8000" 表示启动成功。

### 二、生成教案（原系统）

1. 在浏览器打开 `update_lesson_plan.html`
2. 上传教案文件或手动输入教案内容
3. 选择地区、年级等参数
4. 生成初步教案
5. 等待专家讨论和优化（可选）

**自动推送**：
- 初步教案生成后，自动推送到后端
- 优化教案生成后，自动推送纯净版和标注版
- 控制台会显示：`✅ 教案已推送到格式转换服务，ID: xxx`

**本地保存**：
```
[你选择的文件夹]/
  └── [课程名_日期]/
        ├── 教案内容/
        │     ├── 初步教案.json          ← 新增
        │     ├── 第1轮优化_纯净版.json   ← 新增
        │     └── 第1轮优化_标注版.json   ← 新增
        ├── 讨论过程_投票_评分.json       ← 新增
        ├── 初步教案.txt
        └── ...
```

### 三、格式转换

1. 在浏览器打开 `format_converter.html`

2. **选择教案**
   - 从下拉列表选择要转换的教案
   - 显示格式：`课程名 - 教案类型 (生成时间)`

3. **上传模版**
   - 点击"上传格式模版（PDF）"
   - 选择标准格式的教案PDF（如：旋轉對稱圖形教案.pdf）
   - 此PDF将作为格式和样式参考

4. **选择格式**
   - 勾选需要的输出格式
   - JSON - 原始结构化数据
   - DOCX - Word文档
   - Markdown - Markdown格式
   - TXT - 纯文本
   - PDF - PDF文档

5. **开始转换**
   - 点击"开始转换"按钮
   - 等待Qwen API生成HTML（约5-15秒）
   - 查看HTML预览

6. **下载文件**
   - 点击对应格式的下载按钮
   - 文件自动下载到浏览器下载文件夹

## 工作原理

### 格式转换流程

```
1. 前端上传模版PDF（Base64编码）
   ↓
2. 后端调用Qwen多模态API
   - 输入1: PDF模版图片
   - 输入2: 教案文本内容
   - Prompt: 以PDF格式为参考，将内容生成HTML
   ↓
3. Qwen返回格式化的HTML
   ↓
4. 后端转换为多种格式
   - JSON: 直接返回原始数据
   - DOCX: python-docx库生成
   - MD: html2text转换
   - TXT: 去除HTML标签
   - PDF: WeasyPrint转换
   ↓
5. 前端提供下载链接
```

### 降级方案

**当Qwen API调用失败时**：
- 自动使用基础HTML模版
- 保留教案内容，仅缺少自定义格式
- 仍可正常下载各种格式

**当PDF转换失败时**：
- 使用打印对话框方式
- 用户手动选择"另存为PDF"

## 高级功能

### 1. 批量转换

可以在 `format_converter.html` 中添加多选功能，一次转换多个教案

### 2. 格式定制

修改 `app/services/converter.py` 中的转换逻辑：
- 自定义DOCX样式
- 调整PDF页边距
- 修改Markdown格式

### 3. API集成

其他系统可以直接调用API：

```javascript
// 推送教案
fetch('http://localhost:8000/api/lesson-plans', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(lessonData)
});

// 转换格式
fetch('http://localhost:8000/api/convert', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        lesson_plan_id: 'xxx',
        template_pdf: 'base64...',
        output_formats: ['docx', 'pdf']
    })
});
```

## 常见使用场景

### 场景1: 快速生成标准格式教案

1. 在原系统生成初步教案
2. 使用学校标准模版PDF转换
3. 下载DOCX，微调后提交

### 场景2: 对比不同版本

1. 转换初步教案
2. 转换第1轮优化_纯净版
3. 对比两份文档的差异

### 场景3: 制作演示文稿

1. 转换为Markdown
2. 使用Markdown编辑器（Typora）
3. 导出为演示文稿

## 性能优化建议

1. **缓存模版**：相同模版PDF可以在后端缓存
2. **并行转换**：同时转换多种格式
3. **压缩传输**：启用gzip压缩
4. **CDN加速**：静态资源使用CDN

## 故障排查

### 问题1: 教案列表为空
- 原因：后端未收到教案数据
- 解决：在 `update_lesson_plan.html` 中重新生成教案
- 验证：查看原系统控制台是否有"✅ 教案已推送到格式转换服务"

### 问题2: 转换速度慢
- 原因：Qwen API调用较慢（5-15秒）
- 优化：使用更快的模型或本地部署
- 备选：直接使用降级方案（基础HTML）

### 问题3: 格式不理想
- 原因：PDF模版质量或AI理解偏差
- 解决：
  1. 使用更清晰的PDF模版
  2. 调整Qwen的prompt
  3. 手动微调生成的DOCX

### 问题4: 繁体字显示问题
- 原因：字体缺失
- 解决：确保系统安装了繁体中文字体
  - Windows: Microsoft JhengHei
  - Mac: PMingLiU

## 文件位置说明

| 文件 | 路径 | 用途 |
|------|------|------|
| 教案生成系统 | `proto/update_lesson_plan.html` | 生成教案并推送到后端 |
| 格式转换前端 | `proto/format_converter.html` | 转换格式和下载 |
| 后端服务 | `proto/lesson_format_service/` | API服务 |
| 本地JSON | `[用户选择]/[课程名_日期]/教案内容/*.json` | 本地备份 |
| 后端存储 | 内存（重启后清空） | 临时存储 |

## 下一步增强

可以考虑的功能：
- [ ] 持久化存储（SQLite/PostgreSQL）
- [ ] 模版库管理（多个预设模版）
- [ ] 批量转换
- [ ] 格式预览对比
- [ ] 导出记录和统计
- [ ] WebSocket实时推送
- [ ] 多用户支持
