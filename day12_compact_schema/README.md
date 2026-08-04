# Day 12：紧凑完整 Schema 表示

动态Schema选择在高召回要求下几乎总是回退完整Schema。本阶段改为不删除任何表或字段，
只压缩Schema表达形式。

传统DDL中的`CREATE TABLE`、缩进、`NOT NULL`等内容被改写为紧凑格式，同时保留：

- 全部表名与字段名
- SQLite字段类型
- 主键标记
- 全部外键关系

该方法没有表召回风险，也不使用gold SQL。150题验证结果属于在发现Top-4失败后的探索性实验，
最终仍需新的测试数据确认。

```powershell
.\.venv\Scripts\python.exe .\day12_compact_schema\prepare_compact_schemas.py
```

检查压缩率后再决定是否运行API实验。
