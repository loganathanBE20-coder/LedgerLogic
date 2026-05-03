/* ============================================================
   ELECTORAL ASSISTANT — Floating Chat Widget (chatwidget.js)
   Powered by Gemini 1.5 Flash via /api/chat
   ============================================================ */

(function () {
    'use strict';

    /* ── Configuration ─────────────────────────────────────── */
    const GREETING = 'Welcome to the chat, Electoral Assistant.';
    const BLO_FALLBACK = 'I only assist with election education. For administrative issues, please contact your Booth Level Officer (BLO).';

    /* ── Pre-built educational responses (menu buttons) ─────── */
    const MENU_RESPONSES = {
        security: `<strong>Security: Why OTP?</strong><br><br>` +
            `When you vote online through LedgerLogic, your identity is verified via a <strong>one-time password (OTP)</strong> sent to your registered mobile number.<br><br>` +
            `This ensures:<br>` +
            `• <strong>One person, one vote</strong> — only the registered phone holder can authenticate.<br>` +
            `• <strong>Identity theft prevention</strong> — even if someone knows your name, they cannot vote without your phone.<br>` +
            `• <strong>Tamper-proof verification</strong> — every OTP event is logged in the audit trail for public verification.<br><br>` +
            `The OTP is generated server-side and expires after one use. Invalid attempts are flagged as security threats.`,

        transparency: `<strong>Transparency: The Ledger</strong><br><br>` +
            `LedgerLogic maintains a <strong>Public Ledger</strong> — a real-time, immutable record of all voting activity.<br><br>` +
            `How it keeps your vote secure and fair:<br>` +
            `• Every vote cast is <strong>hashed and uploaded</strong> to the Data Uploaded log in real time.<br>` +
            `• Every system interaction — OTP generation, identity verification, vote casting — is recorded in the <strong>Audit Trail</strong>.<br>` +
            `• Any unauthorized access attempt is flagged in the <strong>Attack Detection</strong> log.<br><br>` +
            `The full source code and database are publicly auditable via the "Source Code" and "Database" buttons, ensuring <strong>no hidden algorithms or black boxes</strong>.`,

        legal: `<strong>Your Legal Rights — Section 49A</strong><br><br>` +
            `Under <strong>Section 49A of the Representation of the People Act</strong>, if someone has already voted in your name (a "proxied" or tendered vote), you still have the <strong>legal right to cast a tendered ballot</strong>.<br><br>` +
            `What to do:<br>` +
            `• Inform the <strong>Presiding Officer</strong> at your polling station immediately.<br>` +
            `• You will be issued a <strong>tendered ballot paper</strong> to cast your vote.<br>` +
            `• Your tendered vote is recorded separately and can be counted during a recount or dispute.<br><br>` +
            `<strong>Your vote is your constitutional right — no one can take it away.</strong>`
    };

    /* ── State ─────────────────────────────────────────────── */
    let isOpen = false;
    let chatHistory = []; // for Gemini context

    /* ── DOM Construction ──────────────────────────────────── */

    function createWidget() {
        // Floating Action Button
        const fab = document.createElement('button');
        fab.id = 'chat-fab';
        fab.className = 'chat-fab';
        fab.setAttribute('aria-label', 'Open Electoral Assistant Chat');
        fab.innerHTML = `
            <svg class="chat-fab-icon chat-fab-icon-msg" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
            </svg>
            <svg class="chat-fab-icon chat-fab-icon-close" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="display:none;">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
            <span class="chat-fab-pulse"></span>
        `;
        document.body.appendChild(fab);

        // Chat Window
        const win = document.createElement('div');
        win.id = 'chat-window';
        win.className = 'chat-window';
        win.innerHTML = `
            <div class="chat-window-header">
                <div class="chat-window-header-left">
                    <div class="chat-window-avatar">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                  d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                        </svg>
                    </div>
                    <div>
                        <div class="chat-window-title">Electoral Assistant</div>
                        <div class="chat-window-status">
                            <span class="chat-window-status-dot"></span>
                            Gemini 1.5 Flash
                        </div>
                    </div>
                </div>
                <button class="chat-window-close" id="chat-close-btn" aria-label="Close Chat">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                    </svg>
                </button>
            </div>

            <div class="chat-messages" id="chat-messages"></div>

            <div class="chat-menu" id="chat-menu">
                <button class="chat-menu-btn chat-menu-btn-security" data-topic="security">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>
                    Security: Why OTP?
                </button>
                <button class="chat-menu-btn chat-menu-btn-transparency" data-topic="transparency">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/></svg>
                    Transparency: The Ledger
                </button>
                <button class="chat-menu-btn chat-menu-btn-legal" data-topic="legal">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3"/></svg>
                    My Legal Rights
                </button>
                <button class="chat-menu-btn chat-menu-btn-other" data-topic="other">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/></svg>
                    Other
                </button>
            </div>

            <div class="chat-input-area" id="chat-input-area">
                <input type="text" class="chat-input" id="chat-input"
                       placeholder="Ask about the election..." autocomplete="off" />
                <button class="chat-send-btn" id="chat-send-btn" aria-label="Send Message">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
                    </svg>
                </button>
            </div>
        `;
        document.body.appendChild(win);

        // Bind events
        fab.addEventListener('click', toggleChat);
        document.getElementById('chat-close-btn').addEventListener('click', toggleChat);

        // Menu buttons
        document.querySelectorAll('.chat-menu-btn').forEach(btn => {
            btn.addEventListener('click', () => handleMenuClick(btn.dataset.topic));
        });

        // Send
        document.getElementById('chat-send-btn').addEventListener('click', handleSend);
        document.getElementById('chat-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') handleSend();
        });
    }

    /* ── Toggle Chat ───────────────────────────────────────── */

    function toggleChat() {
        isOpen = !isOpen;
        const win = document.getElementById('chat-window');
        const fab = document.getElementById('chat-fab');
        const msgIcon = fab.querySelector('.chat-fab-icon-msg');
        const closeIcon = fab.querySelector('.chat-fab-icon-close');
        const pulse = fab.querySelector('.chat-fab-pulse');

        if (isOpen) {
            win.classList.add('chat-window-open');
            fab.classList.add('chat-fab-active');
            msgIcon.style.display = 'none';
            closeIcon.style.display = 'block';
            if (pulse) pulse.style.display = 'none';

            // Auto-greeting on first open
            const msgs = document.getElementById('chat-messages');
            if (msgs.children.length === 0) {
                addBotMessage(GREETING);
            }
        } else {
            win.classList.remove('chat-window-open');
            fab.classList.remove('chat-fab-active');
            msgIcon.style.display = 'block';
            closeIcon.style.display = 'none';
        }
    }

    /* ── Menu Click Handler ────────────────────────────────── */

    function handleMenuClick(topic) {
        if (topic === 'other') {
            // Focus the input for custom question
            const input = document.getElementById('chat-input');
            input.focus();
            input.placeholder = 'Type your election question...';
            return;
        }

        // Add user "selection" bubble
        const labels = {
            security: 'Security: Why OTP?',
            transparency: 'Transparency: The Ledger',
            legal: 'My Legal Rights'
        };
        addUserMessage(labels[topic]);

        // Show typing, then respond
        showTyping();
        setTimeout(() => {
            hideTyping();
            addBotMessageHTML(MENU_RESPONSES[topic]);
        }, 600);
    }

    /* ── Send Handler (free-form + Gemini) ─────────────────── */

    async function handleSend() {
        const input = document.getElementById('chat-input');
        const msg = input.value.trim();
        if (!msg) return;

        addUserMessage(msg);
        input.value = '';

        // Check for greeting
        const lower = msg.toLowerCase();
        if (lower === 'hi' || lower === 'hello' || lower === 'hey') {
            showTyping();
            setTimeout(() => {
                hideTyping();
                addBotMessage(GREETING);
            }, 400);
            return;
        }

        // Send to Gemini via backend
        showTyping();
        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: msg,
                    history: chatHistory.slice(-10) // last 10 messages for context
                })
            });

            hideTyping();

            if (res.ok) {
                const data = await res.json();
                if (data.reply) {
                    addBotMessageHTML(data.reply);
                    // Track history
                    chatHistory.push({ role: 'user', text: msg });
                    chatHistory.push({ role: 'assistant', text: data.reply });
                } else {
                    addBotMessage(BLO_FALLBACK);
                }
            } else {
                addBotMessage(BLO_FALLBACK);
            }
        } catch (err) {
            hideTyping();
            addBotMessage(BLO_FALLBACK);
            console.error('Chat error:', err);
        }
    }

    /* ── Message Helpers ───────────────────────────────────── */

    function addUserMessage(text) {
        const container = document.getElementById('chat-messages');
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble chat-bubble-user';
        bubble.textContent = text;
        container.appendChild(bubble);
        scrollToBottom();
    }

    function addBotMessage(text) {
        const container = document.getElementById('chat-messages');
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble chat-bubble-bot';
        bubble.textContent = text;
        container.appendChild(bubble);
        scrollToBottom();
    }

    function addBotMessageHTML(html) {
        const container = document.getElementById('chat-messages');
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble chat-bubble-bot';
        bubble.innerHTML = html;
        container.appendChild(bubble);
        scrollToBottom();
    }

    function showTyping() {
        const container = document.getElementById('chat-messages');
        // Remove existing typing indicator
        hideTyping();
        const typing = document.createElement('div');
        typing.className = 'chat-bubble chat-bubble-bot chat-typing';
        typing.id = 'chat-typing-indicator';
        typing.innerHTML = `
            <div class="chat-typing-dots">
                <span></span><span></span><span></span>
            </div>
        `;
        container.appendChild(typing);
        scrollToBottom();
    }

    function hideTyping() {
        const el = document.getElementById('chat-typing-indicator');
        if (el) el.remove();
    }

    function scrollToBottom() {
        const container = document.getElementById('chat-messages');
        requestAnimationFrame(() => {
            container.scrollTop = container.scrollHeight;
        });
    }

    /* ── Initialize on DOM Ready ───────────────────────────── */
    function init() {
        createWidget();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
