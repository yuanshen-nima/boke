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
