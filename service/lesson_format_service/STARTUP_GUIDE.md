# 教案格式转换服务 - 快速启动指南

## 一、环境准备

### 1. Python环境
确保已安装 Python 3.8+

```bash
python --version
```

### 2. 安装依赖

```bash
cd lesson_format_service
pip install -r requirements.txt
```

**注意**：WeasyPrint在Windows上需要额外配置：
- 下载 GTK+ for Windows: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
- 安装后添加到系统PATH

或者使用简化版（不支持PDF生成）：
```bash
# 如果WeasyPrint安装失败，可以先注释掉requirements.txt中的weasyprint
# 或直接跳过，PDF功能会降级
```

### 3. 配置API密钥

复制 `.env.example` 为 `.env`：
```bash
copy .env.example .env
```

编辑 `.env` 文件，填入Qwen API密钥：
```
QWEN_API_KEY=sk-your-api-key-here
```

## 二、启动服务

### 方式1：使用启动脚本
```bash
python run.py
```

### 方式2：使用uvicorn
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动成功后，服务运行在：http://localhost:8000

### 验证服务
浏览器访问：http://localhost:8000
应该看到API信息页面

## 三、使用流程

### 步骤1：生成教案（在原系统中）
1. 打开 `update_lesson_plan.html`
2. 上传教案文件或直接输入
3. 生成初步教案
4. 系统会自动将教案推送到格式转换服务

### 步骤2：转换格式
1. 打开 `format_converter.html`
2. 从下拉列表选择要转换的教案
3. 上传格式模版PDF（如：旋轉對稱圖形教案.pdf）
4. 选择输出格式（JSON/DOCX/MD/TXT/PDF）
5. 点击"开始转换"
6. 预览HTML结果
7. 下载所需格式

## 四、目录结构

```
proto/
├── update_lesson_plan.html          # 原教案生成系统（已集成推送功能）
├── format_converter.html            # 新的格式转换前端
└── lesson_format_service/           # 后端服务
    ├── app/
    │   ├── main.py                  # FastAPI应用入口
    │   ├── models.py                # 数据模型
    │   ├── services/
    │   │   ├── qwen_service.py      # Qwen API
    │   │   ├── converter.py         # 格式转换
    │   │   └── storage.py           # 内存存储
    │   └── routes/
    │       ├── lesson_plans.py      # 教案API
    │       └── convert.py           # 转换API
    ├── config.py                    # 配置
    ├── run.py                       # 启动脚本
    └── requirements.txt             # 依赖列表
```

## 五、API测试

### 测试健康检查
```bash
curl http://localhost:8000/health
```

### 测试获取教案列表
```bash
curl http://localhost:8000/api/lesson-plans
```

### 手动推送教案（测试）
```bash
curl -X POST http://localhost:8000/api/lesson-plans \
  -H "Content-Type: application/json" \
  -d '{"metadata":{"type":"测试教案","generatedAt":"2025-02-13T08:00:00Z","generatedAtReadable":"2025/2/13 16:00:00","courseTitle":"测试课程"},"content":"这是测试内容"}'
```

## 六、常见问题

### Q1: 启动服务时提示端口被占用
A: 修改 `config.py` 中的 `PORT = 8001` 使用其他端口

### Q2: WeasyPrint安装失败
A: 
- Windows: 确保已安装GTK+ Runtime
- 或暂时跳过PDF生成功能
- 或使用 pdfkit 替代（需要 wkhtmltopdf）

### Q3: Qwen API调用失败
A: 检查：
- `.env` 文件中的API密钥是否正确
- 网络连接是否正常
- API配额是否充足

### Q4: CORS错误
A: 确保 `config.py` 中的 `CORS_ORIGINS` 包含前端页面的URL

### Q5: 前端无法连接后端
A: 
- 确认后端服务已启动
- 检查 `update_lesson_plan.html` 和 `format_converter.html` 中的 API_BASE_URL 是否正确
- 检查防火墙设置

## 七、开发调试

### 查看日志
服务启动后，所有日志会输出到控制台

### 热重载
使用 `--reload` 参数启动时，修改代码会自动重启服务

### 调试模式
在 `config.py` 中设置：
```python
RELOAD = True  # 开发模式
```

## 八、生产部署建议

1. **环境变量**：通过环境变量设置敏感信息，不要提交 `.env`
2. **HTTPS**：使用 Nginx 反向代理并配置 SSL
3. **进程管理**：使用 Gunicorn 或 Supervisor 管理进程
4. **持久化存储**：当前使用内存存储，生产环境建议使用数据库
5. **日志**：配置日志文件和日志轮转
6. **性能**：使用多worker模式

```bash
# 生产启动示例
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## 九、功能清单

✅ 接收教案JSON
✅ 教案列表查询
✅ Qwen多模态API集成
✅ HTML生成
✅ 格式转换（JSON/DOCX/MD/TXT/PDF）
✅ 文件下载
✅ CORS支持
✅ 错误处理
✅ 降级方案

## 十、联系与支持

开发团队：黄海博士 • 钟丽霞博士 • 梁展帆团队

如有问题，请查看：
- `README.md` - 项目文档
- `app/` - 源代码
- GitHub Issues - 问题反馈
