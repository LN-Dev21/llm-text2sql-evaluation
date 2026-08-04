# Day 10：150题内部 Held-out 泛化评测

## 目的

前30题用于方法开发和参数选择，不能继续用来证明泛化。本阶段冻结Exp2的Top-4词法
Schema Linking配置，在150道未见题目和4个未见数据库上进行一次性确认。

数据来自Spider 1.0 `train_others.json`，但在本项目中作为内部held-out使用；它不是官方
隐藏test集，也不能声称模型从未在预训练阶段见过Spider数据。

数据库与题量：`academic` 38、`imdb` 38、`scholar` 37、`yelp` 37。它们分别有
15、16、10、7张表，并且官方Test Suite包提供增强数据库。

## 离线准备（不调用API）

```powershell
.\.venv\Scripts\python.exe .\day10_heldout_evaluation\prepare_heldout_subset.py
.\.venv\Scripts\python.exe .\day10_heldout_evaluation\profile_heldout.py
.\.venv\Scripts\python.exe .\day10_heldout_evaluation\audit_heldout_schema_linking.py
```

Top-4是开发阶段已经固定的配置。held-out审计只用于报告覆盖率，不能根据审计结果修改配置。

## 正式实验

设置智谱API Key后，每组先跑2题，再续跑150题：

```powershell
.\.venv\Scripts\python.exe .\day10_heldout_evaluation\run_heldout_full_schema.py --limit 2
.\.venv\Scripts\python.exe .\day10_heldout_evaluation\run_heldout_full_schema.py --resume

.\.venv\Scripts\python.exe .\day10_heldout_evaluation\run_heldout_lexical.py --limit 2
.\.venv\Scripts\python.exe .\day10_heldout_evaluation\run_heldout_lexical.py --resume
```

最终以官方Test Suite Accuracy作主指标，并进行逐题配对与McNemar检验。
