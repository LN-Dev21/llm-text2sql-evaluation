# Day 4：接入 Spider 1.0 并建立跨数据库开发子集

## 这一阶段解决什么问题

Day 3 的 10 道题全部来自我们自己创建的 `student.db`。它适合验证程序流程，
但不能证明系统面对陌生数据库仍然有效。Day 4 开始接入公开的 Spider 1.0 数据集，
把评测对象从“单个自建数据库”扩展到“多个不同领域的数据库”。

本阶段先不调用大模型，目标是确认数据来源、数据库、问题和标准 SQL 能正确对应。
只有标准 SQL 全部能够执行，后续模型评测才有可信基础。

## 文件说明

- `inspect_spider.py`：检查 `dev.json`、`tables.json` 和 SQLite 数据库是否完整对应。
- `dataset_summary.json`：运行检查脚本后生成的数据集摘要。
- `prepare_subset.py`：从 4 个数据库中各选 5 道题，并执行全部标准 SQL。
- `spider_subset.json`：生成的 20 道开发用小样本。
- `run_spider_baseline.py`：自动提取每个数据库的 Schema，并调用 Zhipu GLM。
- `spider_baseline_results.json`：模型运行后生成的逐题结果与汇总。
- `analyze_results.py`：区分真正的结果错误与仅输出列顺序不同的等价 SQL。
- `error_analysis.json`：不重新调用 API 的错误分类结果。

`data/spider_data/` 保存外部数据集，不提交到 GitHub；上述脚本和摘要可以提交。

## 为什么先用 20 道题

这是管线开发集，不是最终实验规模。它用于低成本发现路径、Schema 提取、SQL 执行、
结果比较和 API 调用中的错误。流程稳定后，再扩大样本并接入官方评测器。

当前选取 4 个领域：`concert_singer`、`pets_1`、`course_teach`、`world_1`。
每个数据库内部先按标准 SQL 去重，再根据本项目的结构复杂度分数均匀抽样。
这个分数只负责抽样，不能称为 Spider 官方难度。

## 运行方式

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe .\day4_spider_subset\inspect_spider.py
.\.venv\Scripts\python.exe .\day4_spider_subset\prepare_subset.py
```

这两个命令都不会调用 Zhipu API，也不会修改 Spider 数据库。

确认数据检查通过后，先用 2 道题测试 API 管线：

```powershell
.\.venv\Scripts\python.exe .\day4_spider_subset\run_spider_baseline.py --limit 2
```

再从已有结果继续完成 20 道题：

```powershell
.\.venv\Scripts\python.exe .\day4_spider_subset\run_spider_baseline.py --resume
```

运行前仍需在当前 PowerShell 窗口设置 `ZAI_API_KEY` 和 `ZAI_MODEL`。
本程序报告的是开发期行结果比较，尚不是 Spider 官方 Test Suite Accuracy。

模型运行结束后进行错误分析：

```powershell
.\.venv\Scripts\python.exe .\day4_spider_subset\analyze_results.py
```

分析脚本会同时保留严格逐列准确率，以及允许等价输出列置换的单数据库准确率。
