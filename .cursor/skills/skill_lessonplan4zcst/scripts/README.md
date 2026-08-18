# scripts 说明

本目录脚本为**辅助**。教学正文由 DeepSeek 生成；Agent 负责门禁与写入官方模版。

| 文件 | 作用 |
|---|---|
| `detect_mode.py` | 根据用户给出的文件路径列表，启发式判定模式 A/B/C 并打印建议 |
| `deepseek_generate.py` | 调用 DeepSeek API，按任务输出大纲/周次/教案 JSON |

## detect_mode

```bash
python detect_mode.py path1 path2 ...
```

退出码恒为 0；stdout 为 JSON 一行（mode / reasons / hints）。

## deepseek_generate

默认模型：**`deepseek-v4-pro`**（DeepSeek 当前最新旗舰）。可用 `DEEPSEEK_MODEL=deepseek-v4-flash` 切换。

```bash
set DEEPSEEK_API_KEY=sk-...
python deepseek_generate.py --task syllabus --context context.json --out syllabus.json
python deepseek_generate.py --task weeks --context context.json --out weeks.json
python deepseek_generate.py --task lessons --context context.json --out lessons.json
```

- 无密钥或 API 失败：非零退出，打印错误；**禁止** Agent 改用本地长文顶替。
- 约定与 schema：`../reference/deepseek-contract.md`。

## 注意

- 不读写教学模版版式。  
- 不替代「上课时间门禁」交互。  
- 正式填写仍须复制 `reference/defaults.md` 中的官方模版。
