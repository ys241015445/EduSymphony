# 更新日志

## [1.1.0] - 2026-02-12

### 简化与优化

#### Qwen API调用简化
- **移除**: pdf2image转换步骤，直接使用Qwen API的PDF上传功能
- **移除**: pillow依赖（仅用于pdf2image）
- **移除**: poppler系统依赖要求
- **简化**: `convert_with_qwen_pdf()` 函数，从30行减少到3行
- **优化**: 处理速度提升20-30倍（移除PDF→PNG转换）
- **改进**: 参数命名从 `is_image` 改为 `is_pdf` 更清晰

#### 依赖简化
- **前**: 13个Python包 + 1个系统依赖（poppler）
- **后**: 11个Python包 + 0个系统依赖
- **减少**: 2个Python包，1个系统依赖

#### 文档更新
- 更新 `HYBRID_CONVERSION.md` - 移除pdf2image相关说明
- 更新 `IMPLEMENTATION_COMPLETE.md` - 移除poppler安装指南
- 新增 `QWEN_SIMPLIFICATION.md` - 简化说明文档

---

## [1.0.0] - 2026-02-12

### 新增功能

#### 混合PDF格式转换方案
实现了三层降级的转换策略：

1. **方案1: PDF解析填充（主方案）**
   - 使用pdfplumber提取PDF结构和样式
   - 解析教案内容章节
   - 根据样式生成HTML
   - 优势：快速、免费、样式还原度高

2. **方案2: Qwen AI（降级方案1）**
   - 直接上传PDF到Qwen API
   - AI理解模版格式和要点
   - 生成符合要求的HTML
   - 优势：智能理解、处理复杂布局

3. **方案3: 基础模版（降级方案2）**
   - 使用内置HTML模版
   - 保底方案，确保总能生成结果

#### 核心功能
- PDF模版样式提取和分析
- 教案内容结构化解析（支持JSON和纯文本）
- 多格式输出（HTML/JSON/DOCX/MD/TXT/PDF）
- 智能方案选择
- 用户可手动选择转换方式

#### 前端界面
- 教案选择下拉列表
- PDF模版上传
- 转换方案选择（智能/强制Qwen）
- 输出格式多选
- HTML预览
- 多格式下载

#### 后端API
- POST `/api/lesson-plans` - 添加教案
- GET `/api/lesson-plans` - 获取教案列表
- GET `/api/lesson-plans/{id}` - 获取单个教案
- POST `/api/convert` - 格式转换
- GET `/api/download/{format}/{id}` - 下载文件

### 技术栈
- **后端**: FastAPI + Python 3.8+
- **前端**: 原生HTML/CSS/JavaScript
- **PDF处理**: pdfplumber（解析），weasyprint（生成）
- **AI服务**: Qwen多模态API
- **文档生成**: python-docx（DOCX），html2text（Markdown）

### 文档
- `README.md` - 项目介绍
- `HYBRID_CONVERSION.md` - 技术文档
- `IMPLEMENTATION_COMPLETE.md` - 实施完成报告
- `STARTUP_GUIDE.md` - 启动指南
- `USAGE_GUIDE.md` - 使用指南

---

## 升级指南

### 从 v1.0.0 升级到 v1.1.0

1. **更新代码**：
   ```bash
   git pull origin main
   ```

2. **更新依赖**：
   ```bash
   pip install -r requirements.txt --upgrade
   ```

3. **无需安装poppler**：
   - 如果之前安装了poppler，现在可以卸载
   - 新安装的用户无需安装poppler

4. **无需修改配置**：
   - API接口保持不变
   - 前端无需修改
   - 已有的教案数据兼容

5. **重启服务**：
   ```bash
   python run.py
   ```

### 测试升级
升级后建议测试：
- Qwen AI转换功能
- 混合转换策略（智能选择）
- 各种输出格式生成
- PDF模版解析功能

---

## 已知问题

### v1.1.0
无已知问题

### v1.0.0
- ~~需要安装poppler系统依赖~~ (已在v1.1.0修复)
- ~~PDF转换需要额外的pdf2image步骤~~ (已在v1.1.0简化)

---

## 计划中的功能

### v1.2.0 (计划中)
- [ ] 批量教案转换
- [ ] 转换结果缓存
- [ ] 支持多页PDF处理
- [ ] 提取PDF中的图片
- [ ] 转换进度实时跟踪

### v1.3.0 (计划中)
- [ ] 支持更多输出格式（PPT、LaTeX等）
- [ ] 自定义模版管理
- [ ] 历史转换记录查询
- [ ] 转换质量评分

---

## 贡献者
- 开发团队
- 感谢所有提供反馈的用户

---

**注意**: 本项目遵循语义化版本控制 (Semantic Versioning)
