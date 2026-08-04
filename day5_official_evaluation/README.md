# Day 5：接入 Spider 官方执行评测器

## 本阶段的目的

Day 4 使用项目自己的结果比较器完成了开发期评测。Day 5 把相同的预测转换为
Spider 官方格式，并调用官方 `test-suite-sql-eval` 代码，避免自己重写评测规则。

官方输入格式：

- 标准答案：每行 `gold SQL + Tab + db_id`
- 模型预测：每行一条生成 SQL

## 两种容易混淆的结果

1. **官方评测器 + 原始数据库**：每个 Schema 只有一个 SQLite 数据库实例，可验证
   列置换等官方比较规则，但不能称为 Test Suite Accuracy。
2. **官方评测器 + Test Suite 数据库**：每个 Schema 有多个自动生成的数据库实例，
   同一对 SQL 必须在多个数据内容上结果一致，才能称为 Test Suite Accuracy。

官方 Test Suite 数据库压缩包约 1.18 GiB，未包含在 Git 仓库中。

## 当前运行方式

项目根目录执行：

```powershell
.\.venv\Scripts\python.exe .\day5_official_evaluation\run_official_eval.py
```

该命令读取 Day 4 已有预测，不调用任何大模型 API。

官方默认会移除 `DISTINCT`。为了观察该设置的影响，可运行保留 `DISTINCT` 的对照：

```powershell
.\.venv\Scripts\python.exe .\day5_official_evaluation\run_official_eval.py `
  --keep-distinct `
  --output .\day5_official_evaluation\official_keep_distinct_output.txt `
  --metadata .\day5_official_evaluation\official_keep_distinct_metadata.json
```

当前 20 道题在原始数据库上的结果为：官方默认设置 80%，保留 `DISTINCT` 85%。
两者都不是 Test Suite Accuracy，应把官方默认设置作为主结果，对照设置只用于解释差异。

## 文件说明

- `run_official_eval.py`：生成官方输入文件并调用官方评测器。
- `official_gold.txt`：20 条标准 SQL 与数据库 ID。
- `official_predictions.txt`：20 条 GLM 生成 SQL。
- `official_single_db_output.txt`：官方评测器在原始数据库上的终端输出。
- `official_eval_metadata.json`：记录评测器、数据库路径和实例数量，防止指标误标。
- `analyze_test_suite_cases.py`：逐题比较单数据库判定与 Test Suite 判定。
- `test_suite_case_analysis.json`：记录哪些错误曾在原始数据上侥幸通过。

## 当前正式结果

20 道开发子集在官方默认设置下：

- 原始单数据库执行准确率：80%
- Test Suite Accuracy：55%
- 保留 `DISTINCT` 的 Test Suite 对照：55%

增强数据库会改变表中数据，但保持 Schema 不变。如果错误 SQL 只是在原始数据上
碰巧与标准 SQL 返回相同结果，它会在其他数据库实例中暴露出来。
