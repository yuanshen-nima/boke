# ChatGPT 论文会话一键同步指南 (Tampermonkey 油猴方案)

本方案通过浏览器油猴脚本，实现在 ChatGPT 网页端**一键提取当前论文讨论会话**并直接推送到本地知识库系统，自动生成私有草稿。

---

## 🌟 为什么这种方案最稳健？

1. **零封号风险**：完全在你的真实浏览器标签页中运行，依托你已登录的正常账号，不触发任何异常风控。
2. **100% 绕过 Cloudflare 验证码**：无需编写无头浏览器模拟登录，不需要维护易失效的 Cookie。
3. **轻量即时**：不再需要从 ChatGPT 设置里申请等待几十兆的全局导出 zip 包，单篇读完即点即录。
4. **全自动闭环与保底**：
   - 本地服务启动时：一键直接入库并完成草稿生成；
   - 本地服务未启动时：自动降级为下载 `.json` 文件，放入 `inbox/` 即可。

---

## 🚀 安装步骤 (只需配置一次，约 2 分钟)

### 步骤 1：安装 Tampermonkey (油猴) 扩展
- Chrome / Edge 浏览器插件应用商店搜索 **Tampermonkey** 并安装（或访问 [tampermonkey.net](https://www.tampermonkey.net/)）。

### 步骤 2：添加同步脚本
1. 点击浏览器右上角油猴图标 → **添加新脚本**。
2. 打开本项目中的 [`paper_sync/chatgpt-paper-sync.user.js`](../paper_sync/chatgpt-paper-sync.user.js)。
3. 将全文复制并粘贴到油猴编辑器中，按 `Ctrl + S` 保存。

### 步骤 3：启动本地接收服务
双击运行项目根目录下的批处理脚本：
```cmd
paper_sync\start-server.bat
```
*(或在终端中执行：`python -m paper_sync serve`)*
看到控制台输出：
```
PaperSync 本地接收服务已启动: http://127.0.0.1:8765
油猴脚本数据接收端点: http://127.0.0.1:8765/api/inbox
```
即表示本地服务已就绪！

---

## 📖 日常使用工作流

1. **网页端论文阅读**：
   在网页端 ChatGPT 的「论文阅读」项目或对话窗口中，像平时一样讨论论文的方法、公式、实验与启示。
2. **一键同步**：
   - 网页右上角会出现一个悬浮胶囊按钮：**【📥 同步到论文库】**（前置圆点为 🟢 绿色表示本地服务在线）。
   - 点击该按钮，脚本自动提取当前会话（优先通过原生接口获取最精确的结构树，支持公式与代码），并 POST 推送给本地端。
   - 页面弹出提示：`✅ 同步成功！已接收并触发草稿同步`。
3. **私有草稿查看与审核**：
   在终端查看新入库的草稿：
   ```bash
   python -m paper_sync list --status draft
   python -m paper_sync show <paper_id>
   ```
   私有草稿保存在 `paper_sync_data/papers/<paper_id>/draft.md`，内含 Machine 自动提炼区与 Human 人工笔记区。
4. **安全审核与一键发布**：
   ```bash
   python -m paper_sync approve <paper_id>     # 标记审核通过
   python -m paper_sync publish <paper_id>     # 安全扫描无敏感词后导出并 push 上线
   ```
   约 1 分钟后即可在博客 [`/papers/`](https://github.com/yuanshen-nima/boke) 页面看到精美排版的论文精读文章！

---

## 💡 常见问题与技巧

- **Q：我没开本地服务，点了按钮会怎样？**
  - 脚本会自动检测到本地服务未运行，并**自动将当前会话打包下载为 `.json` 文件**，并弹出提示。你只需把它拖入 `paper_sync_data/inbox/` 目录，下次同步时就会自动入库。
- **Q：同一篇论文讨论了多次，会产生重复文章吗？**
  - 不会。系统内置同一性判定引擎（DOI > arXiv > 标题），多次讨论会自动合并进同一篇论文的草稿中，且**绝不覆盖你写过的人工笔记**。
- **Q：如何开机自启本地接收服务？**
  - 可以把 `paper_sync\start-server.bat` 的快捷方式放入 Windows 开机启动文件夹（按 `Win + R` 输入 `shell:startup` 回车），即可随电脑启动在后台常驻。
- **Q：脚本版本如何升级？**
  - 打开 `paper_sync/chatgpt-paper-sync.user.js`，全选覆盖油猴里已有的旧脚本并保存即可。当前版本 `1.1.1`。

---

## 🛠️ 提取失败排查（v1.1.1）

按钮点击后若提示 **「提取失败：页面里没找到消息节点」**，说明脚本的两种提取途径都没拿到内容。v1.1.1 的提取顺序是：

1. **站内接口**（最优先）：先取 `/api/auth/session` 的 accessToken，再请求 `/backend-api/conversation/<id>`，拿到官方完整消息树（含公式、代码，质量最好）。
2. **DOM 多级选择器**：`article[data-testid^="conversation-turn-"]` → `[data-message-author-role]` → `main article` → `main .markdown`。
3. **按文案切分**：用「你说：/ ChatGPT 说:」这类标签切分正文，任何 UI 结构都能兜底。
4. **等待重试**：首次为空会等待 1.2 秒再抓一次（应对懒渲染）。

如果仍然失败，按下面顺序排查：

| 现象 | 原因 | 处理 |
|---|---|---|
| Toast 里 `article=0 role节点=0 markdown=0 main=无` | 页面未加载完 / 不在会话页 | 等页面完全加载后重试；确认地址栏是 `.../c/<会话ID>` |
| `article=N` 但 `collected=0` | 消息折叠或正文为空 | 滚动到对话底部再点；按 F12 看 `[PaperSync] DOM 诊断` 里的 `sampleHtml` |
| 接口 401/403 | 会话过期或需要额外校验 | 刷新页面重新登录后重试（脚本会自动降级为 DOM 提取） |
| 无 Toast、按钮无反应 | 脚本未生效 | 油猴里确认脚本已启用、「用户脚本」开关已打开 |

**调试入口**：按 `F12` → Console，过滤 `[PaperSync]`，能看到接口状态码、DOM 诊断计数和首个节点的 HTML 片段，便于定位。

**永远可用的兜底**：`Shift + 点击` 按钮 = 只下载 JSON 不推送，适合本地服务没开时先存一份到 `paper_sync_data/inbox/`。

---

## ⚠️ 提示「连不上本地服务（127.0.0.1:8765）」怎么办

这条提示说明**提取已经成功**，只是本地接收服务没在跑（按钮左侧的小圆点是灰色）。二选一：

**方式一（推荐）：把服务跑起来，再点一次按钮**

```cmd
:: 在仓库根目录双击，或命令行执行
paper_sync\start-server.bat
```
看到下面这行就代表就绪，窗口**不要关**（关掉即停止服务）：
```
PaperSync 本地接收服务已启动: http://127.0.0.1:8765
```
此时按钮的圆点会变绿，再点【📥 同步到论文库】就会直接入库并自动生成草稿。

> 想开机常驻：把 `start-server.bat` 的快捷方式放进 `Win + R` → `shell:startup`。

**方式二：用已下载的 JSON 直接导入**

脚本会先把会话下载成 `chatgpt-web-<会话ID>.json`，在仓库根目录执行：

```cmd
python -m paper_sync import-note "%USERPROFILE%\Downloads\chatgpt-web-<会话ID>.json"
```

它会自动把文件放进 inbox 并立即同步出草稿。

**排查连接问题**：在本机浏览器直接打开 <http://127.0.0.1:8765/health>，正常应返回 `{"ok": true, ...}`。
若打不开，检查：① 服务窗口是否被关掉；② 8765 端口是否被其它程序占用（`netstat -ano | findstr 8765`）。

---

## 🔒 配置文件的 BOM 兼容说明

`paper_sync_data/config.json`、`digest/config.json` 等配置现在按 **UTF-8 with BOM 兼容**方式读取。原因是：记事本 / Windows PowerShell 5.1 保存的 UTF-8 文件常带 BOM，旧实现会静默解析失败并回退默认值，导致 `project_ids` 白名单、`ai.enabled` 开关**无提示失效**。若你之前遇到过「改了 config.json 却没生效」，升级后再试即可。
