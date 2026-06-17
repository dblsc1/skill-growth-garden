# Contributing Guide

## 分支规范

| 分支 | 用途 |
|------|------|
| `main` | 生产就绪，只通过 PR 合入 |
| `develop` | 日常开发集成线，只通过 PR 合入 |
| `feature/<name>` | 新功能，从 develop 切出 |
| `fix/<name>` | Bug 修复，从 develop 切出 |
| `hotfix/<name>` | 紧急生产修复，从 main 切出 |

## 工作流程

```bash
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name
# ... 写代码 ...
git push origin feature/your-feature-name
# → GitHub 上开 Pull Request 到 develop
```

## Commit 规范

格式：`类型: 简短描述（中英文均可）`

```
feat:     新功能
fix:      修 bug
docs:     文档变更
test:     测试相关
refactor: 重构
chore:    构建/依赖/配置
```

示例：
- `feat: add player movement system`
- `fix: resolve collision on mobile`
- `docs: update API reference`
