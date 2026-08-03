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

