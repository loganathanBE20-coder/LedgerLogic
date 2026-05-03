/* ============================================================
   DIGITAL ELECTORAL NAVIGATOR — navigator.js
   Self-contained tour engine for LedgerLogic onboarding
   ============================================================ */

(function () {
    'use strict';

    /* ── Tour Step Definitions ─────────────────────────────── */
    const TOUR_STEPS = [
        {
            id: 'heartbeat',
            selector: 'aside.w-\\[300px\\]',
            title: 'System Heartbeat',
            description:
                'This sidebar is the <strong>pulse of the entire election system</strong>. It continuously monitors ' +
                'server liveness and ensures the voting infrastructure hasn\'t been tampered with. If this heartbeat ' +
                'ever stops, it signals a potential breach — alerting administrators instantly.',
            badge: 'LIVE MONITOR',
            position: 'right'
        },
        {
            id: 'data-uploaded',
            selector: '#log-data',
            title: 'Data Uploaded',
            description:
                'Every vote cast is <strong>hashed and uploaded in real time</strong>. This log shows ' +
                'transparent, cryptographic proof that tallies are being recorded faithfully. ' +
                'No single entity can alter these entries without detection — ensuring full transparency.',
            badge: 'TRANSPARENCY',
            position: 'right'
        },
        {
            id: 'audit-trail',
            selector: '#log-changes',
            title: 'Audit Trail — Changes Happened',
            description:
                'Every interaction — from OTP generation to identity verification — is <strong>permanently recorded here</strong>. ' +
                'This immutable log allows the public and independent auditors to verify that no unauthorized modifications occurred. ' +
                'This is the backbone of <strong>fraud prevention</strong>.',
            badge: 'AUDIT LOG',
            position: 'right'
        },
        {
            id: 'security',
            selector: '#log-attack',
            title: 'Security — Attack Detection',
            description:
                'The system actively monitors for <strong>unauthorized threats</strong>: SQL injection attempts, ' +
                'brute-force OTP attacks, and unauthorized access. Every threat is logged with a masked IP address ' +
                'for forensic analysis. This ensures the <strong>integrity of every vote</strong>.',
            badge: 'THREAT INTEL',
            position: 'right'
        },
        {
            id: 'open-verification',
            selectorMultiple: [
                'nav button[title="Database"]',
                'nav button[title="Source Code"]'
            ],
            selector: 'nav button[title="Source Code"]',
            title: 'Open Verification',
            description:
                'These controls grant access to the <strong>Public Ledger (Database)</strong> and the <strong>full source code</strong>. ' +
                'This is "glass-box" auditing — any citizen can inspect the system\'s logic and verify that votes are counted exactly as cast. ' +
                '<strong>No hidden algorithms. No black boxes.</strong>',
            badge: 'GLASS BOX',
            position: 'right'
        },
        {
            id: 'voting-process',
            selector: 'button[aria-label="Open Voting Modal"]',
            title: 'The Voting Process',
            description:
                'To cast a vote, the voter enters their registered details and receives a <strong>one-time password (OTP)</strong> ' +
                'on their mobile phone. This two-factor authentication ensures <strong>"one person, one vote"</strong> — ' +
                'protecting digital identity and preventing impersonation or duplicate voting.',
            badge: 'IDENTITY GATE',
            position: 'bottom'
        },
        {
            id: 'section-49a',
            selector: null, // Centered modal — no target element
            title: 'Section 49A — Your Legal Right',
            description:
                '<div class="tour-legal-badge">⚖️ MANDATORY LEGAL NOTICE</div>' +
                'Under <strong>Section 49A of the Representation of the People Act</strong>, if someone has already voted ' +
                'in your name (a "proxied" or tendered vote), you still have the <strong>legal right to cast a tendered ballot</strong>. ' +
                'Report the issue to your Presiding Officer immediately. Your vote is your constitutional right — ' +
                '<strong>no one can take it away</strong>.',
            badge: 'LEGAL MANDATE',
            position: 'center'
        }
    ];

    /* ── Navigator Class ───────────────────────────────────── */
    class DigitalElectoralNavigator {

        constructor() {
            this.currentStep = -1;
            this.overlay = null;
            this.tooltip = null;
            this.welcomeEl = null;
            this.isActive = false;
            this.blurredElements = [];
        }

        /* ── Public API ────────────────────────────────────── */

        start() {
            if (this.isActive) return;
            this.isActive = true;
            this._showWelcome();
        }

        next() {
            this.currentStep++;
            if (this.currentStep >= TOUR_STEPS.length) {
                this.destroy();
                return;
            }
            this._renderStep(this.currentStep);
        }

        skip() {
            this.destroy();
        }

        destroy() {
            this.isActive = false;
            this.currentStep = -1;

            // Remove overlay
            if (this.overlay) {
                this.overlay.remove();
                this.overlay = null;
            }

            // Remove tooltip
            if (this.tooltip) {
                this.tooltip.remove();
                this.tooltip = null;
            }

            // Remove welcome
            if (this.welcomeEl) {
                this.welcomeEl.remove();
                this.welcomeEl = null;
            }

            // Remove blur from all elements
            this._clearBlur();

            // Re-enable body interaction
            document.body.style.overflow = '';
        }

        /* ── Welcome Splash ────────────────────────────────── */

        _showWelcome() {
            this.welcomeEl = document.createElement('div');
            this.welcomeEl.className = 'tour-welcome';
            this.welcomeEl.innerHTML = `
                <div class="tour-welcome-card">
                    <div class="tour-welcome-icon">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                  d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                        </svg>
                    </div>
                    <h2 class="tour-welcome-title">DIGITAL NAVIGATOR</h2>
                    <p class="tour-welcome-sub">// Interactive Election Education Tour</p>
                    <button class="tour-welcome-start" id="tour-start-btn">
                        Begin Tour
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" style="width:16px;height:16px;">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/>
                        </svg>
                    </button>
                    <button class="tour-welcome-skip" id="tour-skip-welcome-btn">Skip Tour</button>
                </div>
            `;
            document.body.appendChild(this.welcomeEl);

            // Bind buttons
            document.getElementById('tour-start-btn').addEventListener('click', () => {
                this.welcomeEl.remove();
                this.welcomeEl = null;
                this._createOverlay();
                this.next();
            });
            document.getElementById('tour-skip-welcome-btn').addEventListener('click', () => {
                this.destroy();
            });
        }

        /* ── Overlay ───────────────────────────────────────── */

        _createOverlay() {
            this.overlay = document.createElement('div');
            this.overlay.className = 'tour-overlay';
            this.overlay.style.background = 'rgba(10, 12, 16, 0.75)';
            document.body.appendChild(this.overlay);

            // Click on overlay does nothing (user must use buttons)
            this.overlay.addEventListener('click', (e) => e.stopPropagation());
        }

        /* ── Blur Management ───────────────────────────────── */

        _applyBlur(targetEl) {
            this._clearBlur();

            // Blur the direct children of body except our tour elements & the target
            const bodyChildren = Array.from(document.body.children);
            bodyChildren.forEach(child => {
                if (
                    child === this.overlay ||
                    child === this.tooltip ||
                    child === this.welcomeEl ||
                    child.classList.contains('tour-overlay') ||
                    child.classList.contains('tour-tooltip')
                ) return;

                // If this child IS the target or CONTAINS the target, don't blur it entirely
                if (targetEl && (child === targetEl || child.contains(targetEl))) {
                    // Instead, blur sibling elements inside this container
                    this._blurSiblings(child, targetEl);
                } else {
                    child.classList.add('tour-blur-active');
                    this.blurredElements.push(child);
                }
            });
        }

        _blurSiblings(container, targetEl) {
            // Walk up from targetEl to find the direct child of container that holds target
            let targetAncestor = targetEl;
            while (targetAncestor && targetAncestor.parentElement !== container) {
                targetAncestor = targetAncestor.parentElement;
            }

            if (!targetAncestor) return;

            Array.from(container.children).forEach(sibling => {
                if (
                    sibling === targetAncestor ||
                    sibling.contains(targetEl) ||
                    sibling === targetEl
                ) return;

                sibling.classList.add('tour-blur-active');
                this.blurredElements.push(sibling);
            });
        }

        _clearBlur() {
            this.blurredElements.forEach(el => {
                el.classList.remove('tour-blur-active');
            });
            this.blurredElements = [];

            // Also remove any lingering spotlight classes
            document.querySelectorAll('.tour-spotlight').forEach(el => {
                el.classList.remove('tour-spotlight');
            });
        }

        /* ── Step Rendering ────────────────────────────────── */

        _renderStep(index) {
            const step = TOUR_STEPS[index];

            // Remove previous tooltip
            if (this.tooltip) {
                this.tooltip.classList.remove('tour-tooltip-visible');
                setTimeout(() => {
                    if (this.tooltip) this.tooltip.remove();
                    this._doRenderStep(step, index);
                }, 200);
            } else {
                this._doRenderStep(step, index);
            }
        }

        _doRenderStep(step, index) {
            // Clear previous spotlight
            this._clearBlur();

            let targetEl = null;

            if (step.selector) {
                targetEl = document.querySelector(step.selector);
            }

            // Highlight multiple elements if specified
            if (step.selectorMultiple) {
                step.selectorMultiple.forEach(sel => {
                    const el = document.querySelector(sel);
                    if (el) el.classList.add('tour-spotlight');
                });
            }

            if (targetEl) {
                // Scroll into view
                targetEl.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });

                // Add spotlight class
                targetEl.classList.add('tour-spotlight');

                // Apply blur to everything else
                this._applyBlur(targetEl);
            } else {
                // Center modal (e.g., Section 49A) — blur everything
                this._applyBlur(null);
            }

            // Build tooltip
            this.tooltip = this._createTooltip(step, index);
            document.body.appendChild(this.tooltip);

            // Position tooltip
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    this._positionTooltip(step, targetEl);
                    this.tooltip.classList.add('tour-tooltip-visible');
                });
            });
        }

        _createTooltip(step, index) {
            const total = TOUR_STEPS.length;
            const progress = ((index + 1) / total) * 100;
            const isLast = index === total - 1;

            const tooltip = document.createElement('div');
            tooltip.className = 'tour-tooltip';
            tooltip.innerHTML = `
                <div class="tour-tooltip-header">
                    <div class="tour-tooltip-step">
                        <span class="tour-tooltip-step-dot"></span>
                        Step ${index + 1} of ${total}
                    </div>
                    <span class="tour-tooltip-badge">${step.badge}</span>
                </div>
                <div class="tour-tooltip-body">
                    <h3 class="tour-tooltip-title">${step.title}</h3>
                    <p class="tour-tooltip-desc">${step.description}</p>
                </div>
                <div class="tour-tooltip-actions">
                    <button class="tour-btn-skip" id="tour-action-skip">Skip Tour</button>
                    <div class="tour-dots" id="tour-dots"></div>
                    <button class="tour-btn-next" id="tour-action-next">
                        ${isLast ? 'Finish' : 'Next'}
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                  d="${isLast ? 'M5 13l4 4L19 7' : 'M14 5l7 7m0 0l-7 7m7-7H3'}"/>
                        </svg>
                    </button>
                </div>
                <div class="tour-progress-bar">
                    <div class="tour-progress-fill" style="width: ${progress}%"></div>
                </div>
            `;

            // Progress dots
            const dotsContainer = tooltip.querySelector('#tour-dots');
            for (let i = 0; i < total; i++) {
                const dot = document.createElement('div');
                dot.className = 'tour-dot';
                if (i < index) dot.classList.add('tour-dot-done');
                if (i === index) dot.classList.add('tour-dot-active');
                dotsContainer.appendChild(dot);
            }

            // Button handlers
            tooltip.querySelector('#tour-action-next').addEventListener('click', () => this.next());
            tooltip.querySelector('#tour-action-skip').addEventListener('click', () => this.skip());

            return tooltip;
        }

        /* ── Tooltip Positioning ───────────────────────────── */

        _positionTooltip(step, targetEl) {
            if (!this.tooltip) return;

            const tooltipRect = this.tooltip.getBoundingClientRect();
            const margin = 16;
            const viewW = window.innerWidth;
            const viewH = window.innerHeight;

            if (step.position === 'center' || !targetEl) {
                // Center on screen
                this.tooltip.style.left = Math.max(margin, (viewW - tooltipRect.width) / 2) + 'px';
                this.tooltip.style.top = Math.max(margin, (viewH - tooltipRect.height) / 2) + 'px';
                return;
            }

            const targetRect = targetEl.getBoundingClientRect();
            let left, top;

            switch (step.position) {
                case 'right':
                    left = targetRect.right + margin;
                    top = targetRect.top + (targetRect.height / 2) - (tooltipRect.height / 2);
                    // If overflows right, try left
                    if (left + tooltipRect.width > viewW - margin) {
                        left = targetRect.left - tooltipRect.width - margin;
                    }
                    break;
                case 'left':
                    left = targetRect.left - tooltipRect.width - margin;
                    top = targetRect.top + (targetRect.height / 2) - (tooltipRect.height / 2);
                    if (left < margin) {
                        left = targetRect.right + margin;
                    }
                    break;
                case 'bottom':
                    left = targetRect.left + (targetRect.width / 2) - (tooltipRect.width / 2);
                    top = targetRect.bottom + margin;
                    if (top + tooltipRect.height > viewH - margin) {
                        top = targetRect.top - tooltipRect.height - margin;
                    }
                    break;
                case 'top':
                    left = targetRect.left + (targetRect.width / 2) - (tooltipRect.width / 2);
                    top = targetRect.top - tooltipRect.height - margin;
                    if (top < margin) {
                        top = targetRect.bottom + margin;
                    }
                    break;
                default:
                    left = targetRect.right + margin;
                    top = targetRect.top;
            }

            // Clamp to viewport
            left = Math.max(margin, Math.min(left, viewW - tooltipRect.width - margin));
            top = Math.max(margin, Math.min(top, viewH - tooltipRect.height - margin));

            this.tooltip.style.left = left + 'px';
            this.tooltip.style.top = top + 'px';
        }
    }

    /* ── Auto-start on DOM ready ───────────────────────────── */
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            // Small delay to let dashboard data load first
            setTimeout(() => new DigitalElectoralNavigator().start(), 1200);
        });
    } else {
        setTimeout(() => new DigitalElectoralNavigator().start(), 1200);
    }

})();
