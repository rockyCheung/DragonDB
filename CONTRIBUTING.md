# 贡献指南

感谢您对 DragonDB 的关注！我们欢迎任何形式的贡献，包括但不限于报告问题、提交功能请求、改进文档、修复 bug 或添加新功能。本指南将帮助您快速上手。

## 行为准则

请阅读并遵守我们的[行为准则](CODE_OF_CONDUCT.md)。我们致力于营造一个开放、友好的社区环境。

## 报告问题

如果您发现 bug 或有功能建议，请通过 [GitHub Issues](https://github.com/rockyCheung/DragonDB/issues) 提交，并尽可能提供以下信息：
- 问题描述（包括预期行为和实际行为）
- 复现步骤
- 环境信息（操作系统、Python 版本、DragonDB 版本）
- 相关日志或截图

## 开发环境搭建

### 1. 克隆仓库
```bash
git clone https://github.com/rockyCheung/DragonDB/dragondb.git
cd dragondb
```

### 2. 创建虚拟环境（推荐）
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

### 3. 安装依赖
安装运行时依赖和开发测试依赖：
```bash
pip install -r requirements-dev.txt
```

### 4. 运行测试
确保所有测试通过：
```bash
pytest tests/
```

### 5. 启动单节点验证
```bash
python start.py --node node1
# 在另一个终端验证
curl http://127.0.0.1:8081/admin/collections
```

## 代码规范

- **Python 版本**：3.10+
- **代码风格**：遵循 [PEP 8](https://www.python.org/dev/peps/pep-0008/)。建议使用 `black` 自动格式化：
  ```bash
  black dragondb/ tests/
  ```
- **导入顺序**：使用 `isort` 排序：
  ```bash
  isort dragondb/ tests/
  ```
- **文档字符串**：重要函数和类应包含清晰的文档字符串，遵循 Google 风格或 NumPy 风格。
- **类型注解**：尽可能为函数参数和返回值添加类型注解。

## 提交 Pull Request

1. **创建分支**：从 `main` 分支创建新分支，命名应简洁（如 `fix-issue-123` 或 `feature-new-api`）。
2. **提交信息**：使用清晰、简洁的提交信息，建议遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范（如 `feat: add support for ...`、`fix: correct ...`）。
3. **保持同步**：定期将 `main` 分支的更新合并到您的分支，避免冲突。
4. **运行测试**：在提交前确保所有测试通过，且代码覆盖率不显著下降。
5. **提交 PR**：在 GitHub 上创建 Pull Request，描述您的更改内容、动机和影响。关联相关 Issue（如有）。
6. **代码审查**：等待维护者 review，并根据反馈进行修改。

## 测试要求

- 新功能应包含相应的单元测试和集成测试。
- 测试文件放在 `tests/` 下对应子目录，命名如 `test_*.py`。
- 使用 `pytest` 运行测试，确保覆盖率报告显示新增代码已被覆盖。
- 对于涉及文件系统的测试，请使用 `tmp_path` fixture 或临时目录。

## 文档改进

- 文档位于 `docs/` 目录，使用 Markdown 格式。
- 修改后请预览确保格式正确。
- 如果有 API 变更，请同步更新 `docs/api_reference.md`。

## 联系方式

- GitHub Issues：问题讨论和跟踪
- 邮件列表：暂无
- 讨论区：欢迎通过 Issues 发起讨论

再次感谢您的贡献！
