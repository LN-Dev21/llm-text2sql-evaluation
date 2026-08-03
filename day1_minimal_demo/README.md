# Day 1：Text-to-SQL 最小闭环

本目录完成一件最小但完整的事情：把中文问题和数据库结构交给大语言模型，让模型生成 SQL，再在真实 SQLite 数据库中执行，并自动判断结果是否正确。

## 文件作用

- `schema.sql`：定义三张表及它们的关系。
- `seed.sql`：插入用于演示的学生、专业和成绩数据。
- `student.db`：运行后实际创建的 SQLite 数据库文件。
- `prompt.txt`：交给大语言模型的 Schema、约束和中文问题。
- `call_zhipu_llm.py`：调用智谱 API，将结果保存为 `llm_generated_api.sql`。
- `llm_generated.sql`：不调用 API 时使用的人工示例 SQL。
- `llm_generated_api.sql`：智谱模型实际生成的 SQL。
- `run_demo.py`：创建数据库、执行指定 SQL、保存评测结果。
- `execution_result.json` / `execution_result_api.json`：执行和判定记录。

## 统一项目环境

本项目只在根目录维护一个 `.venv`。下面所有命令都从 `Text-to-SQL System` 根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

## 1. 先运行人工示例，创建并验证数据库

```powershell
.\.venv\Scripts\python.exe .\day1_minimal_demo\run_demo.py
```

此时会真实创建 `day1_minimal_demo/student.db`，并生成 `execution_result.json`。

## 2. 设置智谱 API 并生成 SQL

只在当前 PowerShell 窗口设置密钥，不要写入代码或提交到 Git：

```powershell
$secureApiKey = Read-Host "请输入 ZAI API Key" -AsSecureString
$env:ZAI_API_KEY = [System.Net.NetworkCredential]::new("", $secureApiKey).Password
$env:ZAI_MODEL = "glm-4.5-air"
.\.venv\Scripts\python.exe .\day1_minimal_demo\call_zhipu_llm.py
```

成功后会在 Day 1 目录生成 `llm_generated_api.sql` 和 `llm_api_metadata.json`。

## 3. 执行并判断模型生成的 SQL

```powershell
.\.venv\Scripts\python.exe .\day1_minimal_demo\run_demo.py --sql-file llm_generated_api.sql --result-file execution_result_api.json --provider "Zhipu GLM-4.5-Air API"
```

看到 `execution_success: true` 和 `is_correct: true`，表示最小闭环跑通。完成 API 调用后可清除密钥：

```powershell
Remove-Item Env:ZAI_API_KEY
Remove-Variable secureApiKey
```

