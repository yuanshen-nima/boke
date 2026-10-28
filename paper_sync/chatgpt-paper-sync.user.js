// ==UserScript==
// @name         ChatGPT 论文阅读会话一键同步到博客知识库 (PaperSync)
// @namespace    https://github.com/yuanshen-nima/boke
// @version      1.2.0
// @description  在 ChatGPT 页面上一键提取当前论文讨论会话，直接推送到本地 PaperSync 知识库生成私有草稿
// @author       liang boyu
// @match        https://chatgpt.com/*
// @match        https://chat.openai.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_addStyle
// @grant        GM_setValue
// @grant        GM_getValue
// @connect      127.0.0.1
// @connect      localhost
// @run-at       document-idle
// ==/UserScript==

(function () {
    'use strict';

    const LOCAL_SERVER = 'http://127.0.0.1:8765';
    const LOG = (...a) => console.log('[PaperSync]', ...a);
    let isServerAlive = false;

    GM_addStyle(`
        #papersync-float-btn {
            position: fixed;
            top: 12px;
            right: 150px;
            z-index: 2147483000;
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 7px 14px;
            background: rgba(32, 33, 35, 0.9);
            backdrop-filter: blur(8px);
            color: #ececf1;
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 20px;
            font-size: 13px;
            font-weight: 500;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.28);
            transition: all 0.2s ease;
            user-select: none;
        }
        #papersync-float-btn:hover {
            background: rgba(52, 53, 65, 0.98);
            border-color: rgba(255, 255, 255, 0.32);
            transform: translateY(-1px);
        }
        #papersync-float-btn.busy { opacity: 0.75; pointer-events: none; }
        #papersync-status-dot {
            width: 8px; height: 8px; border-radius: 50%;
            background: #8e8ea0; transition: background 0.3s;
        }
        #papersync-status-dot.online { background: #10a37f; box-shadow: 0 0 6px #10a37f; }
        #papersync-toast {
            position: fixed; top: 58px; right: 150px; z-index: 2147483001;
            padding: 11px 16px; border-radius: 10px; font-size: 13px; color: #fff;
            background: #1f2023; border: 1px solid rgba(255, 255, 255, 0.12);
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.45);
            opacity: 0; transform: translateY(-8px);
            transition: all 0.25s ease; pointer-events: none;
            max-width: 420px; line-height: 1.55; word-break: break-word;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        #papersync-toast.show { opacity: 1; transform: translateY(0); }
        #papersync-toast code { background: rgba(255,255,255,.1); padding: 1px 4px; border-radius: 4px; font-size: 11px; }
    `);

    const toast = document.createElement('div');
    toast.id = 'papersync-toast';
    document.body.appendChild(toast);

    function showToast(html, ok = true, duration = 4000) {
        toast.innerHTML = html;
        toast.style.borderColor = ok ? '#10a37f' : '#ef4444';
        toast.classList.add('show');
        clearTimeout(showToast._t);
        showToast._t = setTimeout(() => toast.classList.remove('show'), duration);
    }

    // ---------------- 服务与工具 ----------------
    function checkServerHealth() {
        GM_xmlhttpRequest({
            method: 'GET',
            url: `${LOCAL_SERVER}/health`,
            timeout: 2000,
            onload: r => {
                isServerAlive = r.status === 200;
                const dot = document.getElementById('papersync-status-dot');
                if (dot) dot.classList.toggle('online', isServerAlive);
                if (isServerAlive) {
                    try {
                        const info = JSON.parse(r.responseText);
                        if (info && info.inbox_dir) GM_setValue('inbox_dir', info.inbox_dir);
                    } catch (e) { /* ignore */ }
                }
            },
            onerror: () => {
                isServerAlive = false;
                const dot = document.getElementById('papersync-status-dot');
                if (dot) dot.classList.remove('online');
            }
        });
    }

    function getConversationId() {
        const m = window.location.pathname.match(/\/c\/([A-Za-z0-9_-]{8,})/);
        return m ? m[1] : null;
    }

    function pageTitle() {
        const t = (document.title || '').replace(/\s*[-|]\s*ChatGPT.*$/i, '').trim();
        return t || 'ChatGPT 论文阅读会话';
    }

    const ROLE_LABEL = /^(You said:|ChatGPT said:|你说：|你说:|ChatGPT 说：|ChatGPT 说:)\s*/i;

    function cleanText(raw) {
        if (!raw) return '';
        let t = raw.replace(/\r\n/g, '\n').replace(/\u00a0/g, ' ');
        t = t.replace(ROLE_LABEL, '');
        // 逐行 trim，并把连续空行折叠成一个
        const out = [];
        for (const line of t.split('\n')) {
            const s = line.trim();
            if (s === '' && (out.length === 0 || out[out.length - 1] === '')) continue;
            out.push(s);
        }
        return out.join('\n').trim();
    }

    // ---------------- 提取途径 1：站内原生接口 ----------------
    async function getAccessToken() {
        try {
            const r = await fetch('/api/auth/session', { credentials: 'include' });
            if (r.ok) {
                const j = await r.json();
                return j.accessToken || null;
            }
        } catch (e) {
            LOG('获取 accessToken 失败', e);
        }
        return null;
    }

    async function apiFetchConversation(convId) {
        const token = await getAccessToken();
        const url = `/backend-api/conversation/${convId}`;
        const timeoutMs = 45000; // 长论文会话 JSON 大 (1~3MB)，给足 45 秒超时，避免被提前 abort

        const btn = document.getElementById('papersync-float-btn');

        // 尝试方式 1：标准 window.fetch (带 45s 超时)
        for (let attempt = 1; attempt <= 2; attempt++) {
            try {
                if (btn) btn.innerHTML = `⏳ 读取接口 (${attempt}/2)…`;
                const headers = {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                };
                if (token) headers['Authorization'] = `Bearer ${token}`;
                LOG(`尝试接口 (第 ${attempt} 次)`, url, token ? '(带 token)' : '(仅 Cookie)');

                const ctrl = new AbortController();
                const timer = setTimeout(() => ctrl.abort(new Error(`API 超时 (${timeoutMs / 1000}s)`)), timeoutMs);

                const resp = await fetch(url, {
                    credentials: 'include',
                    headers,
                    signal: ctrl.signal
                });
                clearTimeout(timer);

                LOG('接口响应状态', url, resp.status);
                if (resp.status === 200) {
                    const data = await resp.json();
                    if (data && data.mapping && Object.keys(data.mapping).length) {
                        LOG('接口提取成功，节点数', Object.keys(data.mapping).length);
                        return data;
                    }
                }
            } catch (e) {
                LOG(`接口异常 (第 ${attempt} 次)`, url, e);
            }
        }

        // 尝试方式 2：使用油猴特权 GM_xmlhttpRequest 兜底 (绕过前端拦截与跨域限制)
        try {
            if (btn) btn.innerHTML = '⏳ GM读取接口…';
            LOG('尝试 GM_xmlhttpRequest 备用通道', url);
            const gmData = await new Promise(resolve => {
                const headers = { 'Accept': 'application/json' };
                if (token) headers['Authorization'] = `Bearer ${token}`;
                GM_xmlhttpRequest({
                    method: 'GET',
                    url: `${window.location.origin}${url}`,
                    headers,
                    timeout: 45000,
                    onload: res => {
                        if (res.status === 200) {
                            try {
                                const d = JSON.parse(res.responseText);
                                if (d && d.mapping && Object.keys(d.mapping).length) {
                                    resolve(d);
                                    return;
                                }
                            } catch (err) { /* ignore */ }
                        }
                        resolve(null);
                    },
                    onerror: () => resolve(null),
                    ontimeout: () => resolve(null)
                });
            });
            if (gmData) {
                LOG('GM 接口提取成功，节点数', Object.keys(gmData.mapping).length);
                return gmData;
            }
        } catch (e) {
            LOG('GM 接口异常', e);
        }

        return null;
    }

    // ---------------- 提取途径 2：DOM 多级选择器 ----------------
    function pickTurnNodes() {
        // 策略 1：[data-testid^="conversation-turn-"] (不限 article，div/section 均可)
        let nodes = Array.from(document.querySelectorAll('[data-testid^="conversation-turn-"], [data-testid*="conversation-turn"]'));
        if (nodes.length) return { nodes, mode: 'test-id-turn' };

        // 策略 2：ChatGPT 常用类名
        nodes = Array.from(document.querySelectorAll('div[class*="conversation-turn"], [class*="agent-turn"], [class*="user-turn"]'));
        if (nodes.length) return { nodes, mode: 'class-turn' };

        // 策略 3：角色属性节点
        nodes = Array.from(document.querySelectorAll('[data-message-author-role]'));
        if (nodes.length) return { nodes, mode: 'role-attr' };

        // 策略 4：消息唯一标识块
        nodes = Array.from(document.querySelectorAll('[data-message-id]'));
        if (nodes.length) return { nodes, mode: 'message-id' };

        // 策略 5：main 内部的 article / section
        nodes = Array.from(document.querySelectorAll('main article, main section'));
        if (nodes.length) return { nodes, mode: 'main-article' };

        // 策略 6：所有 markdown / prose 块
        const mds = Array.from(document.querySelectorAll('main .markdown, main [class*="markdown"], main .prose, main [class*="prose"]'));
        if (mds.length) return { nodes: mds, mode: 'prose-blocks' };

        return { nodes: [], mode: 'none' };
    }

    function nodeRole(node, index, mode) {
        if (mode === 'role-attr') {
            return node.getAttribute('data-message-author-role') || (index % 2 === 0 ? 'user' : 'assistant');
        }
        const innerRole = node.querySelector('[data-message-author-role]');
        if (innerRole) return innerRole.getAttribute('data-message-author-role');
        const testid = ((node.getAttribute('data-testid') || '') + ' ' + (node.className || '')).toLowerCase();
        if (testid.includes('user')) return 'user';
        if (testid.includes('assistant') || testid.includes('agent')) return 'assistant';
        // 如果包含复制/重试按钮，或者包含复杂的 markdown / prose 结构，大概率是 assistant
        if (node.querySelector('.markdown, [class*="markdown"], .prose, [class*="prose"], [data-testid*="copy"], button[aria-label*="Copy"], button[aria-label*="复制"]')) {
            return 'assistant';
        }
        // 按奇偶推断：ChatGPT 对话总是 user 开头
        return index % 2 === 0 ? 'user' : 'assistant';
    }

    function nodeText(node, mode) {
        // 克隆节点并过滤无关按钮与无障碍图标
        const clone = node.cloneNode(true);
        const toRemove = clone.querySelectorAll('button, svg, [role="button"], [data-testid*="action"], [class*="action"], .sr-only');
        toRemove.forEach(el => el.remove());

        const container =
            clone.querySelector('.markdown') ||
            clone.querySelector('[class*="markdown"]') ||
            clone.querySelector('.prose') ||
            clone.querySelector('[class*="prose"]') ||
            clone.querySelector('[class*="whitespace-pre-wrap"]') ||
            clone;
        return cleanText(container.innerText || container.textContent || '');
    }

    // 策略 5：按 "You said / ChatGPT said / User / Assistant" 文案切分正文
    function splitByLabels() {
        const main = document.querySelector('main');
        if (!main) return [];
        const clone = main.cloneNode(true);
        clone.querySelectorAll('button, svg, [role="button"], nav').forEach(el => el.remove());
        const text = clone.innerText || '';
        const re = /(?:^|\n)\s*(You said:|ChatGPT said:|你说：|你说:|ChatGPT 说：|ChatGPT 说:|User:|Assistant:|Model:)\s*/g;
        const matches = [...text.matchAll(re)];
        if (!matches.length) return [];
        const parts = [];
        matches.forEach((mm, i) => {
            const start = mm.index + mm[0].length;
            const end = i + 1 < matches.length ? matches[i + 1].index : text.length;
            const role = /ChatGPT|Assistant|Model/i.test(mm[1]) ? 'assistant' : 'user';
            const body = cleanText(text.slice(start, end));
            if (body) parts.push({ role, text: body });
        });
        return parts;
    }

    function extractFromDOM() {
        const { nodes, mode } = pickTurnNodes();
        const messages = [];
        nodes.forEach((node, i) => {
            const role = nodeRole(node, i, mode);
            const text = nodeText(node, mode);
            if (text) messages.push({ role, text });
        });

        let usedMode = mode;
        if (!messages.length) {
            const labeled = splitByLabels();
            if (labeled.length) {
                messages.push(...labeled);
                usedMode = 'label-split';
            }
        }

        // 策略 6 兜底：如果依然没拿到独立消息，检查 main 中是否有现成的长文精读
        if (!messages.length) {
            const main = document.querySelector('main');
            if (main) {
                const clone = main.cloneNode(true);
                clone.querySelectorAll('button, svg, nav').forEach(el => el.remove());
                const fullText = cleanText(clone.innerText || '');
                if (fullText && fullText.length > 500 && (fullText.includes('论文精读') || fullText.includes('论文解读') || fullText.includes('总体深度解读'))) {
                    messages.push({ role: 'assistant', text: fullText });
                    usedMode = 'main-fulltext';
                }
            }
        }

        const diag = {
            mode: usedMode,
            turns: document.querySelectorAll('[data-testid^="conversation-turn-"], [data-testid*="conversation-turn"]').length,
            articles: document.querySelectorAll('article').length,
            roleNodes: document.querySelectorAll('[data-message-author-role]').length,
            markdownBlocks: document.querySelectorAll('main .markdown, main [class*="markdown"], main .prose').length,
            mainExists: !!document.querySelector('main'),
            collected: messages.length,
            sampleHtml: nodes[0] ? String(nodes[0].outerHTML || '').slice(0, 400) : ''
        };
        LOG('DOM 诊断', diag);

        return {
            payload: {
                source: 'chatgpt_web',
                conversation_id: getConversationId() || `web-${Date.now()}`,
                title: pageTitle(),
                project_id: 'paper_reading',
                messages
            },
            diag
        };
    }

    const sleep = ms => new Promise(r => setTimeout(r, ms));

    // ---------------- 备用下载 ----------------
    function downloadPayload(data, note) {
        const filename = `chatgpt-web-${data.conversation_id || Date.now()}.json`;
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);

        let inboxDir = '';
        try { inboxDir = GM_getValue('inbox_dir', '') || ''; } catch (e) { /* ignore */ }
        const where = inboxDir ? `<code>${inboxDir}</code>` : '<code>paper_sync_data/inbox</code>';

        showToast(
            `⚠️ ${note || '本地服务未连接'}<br/>` +
            `已下载 <b>${filename}</b>，两种入库方式任选其一：<br/>` +
            `① 双击 <code>paper_sync\\start-server.bat</code> 启动服务后，重新点按钮；<br/>` +
            `② 把它放入 ${where}，或在仓库目录执行：<br/>` +
            `<code>python -m paper_sync import-note "下载目录\\${filename}"</code>`,
            false, 15000
        );
    }

    // ---------------- 主流程 ----------------
    async function syncCurrentConversation(ev) {
        const btn = document.getElementById('papersync-float-btn');
        const convId = getConversationId();
        if (!convId) {
            showToast('⚠️ 当前页面不是具体会话（URL 中没有 /c/...），请先打开论文对话', false);
            return;
        }

        const originalHTML = btn.innerHTML;
        btn.classList.add('busy');

        let payload = null;

        // 1) 原生接口
        btn.innerHTML = '⏳ 读取会话…';
        const apiData = await apiFetchConversation(convId);
        if (apiData) {
            payload = apiData;
        } else {
            // 2) DOM 提取（首次为空时等待渲染再重试一次）
            btn.innerHTML = '⏳ 解析页面…';
            let { payload: domPayload, diag } = extractFromDOM();
            if (!domPayload.messages.length) {
                await sleep(1200);
                ({ payload: domPayload, diag } = extractFromDOM());
            }
            if (domPayload.messages.length) {
                payload = domPayload;
            } else {
                btn.innerHTML = originalHTML;
                btn.classList.remove('busy');
                showToast(
                    `❌ 提取失败：页面里没找到消息节点。<br/>` +
                    `诊断：turn=${diag.turns || 0}，role节点=${diag.roleNodes}，` +
                    `markdown=${diag.markdownBlocks}，main=${diag.mainExists ? '有' : '无'}。<br/>` +
                    `请确认会话已加载完成，并按 F12 看 Console 的 <code>[PaperSync]</code> 日志。`,
                    false, 12000
                );
                console.warn('[PaperSync] 提取失败诊断', diag,
                    '如果页面结构特殊，请把这段日志发给开发者。');
                return;
            }
        }

        // Shift+点击：只下载不推送
        if (ev && ev.shiftKey) {
            btn.innerHTML = originalHTML;
            btn.classList.remove('busy');
            downloadPayload(payload, '已跳过推送（Shift+点击）');
            return;
        }

        btn.innerHTML = '🚀 推送中…';

        GM_xmlhttpRequest({
            method: 'POST',
            url: `${LOCAL_SERVER}/api/inbox`,
            data: JSON.stringify(payload),
            headers: { 'Content-Type': 'application/json; charset=utf-8' },
            timeout: 60000,
            onload: resp => {
                btn.innerHTML = originalHTML;
                btn.classList.remove('busy');
                let res = null;
                try { res = JSON.parse(resp.responseText); } catch (e) { /* ignore */ }
                if (resp.status === 200 && res && res.ok) {
                    const warn = res.sync_status && res.sync_status !== 'success';
                    showToast(
                        `<b>${warn ? '⚠️ 已入库（同步有告警）' : '✅ 同步成功！'}</b><br/>` +
                        `${res.message || ''}<br/>` +
                        `<span style="color:#8e8ea0;font-size:11px;">文件：${res.file || ''}</span>`,
                        !warn, 6000
                    );
                } else {
                    downloadPayload(payload, `本地服务返回 ${resp.status}`);
                }
            },
            onerror: () => {
                btn.innerHTML = originalHTML;
                btn.classList.remove('busy');
                isServerAlive = false;
                const dot = document.getElementById('papersync-status-dot');
                if (dot) dot.classList.remove('online');
                downloadPayload(payload, '连不上本地服务（127.0.0.1:8765）');
            }
        });
    }

    // ---------------- 注入按钮 ----------------
    function ensureButton() {
        if (!document.body) return;
        if (document.getElementById('papersync-float-btn')) return;
        const btn = document.createElement('button');
        btn.id = 'papersync-float-btn';
        btn.innerHTML = '<span id="papersync-status-dot"></span><span>📥 同步到论文库</span>';
        btn.title = '一键把当前 ChatGPT 会话同步到论文知识库（Shift+点击 = 只下载 JSON）';
        btn.addEventListener('click', syncCurrentConversation);
        document.body.appendChild(btn);
        checkServerHealth();
    }

    ensureButton();
    setInterval(ensureButton, 2000);
    setInterval(checkServerHealth, 15000);
})();
