// ==UserScript==
// @name         ChatGPT 论文阅读会话一键同步到博客知识库 (PaperSync)
// @namespace    https://github.com/yuanshen-nima/boke
// @version      1.0.0
// @description  在 ChatGPT 页面上一键提取当前论文讨论会话，直接推送到本地 PaperSync 知识库生成私有草稿
// @author       liang boyu
// @match        https://chatgpt.com/*
// @match        https://chat.openai.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_addStyle
// @grant        GM_notification
// @connect      127.0.0.1
// @connect      localhost
// @run-at       document-idle
// ==/UserScript==

(function () {
    'use strict';

    const LOCAL_SERVER = 'http://127.0.0.1:8765';
    let isServerAlive = false;

    // 注入悬浮按钮样式
    GM_addStyle(`
        #papersync-float-btn {
            position: fixed;
            top: 14px;
            right: 130px;
            z-index: 99999;
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 7px 14px;
            background: rgba(32, 33, 35, 0.85);
            backdrop-filter: blur(8px);
            color: #ececf1;
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 20px;
            font-size: 13px;
            font-weight: 500;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
            transition: all 0.2s ease;
        }
        #papersync-float-btn:hover {
            background: rgba(52, 53, 65, 0.95);
            border-color: rgba(255, 255, 255, 0.3);
            transform: translateY(-1px);
        }
        #papersync-status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #8e8ea0;
            transition: background 0.3s;
        }
        #papersync-status-dot.online {
            background: #10a37f;
            box-shadow: 0 0 6px #10a37f;
        }
        #papersync-toast {
            position: fixed;
            top: 60px;
            right: 130px;
            z-index: 100000;
            padding: 10px 18px;
            border-radius: 8px;
            font-size: 13px;
            color: #fff;
            background: #202123;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
            opacity: 0;
            transform: translateY(-8px);
            transition: all 0.25s ease;
            pointer-events: none;
            max-width: 380px;
            line-height: 1.5;
        }
        #papersync-toast.show {
            opacity: 1;
            transform: translateY(0);
        }
    `);

    // 创建提示框
    const toast = document.createElement('div');
    toast.id = 'papersync-toast';
    document.body.appendChild(toast);

    function showToast(msg, isSuccess = true, duration = 3500) {
        toast.innerHTML = msg;
        toast.style.borderColor = isSuccess ? '#10a37f' : '#ef4444';
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), duration);
    }

    // 检查本地服务状态
    function checkServerHealth() {
        GM_xmlhttpRequest({
            method: 'GET',
            url: `${LOCAL_SERVER}/health`,
            timeout: 2000,
            onload: function (resp) {
                const dot = document.getElementById('papersync-status-dot');
                if (resp.status === 200) {
                    isServerAlive = true;
                    if (dot) dot.classList.add('online');
                } else {
                    isServerAlive = false;
                    if (dot) dot.classList.remove('online');
                }
            },
            onerror: function () {
                isServerAlive = false;
                const dot = document.getElementById('papersync-status-dot');
                if (dot) dot.classList.remove('online');
            }
        });
    }

    // 从 URL 提取 conversation_id
    function getConversationId() {
        const m = window.location.pathname.match(/\/c\/([a-f0-9-]+)/i);
        return m ? m[1] : null;
    }

    // 从 DOM 提取对话备用
    function extractFromDOM() {
        const titleEl = document.querySelector('title');
        let title = titleEl ? titleEl.innerText.replace(/\s*-\s*ChatGPT.*$/i, '').trim() : '论文讨论';
        const messages = [];

        // 查找消息节点
        const turns = document.querySelectorAll('[data-message-author-role]');
        turns.forEach(el => {
            const role = el.getAttribute('data-message-author-role') || 'user';
            const text = el.innerText.trim();
            if (text) {
                messages.push({ role, text });
            }
        });

        return {
            source: 'chatgpt_web',
            conversation_id: getConversationId() || `web-${Date.now()}`,
            title: title || 'ChatGPT 论文阅读会话',
            project_id: 'paper_reading',
            messages: messages
        };
    }

    // 尝试直接调用官方内部接口获取完整干净的 JSON 树
    async function fetchNativeConversation(convId) {
        try {
            const resp = await fetch(`/backend-api/conversation/${convId}`, {
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' }
            });
            if (resp.ok) {
                const data = await resp.json();
                if (data && data.mapping) {
                    return data;
                }
            }
        } catch (e) {
            console.warn('[PaperSync] 原生 API 获取失败，降级为 DOM 提取', e);
        }
        return null;
    }

    // 下载备用 JSON
    function fallbackDownload(data) {
        const filename = `chatgpt-web-${data.conversation_id || Date.now()}.json`;
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
        showToast(`⚠️ 本地服务未运行，已下载为 <b>${filename}</b>。<br/>请将其放入 <code>paper_sync_data/inbox/</code>`, false, 6000);
    }

    // 执行同步主流程
    async function syncCurrentConversation() {
        const btn = document.getElementById('papersync-float-btn');
        const convId = getConversationId();
        if (!convId) {
            showToast('⚠️ 未检测到有效会话，请先进入具体的论文对话', false);
            return;
        }

        const originalText = btn.innerHTML;
        btn.innerHTML = '⏳ 正在提取...';

        let payload = await fetchNativeConversation(convId);
        if (!payload) {
            payload = extractFromDOM();
        }

        if (!payload || (payload.messages && payload.messages.length === 0)) {
            showToast('❌ 提取失败：未在页面中找到消息内容', false);
            btn.innerHTML = originalText;
            return;
        }

        btn.innerHTML = '🚀 正在推送到知识库...';

        // 发送给本地接收服务
        GM_xmlhttpRequest({
            method: 'POST',
            url: `${LOCAL_SERVER}/api/inbox`,
            data: JSON.stringify(payload),
            headers: { 'Content-Type': 'application/json; charset=utf-8' },
            timeout: 10000,
            onload: function (resp) {
                btn.innerHTML = originalText;
                if (resp.status === 200) {
                    try {
                        const res = JSON.parse(resp.responseText);
                        showToast(`<b>✅ 同步成功！</b><br/>${res.message || '已入库'}<br/><span style="color:#8e8ea0;font-size:11px;">文件: ${res.file}</span>`, true, 5000);
                    } catch (e) {
                        showToast('✅ 同步请求已接收！', true);
                    }
                } else {
                    fallbackDownload(payload);
                }
            },
            onerror: function () {
                btn.innerHTML = originalText;
                fallbackDownload(payload);
            }
        });
    }

    // 注入按钮
    function ensureButton() {
        if (document.getElementById('papersync-float-btn')) return;
        const btn = document.createElement('button');
        btn.id = 'papersync-float-btn';
        btn.innerHTML = '<span id="papersync-status-dot"></span><span>📥 同步到论文库</span>';
        btn.title = '将当前 ChatGPT 论文讨论会话推送到本地博客论文库草稿';
        btn.addEventListener('click', syncCurrentConversation);
        document.body.appendChild(btn);
        checkServerHealth();
    }

    // 初始化与路由监听
    ensureButton();
    setInterval(ensureButton, 2000);
    setInterval(checkServerHealth, 10000);

})();
