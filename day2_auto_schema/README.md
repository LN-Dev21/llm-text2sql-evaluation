# Day 2：自动提取 SQLite Schema

这一阶段解决 Day 1 中手工把 `schema.sql` 复制到 Prompt 的问题。程序以只读方式打开真实的 `student.db`，自动读取表、字段、主键和外键，并输出适合交给大语言模型的 Schema 文本。

项目只使用根目录的统一 `.venv`。在 `Text-to-SQL System` 根目录运行：

```powershell
.\.venv\Scripts\python.exe .\day2_auto_schema\extract_schema.py
```

运行后生成 `day2_auto_schema/extracted_schema.txt`。程序使用：

- `sqlite_master`：获取数据库中的表名；
- `PRAGMA table_info(...)`：获取字段、类型、主键和非空约束；
- `PRAGMA foreign_key_list(...)`：获取表之间的外键关系；
- SQLite `mode=ro`：保证读取过程中不会修改数据库。

当前这一步只负责 Schema 自动提取，暂不调用大模型。下一步会把自动提取结果和自然语言问题组合成动态 Prompt。

## 自动构造动态 Prompt

`build_prompt.py` 每次运行都会直接调用 `extract_schema()` 读取数据库，因此不会依赖可能已经过期的手工 Schema。运行：

```powershell
.\.venv\Scripts\python.exe .\day2_auto_schema\build_prompt.py
```

运行后生成 `day2_auto_schema/dynamic_prompt.txt`，其中包含固定输出约束、自动提取的 Schema 和自然语言问题。也可以临时更换问题：

```powershell
.\.venv\Scripts\python.exe .\day2_auto_schema\build_prompt.py --question "查询每个专业的学生人数。"
```

这一小步仍不调用大模型；下一步再把同一个动态 Prompt 交给智谱 GLM。

## 使用动态 Prompt 调用智谱 GLM

先在当前 PowerShell 中安全设置 API Key：

```powershell
$secureApiKey = Read-Host "请输入 ZAI API Key" -AsSecureString
$env:ZAI_API_KEY = [System.Net.NetworkCredential]::new("", $secureApiKey).Password
$env:ZAI_MODEL = "glm-4.5-air"
```

然后运行：

```powershell
.\.venv\Scripts\python.exe .\day2_auto_schema\call_llm_dynamic.py
```

程序按顺序完成：实时提取 Schema、构造并保存动态 Prompt、调用 GLM、检查模型只返回只读查询，并生成：

- `llm_generated_dynamic.sql`：模型根据动态 Prompt 生成的 SQL；
- `llm_dynamic_metadata.json`：模型、问题、数据库、Token 等调用记录。

完成调用后清除当前终端中的密钥：

```powershell
Remove-Item Env:ZAI_API_KEY
Remove-Variable secureApiKey
```

## 执行并评测动态生成的 SQL

当前 Day 2 演示仍使用 Day 1 的固定问题和标准答案。执行：

```powershell
.\.venv\Scripts\python.exe .\day2_auto_schema\evaluate_dynamic_demo.py
```

评测程序以只读方式在 `student.db` 中执行 `llm_generated_dynamic.sql`，并生成 `execution_result_dynamic.json`。其中：

- `execution_success` 表示 SQL 能否运行；
- `is_correct` 表示列名、查询数据和顺序是否与当前题目的标准答案一致。

看到两者都为 `true`，表示 Day 2 的“自动 Schema → 动态 Prompt → GLM → SQL → 执行评测”闭环完成。当前标准答案仍是单题硬编码，后续进入批量数据集阶段后会替换成通用评测器。
