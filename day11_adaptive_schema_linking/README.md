# Day 11：动态 Schema Linking 与安全回退

固定Top-4在150题扩展验证中显著退化。本阶段不再把该150题称为独立测试集，而将其与
原30题一起用于探索性方法开发。

动态策略包含：

1. 小Schema直接使用完整Schema。
2. 大Schema按照表数量比例动态确定种子表数量。
3. 使用外键最短路径补齐连接表，并可加入一跳邻居。
4. 截断边界分数过于接近时视为低置信度，回退完整Schema。
5. 扩展后接近完整Schema时直接回退，避免保留复杂度却几乎不节省Token。

离线配置目标是必要表完整覆盖率至少98%，然后最大化Schema字符压缩率。gold SQL只用于
配置审计，不进入逐题选表，也不发送给模型。

```powershell
.\.venv\Scripts\python.exe .\day11_adaptive_schema_linking\tune_adaptive_policy.py
```

检查离线覆盖率后，才能决定是否运行探索性API实验。该150题上的API结果不能重新包装成
“独立held-out成绩”；最终仍需新的测试数据。
