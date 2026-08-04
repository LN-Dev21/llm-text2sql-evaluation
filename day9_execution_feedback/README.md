# Day 9 / Exp4：执行结果反馈与一次自校正

## 实验设计

Exp4固定使用Exp2词法Schema Linking，并直接复用Exp2生成的首轮SQL。每道题都执行首轮SQL，
然后把问题、精简Schema、首轮SQL、执行状态、错误信息、返回列、总行数和最多3行样例交给
GLM进行一次语义复核。

不能只校正本地评测判错的题，因为真实系统不知道标准答案。所有30题使用完全相同的反馈策略。
标准SQL和标准结果不会进入反馈Prompt。

这比“仅在SQL报错时重试”更宽，因为Exp2的30条SQL全部可执行；项目中应准确称为
“执行结果反馈自校正”，而不是声称所有错误都能由数据库报错发现。

## 1. 离线检查Prompt（不调用API）

```powershell
.\.venv\Scripts\python.exe .\day9_execution_feedback\preview_feedback_prompt.py
```

人工打开`feedback_prompt_example.txt`，确认其中没有gold SQL或gold结果。

## 2. 运行Exp4

安全设置`ZAI_API_KEY`和`ZAI_MODEL=glm-4.5-air`后，先跑2题：

```powershell
.\.venv\Scripts\python.exe .\day9_execution_feedback\run_execution_feedback.py --limit 2
.\.venv\Scripts\python.exe .\day9_execution_feedback\run_execution_feedback.py --resume
```

完成后清除当前PowerShell窗口中的API Key，再运行官方Test Suite评测。
