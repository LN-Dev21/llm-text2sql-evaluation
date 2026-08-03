# Day 3：多问题批量零样本基线

Day 1 和 Day 2 都只验证了一道题。Day 3 建立一个包含10道题的本地小型测试集，让同一个模型在相同设置下逐题生成 SQL，并自动统计执行成功率和执行正确率。

这仍是开发阶段的本地测试集，不是 Spider 正式实验结果，不能作为通用性能结论。

## 文件

- `cases.json`：中文问题、难度和本地标准 SQL；
- `run_batch.py`：动态提取完整 Schema、调用 GLM、执行预测与标准 SQL、比较结果；
- `batch_results.json`：运行后生成的逐题记录与汇总。

标准 SQL 只在本地评测阶段使用，程序发送给模型的 Prompt 仅包含完整 Schema 和当前中文问题。

## 1. 调用 API 前验证标准 SQL

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe .\day3_batch_baseline\run_batch.py --validate-only
```

只有10条标准 SQL 全部通过，才能继续。

## 2. 先试跑2题

安全设置 API Key 后运行：

```powershell
.\.venv\Scripts\python.exe .\day3_batch_baseline\run_batch.py --limit 2
```

确认生成 `batch_results.json` 且两题均完成，再运行剩余题目。

## 3. 从已有结果续跑完整测试集

```powershell
.\.venv\Scripts\python.exe .\day3_batch_baseline\run_batch.py --resume
```

`--resume` 会跳过结果文件中已经完成的题目，避免重复消耗 API Token。程序每完成一题就立即保存一次结果，因此中途异常后也可以续跑。

## 指标

- `execution_success_rate`：模型 SQL 能够在 SQLite 中成功执行的比例；
- `execution_accuracy`：模型 SQL 与标准 SQL 的执行结果一致的比例；
- `total_tokens`：当前已完成调用的总 Token 数。

问题全部规定了排序规则，因此当前评测按结果行顺序进行比较。评测忽略输出列的别名差异，避免把仅列名不同但结果相同的 SQL 错判为错误。

## 当前评测边界

执行结果一致不一定能在单个小数据库上完全证明 SQL 语义一致：错误 SQL 可能碰巧得到相同结果，空结果题尤其容易出现这种情况。因此本阶段只用于验证批量工程链路和初步发现错误，不能作为 Spider Test Suite Accuracy 或通用模型能力结论。正式实验会改用公开数据集及其标准评测器。
