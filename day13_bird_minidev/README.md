# Day 13：BIRD Mini-Dev 跨基准验证

本阶段在方法冻结后，使用 BIRD Mini-Dev SQLite 的全部 500 道题、11 个数据库，比较完整 DDL Schema 与紧凑完整 Schema。该实验用于验证 Spider 上观察到的效率结论能否迁移到另一个公开 Text-to-SQL 基准。

## 冻结设置

- 模型：`glm-4.5-air`
- 两组均提供官方 `evidence`
- 不向模型提供标准 SQL 或标准执行结果
- 两组使用相同提示词、模型和 API 参数，只改变 Schema 表示
- 只重试未获得任何 SQL 的 API 基础设施失败
- 预测 SQL 本地执行上限为 10 秒
- 正式评测使用 BIRD 官方 Execution Accuracy 语义和 30 秒超时
- 看到完整 Schema 结果后，没有修改紧凑 Schema 格式或提示词

## 正式结果

| 指标 | 完整 Schema | 紧凑 Schema | 变化 |
|---|---:|---:|---:|
| BIRD 官方 EX | 44.80%（224/500） | 44.00%（220/500） | -0.80 个百分点 |
| 简单题 EX | 62.84% | 62.16% | -0.68 个百分点 |
| 中等题 EX | 42.40% | 41.60% | -0.80 个百分点 |
| 困难题 EX | 24.51% | 23.53% | -0.98 个百分点 |
| 本地 SQL 可执行率 | 81.80% | 79.60% | -2.20 个百分点 |
| API 总 tokens | 420,203 | 373,819 | **-11.04%** |
| Schema 字符总量 | 1,389,351 | 968,361 | **-30.30%** |

官方逐题配对结果：两组都正确 195 题、仅完整 Schema 正确 29 题、仅紧凑 Schema 正确 25 题、两组都错误 251 题。McNemar 双侧精确检验 `p = 0.6835`，没有证据表明两组准确率存在显著差异。

因此，本实验支持的结论是：**紧凑完整 Schema 能减少输入规模和 API tokens，同时在 BIRD Mini-Dev 上维持统计上相当的准确率；它不是一种提高准确率的方法。**

## 评测说明

本地初步结果比较得到 40.2%，官方 EX 分别为 44.8% 和 44.0%。差异来自评测语义：官方 evaluator 将查询结果转换为集合后比较，不考虑行顺序和重复行。本项目最终报告采用官方 EX。

`official_evaluation/evaluation_ex.py`保留官方执行与计分逻辑；`evaluation_utils.py`只保留本项目实际使用的SQLite路径，移除了上游文件中与本实验无关的MySQL/PostgreSQL连接示例和本地凭据。

BIRD 压缩包中的 SQLite gold 文件有 3 行不符合 evaluator 要求的 `SQL<TAB>db_id` 格式。`prepare_official_evaluation.py` 从同一份官方 `mini_dev_sqlite.json` 原样重建评测输入，不修改任何 gold SQL，并保留原始数据文件以供核查。

## 复现流程

```powershell
# 1. 检查官方数据并冻结实验配置
.\.venv\Scripts\python.exe .\day13_bird_minidev\prepare_bird_experiment.py

# 2. 生成两组模型输出；中断后可在命令末尾添加 --resume
.\.venv\Scripts\python.exe .\day13_bird_minidev\run_bird_validation.py `
  --schema-mode full `
  --output .\day13_bird_minidev\bird_full_schema_final_results.json

.\.venv\Scripts\python.exe .\day13_bird_minidev\run_bird_validation.py `
  --schema-mode compact `
  --output .\day13_bird_minidev\bird_compact_schema_final_results.json

# 3. 生成官方评测输入与本地配对报告
.\.venv\Scripts\python.exe .\day13_bird_minidev\prepare_official_evaluation.py

# 4. 使用官方评测逻辑计算逐题结果与最终配对检验
.\.venv\Scripts\python.exe .\day13_bird_minidev\run_official_paired_evaluation.py `
  --workers 4 `
  --timeout 30
```

主要结果文件：

- `bird_full_schema_final_results.json`
- `bird_compact_schema_final_results.json`
- `bird_paired_comparison.json`
- `bird_official_paired_comparison.json`
- `official_evaluation/full_official_ex.txt`
- `official_evaluation/compact_official_ex.txt`

数据来源：[BIRD Mini-Dev](https://github.com/bird-bench/mini_dev)，许可证为 CC BY-SA 4.0。外部数据位于 `data/bird_mini_dev/`，该目录不提交到 Git。
