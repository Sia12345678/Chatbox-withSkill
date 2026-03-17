# Render 部署指南

## 一键部署步骤

### 1. 推送代码到 GitHub

```bash
git init
git add .
git commit -m "Initial commit for Render deployment"
gh repo create chatbox --public --push
```

或者手动在 GitHub 创建仓库后推送：

```bash
git remote add origin https://github.com/YOUR_USERNAME/chatbox.git
git push -u origin main
```

### 2. 在 Render 上部署

**方式一：Blueprint 部署（推荐）**

1. 登录 [Render Dashboard](https://dashboard.render.com)
2. 点击 "New +" → "Blueprint"
3. 选择你的 GitHub 仓库
4. Render 会自动识别 `render.yaml` 配置并创建服务

**方式二：手动创建 Web Service**

1. 点击 "New +" → "Web Service"
2. 选择你的 GitHub 仓库
3. 配置如下：
   - **Name**: chatbox
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt && playwright install chromium`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. 点击 "Create Web Service"

### 3. 设置环境变量

在 Render Dashboard → Service → Environment 中添加：

| Key | Value |
|-----|-------|
| `DEEPSEEK_API_KEY` | `sk-3c96620488344053ad8a15e1710364b5` |
| `OPENAI_API_KEY` | `sk-3c96620488344053ad8a15e1710364b5` |
| `OPENAI_BASE_URL` | `https://api.deepseek.com/v1` |

### 4. 访问你的应用

部署完成后，Render 会分配一个 URL：
```
https://chatbox-xxx.onrender.com
```

## 部署后配置

### 修改 Skill 配置

如需启用/禁用 web-crawler skill，修改 `config.json`：

```json
{
    "web-crawler": true
}
```

然后重新推送代码。

## 故障排除

### 1. Playwright 安装失败

如果 chromium 安装失败，在 Render Dashboard 的 Shell 中执行：

```bash
playwright install chromium
```

### 2. 环境变量未生效

确保环境变量名称完全匹配：
- `DEEPSEEK_API_KEY`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`

### 3. 内存不足

如果启动失败，可能是内存不足。在 Render Dashboard 中升级计划：
- Free: 512 MB
- Starter: 1 GB
- Standard: 2 GB

## 费用预估

| 项目 | 费用 |
|------|------|
| Render Free 计划 | $0/月 |
| DeepSeek API | ¥2/百万 tokens |
| 预估月费（轻度使用）| ¥10-50 |

## 本地测试

部署前先在本地测试：

```bash
# 安装依赖
pip install -r requirements.txt
playwright install chromium

# 设置环境变量
export DEEPSEEK_API_KEY="sk-3c96620488344053ad8a15e1710364b5"
export OPENAI_API_KEY="sk-3c96620488344053ad8a15e1710364b5"
export OPENAI_BASE_URL="https://api.deepseek.com/v1"

# 启动服务
uvicorn main:app --host 0.0.0.0 --port 8018

# 测试
curl -X POST http://localhost:8018/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好"}'
```
