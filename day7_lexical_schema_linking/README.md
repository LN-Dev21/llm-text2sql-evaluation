# Day 7 / Exp2：词法 Schema Linking

## 方法边界

这是一个简化、可解释的启发式实现，不训练专门的模式链接模型：

1. 将问题、表名和字段名拆分为小写词元，并做简单单复数归一化。
2. 使用精确词元重合和 RapidFuzz 模糊相似度给每张表打分。
3. 选择分数最高的4张表作为种子。
4. 在SQLite外键图上补充种子表之间的最短连接路径。
5. Prompt只包含最终选中表的字段，以及选中表之间的外键。

选择阶段只读取自然语言问题和数据库Schema。标准SQL仅在选择完成后用于离线审计，
不会参与打分，也不会发送给GLM。

## 文件

- `lexical_schema_linker.py`：词法打分、外键路径扩展和选中Schema渲染。
- `audit_lexical_linking.py`：生成选择文件并离线计算gold表覆盖率。
- `lexical_schema_selections.json`：模型实际使用的选择结果，不包含gold SQL。
- `lexical_schema_audit.json`：仅用于实验分析的gold表覆盖率。
- `configuration_comparison.json`：Top-3/4/5离线配置比较与固定参数理由。
- `run_lexical_baseline.py`：复用共享API管线运行同一批30题。
- `lexical_schema_results.json`：Exp2模型预测结果。

## 离线审计（不调用API）

```powershell
.\.venv\Scripts\python.exe .\day7_lexical_schema_linking\audit_lexical_linking.py
```

只有完成覆盖率和Schema压缩率检查后，才运行API实验。

## 固定配置

在调用API前一次性比较Top-3、Top-4和Top-5：

- Top-3：完整覆盖27/30题，Schema字符减少54.1%。
- Top-4：完整覆盖29/30题，Schema字符减少46.0%。
- Top-5：完整覆盖29/30题，Schema字符减少33.3%。

因此Exp2固定使用Top-4；Top-5没有提高覆盖率但压缩更少。唯一遗漏的
`spider_dev_0575`需要通过`Master/Bachelor`两个数据库值推断`Degree_Programs`，
这超出了纯表名和字段名词法匹配的能力边界。配置固定后不再根据模型成绩修改。
