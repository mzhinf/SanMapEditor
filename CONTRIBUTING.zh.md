# 贡献指南

## 开发环境

项目要求 Python 3.11 或更高版本。推荐使用 uv：

```powershell
uv sync --extra dev
uv run python -m unittest discover -s tests -v
```

也可使用普通虚拟环境和 `pip install -e ".[dev]"`。

## 修改要求

- 非代码说明、注释和文档统一使用中文。
- 新脚本必须说明用途、输入输出和关键安全约束。
- 二进制格式实现以 `src/san_tools/ksy/` 为规范来源；未知字段保留原始字节。
- 不提交游戏素材、分析输出、工作簿、发布包或本机绝对路径。
- 功能变更应补充测试，并同步更新 README、格式笔记或已知问题。

提交前请执行完整测试，并确认 `git status --short` 只包含本次修改。
