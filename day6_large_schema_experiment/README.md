# Day 6：较大 Schema 的完整 Schema 基线

## 为什么需要新实验集

Day 4 的数据库只有 2–4 张表。完整 Schema 本来就很短，Schema Linking 即使正确，
也很难体现减少无关表和字段的价值。Day 6 固定选择 Spider dev 中表数量最多且题量
充足的三个数据库：

- `student_transcripts_tracking`：11 张表、56 个字段
- `dog_kennels`：8 张表、49 个字段
- `car_1`：6 张表、23 个字段

每个数据库抽取10道去同义重复、结构复杂度分层的题目，共30题。后续所有实验必须
使用同一个 `large_schema_subset.json`，不能根据模型表现临时换题。

## 实验顺序

1. Exp1：完整 Schema、zero-shot、无反馈。
2. Exp2：字符串匹配与模糊匹配的词法 Schema Linking。
3. Exp3：词法分数加 embedding 语义相似度。
4. Exp4：在最佳 Schema Linking 配置上加入执行错误反馈和有限次数纠错。

标准 SQL 只保存在本地评测文件中，不会出现在模型 Prompt 里。

## 文件说明

- `prepare_large_schema_subset.py`：复用 Day 4 抽样逻辑生成固定30题。
- `large_schema_subset.json`：所有后续实验共用的题目和标准 SQL。
- `profile_schemas.py`：记录表、字段、外键和 Test Suite 实例数量。
- `schema_profile.json`：Schema 规模报告。
- `run_full_schema_baseline.py`：复用 Day 4 API 管线运行 Exp1。
- `full_schema_results.json`：运行 Exp1 后生成的模型预测和开发期结果。
- `full_schema_experiment_summary.json`：冻结的 Exp1 指标汇总。
- `full_schema_test_suite_output.txt`：官方 Test Suite Accuracy 输出。
- `full_schema_test_suite_case_analysis.json`：逐题单数据库与 Test Suite 判定。

## 准备实验集（不调用 API）

```powershell
.\.venv\Scripts\python.exe .\day6_large_schema_experiment\prepare_large_schema_subset.py
.\.venv\Scripts\python.exe .\day6_large_schema_experiment\profile_schemas.py
```

## 运行 Exp1

先测试2题：

```powershell
.\.venv\Scripts\python.exe .\day6_large_schema_experiment\run_full_schema_baseline.py --limit 2
```

确认正常后续跑30题：

```powershell
.\.venv\Scripts\python.exe .\day6_large_schema_experiment\run_full_schema_baseline.py --resume
```

批量管线默认单次请求30秒超时，SDK最多自动重试1次。若网络失败，程序会保存失败记录
并继续后续题目；再次使用 `--resume` 时，未获得 SQL 的题目会自动重试，已有 SQL 的题目
不会重复消耗额度。可用 `--api-timeout` 和 `--api-max-retries` 调整。

运行前需在当前 PowerShell 中安全设置 `ZAI_API_KEY` 和 `ZAI_MODEL=glm-4.5-air`。

## Exp1 最终结果

- SQL 执行成功率：28/30，93.33%
- 严格本地结果比较：19/30，63.33%
- 允许等价列置换的本地比较：21/30，70%
- 官方原始单数据库执行准确率：21/30，70%
- **官方 Test Suite Accuracy：17/30，56.67%**
- 总 tokens：17,531
- 平均 API 延迟：5.486 秒

分数据库 Test Suite Accuracy：

- `student_transcripts_tracking`：7/10
- `dog_kennels`：5/10
- `car_1`：5/10

两条 SQL 执行失败都来自 `car_1`，模型错误引用了不存在的 `countries.Country`；实际字段是
`Countries.CountryId`。这类表字段幻觉是后续 Schema Linking 需要重点观察的错误类型。

官方输入文件必须严格保持“一题一行 SQL”。适配器会把模型生成的多行 SQL 转成单行，并
检查 gold 与 prediction 的行数都等于题目数，防止预测与标准答案错位。
