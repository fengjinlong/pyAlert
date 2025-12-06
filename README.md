# pyAlert

## GitHub Actions 自动部署配置

本项目配置了 GitHub Actions 工作流，当代码推送到 `main` 分支时，会自动部署到服务器。

### 配置步骤

1. **在 GitHub 仓库中配置 Secrets**（推荐方式，更安全）
   
   进入仓库的 Settings → Secrets and variables → Actions，添加以下 Secrets：
   

   **注意**：如果不配置 Secrets，工作流会使用默认值，但为了安全起见，强烈建议将密码存储在 GitHub Secrets 中。

2. **推送代码触发部署**
   
   当代码推送到 `main` 分支时，GitHub Actions 会自动：
   - 检出最新代码
   - 通过 SSH 密码认证连接到服务器
   - 使用 SCP 同步文件到 `/root/pyAlert` 目录

### 工作流文件位置


### 服务器信息

- 用户名：`root`
- 目标目录：`/root/pyAlert`

### 注意事项

- 工作流会自动排除 `.git`、`.github`、`__pycache__`、`*.pyc`、`.DS_Store`、`*.md` 等不需要同步的文件
- 确保服务器上的 `/root/pyAlert` 目录有写入权限
- 为了安全，建议将敏感信息（如密码）存储在 GitHub Secrets 中，而不是直接写在代码里
