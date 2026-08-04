# Day 8 / Exp3：词法 + Embedding Schema Linking

## 目标

在Exp2词法分数上加入智谱`embedding-3`语义相似度，观察是否能提高相关表覆盖率，
同时保持Schema压缩、执行成功率和官方Test Suite Accuracy。

每张表被表示为“表名 + 字段名”的英文描述。Embedding接口只接收自然语言问题和表描述，
不会接收标准SQL、标准结果或数据库数据值。

## 方法边界

- 这是启发式混合排序，不训练模式链接模型。
- gold SQL不参与单道题的打分或选表。
- gold表覆盖率用于这30道开发题上的Top-K和融合权重选择，因此Exp3属于开发性消融实验，
  不能把结果表述为独立测试集上的无偏性能。
- API向量缓存只用于避免重复请求，建议不提交Git。

## 第一步：安全设置API Key并生成缓存

```powershell
$secureApiKey = Read-Host "请输入 ZAI API Key" -AsSecureString
$env:ZAI_API_KEY = [System.Net.NetworkCredential]::new("", $secureApiKey).Password
.\.venv\Scripts\python.exe .\day8_hybrid_schema_linking\prepare_embeddings.py
Remove-Item Env:ZAI_API_KEY
Remove-Variable secureApiKey
```

官方接口最多支持64条批量输入；本实验会去重、批量请求并持续保存缓存。

## 第二步：离线审计并固定配置

```powershell
.\.venv\Scripts\python.exe .\day8_hybrid_schema_linking\audit_hybrid_linking.py
```

先检查输出的gold表覆盖率和Schema压缩率，确认后才能运行GLM生成SQL。

## 第三步：运行Exp3（确认离线结果后再做）

```powershell
.\.venv\Scripts\python.exe .\day8_hybrid_schema_linking\run_hybrid_baseline.py --limit 2
.\.venv\Scripts\python.exe .\day8_hybrid_schema_linking\run_hybrid_baseline.py --resume
```
