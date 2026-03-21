/* ═══════════════════════════════════════════════════════════════════════════
   YouTube Automation Platform — Client-Side Application
   ═══════════════════════════════════════════════════════════════════════════ */

(function() {
    'use strict';

    // ─── Toast System ────────────────────────────────────────────────────────
    const ToastManager = {
        container: null,
        init() {
            this.container = document.getElementById('toast-container');
            if (!this.container) {
                this.container = document.createElement('div');
                this.container.id = 'toast-container';
                this.container.className = 'toast-container';
                document.body.appendChild(this.container);
            }
        },
        show(message, type = 'info', duration = 4000) {
            if (!this.container) this.init();
            const icons = { success: '✓', error: '✕', info: 'ℹ' };
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${message}</span>`;
            this.container.appendChild(toast);
            setTimeout(() => {
                toast.classList.add('removing');
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }
    };
    window.toast = ToastManager;

    // ─── API Helper ──────────────────────────────────────────────────────────
    async function api(url, options = {}) {
        const defaults = {
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        };
        const config = { ...defaults, ...options };
        if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
            config.body = JSON.stringify(options.body);
        }
        if (options.body instanceof FormData) {
            delete config.headers['Content-Type'];
        }
        try {
            const resp = await fetch(url, config);
            if (resp.status === 401) {
                window.location.href = '/login';
                return null;
            }
            return await resp.json();
        } catch (e) {
            console.error('API Error:', e);
            ToastManager.show('Network error. Please try again.', 'error');
            return null;
        }
    }
    window.api = api;

    // ─── Landing Page ────────────────────────────────────────────────────────
    function initLanding() {
        // Navbar scroll effect
        const nav = document.querySelector('.landing-nav');
        if (nav) {
            window.addEventListener('scroll', () => {
                nav.classList.toggle('scrolled', window.scrollY > 40);
            });
        }

        // Mobile menu
        const menuBtn = document.querySelector('.mobile-menu-btn');
        const navLinks = document.querySelector('.nav-links');
        if (menuBtn && navLinks) {
            menuBtn.addEventListener('click', () => navLinks.classList.toggle('open'));
        }

        // Particles
        const particlesContainer = document.querySelector('.hero-particles');
        if (particlesContainer) {
            for (let i = 0; i < 30; i++) {
                const p = document.createElement('div');
                p.className = 'particle';
                p.style.left = Math.random() * 100 + '%';
                p.style.animationDuration = (8 + Math.random() * 12) + 's';
                p.style.animationDelay = (Math.random() * 8) + 's';
                p.style.width = p.style.height = (2 + Math.random() * 4) + 'px';
                const colors = ['#8b5cf6', '#06b6d4', '#ec4899', '#10b981'];
                p.style.background = colors[Math.floor(Math.random() * colors.length)];
                particlesContainer.appendChild(p);
            }
        }

        // Smooth scroll for anchor links
        document.querySelectorAll('a[href^="#"]').forEach(a => {
            a.addEventListener('click', (e) => {
                const target = document.querySelector(a.getAttribute('href'));
                if (target) {
                    e.preventDefault();
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    if (navLinks) navLinks.classList.remove('open');
                }
            });
        });

        // Animate on scroll
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animate-in');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });
        document.querySelectorAll('.feature-card, .step-card, .pricing-card').forEach(el => {
            observer.observe(el);
        });
    }

    // ─── Sidebar ─────────────────────────────────────────────────────────────
    function initSidebar() {
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.querySelector('.sidebar-overlay');
        const toggleBtn = document.querySelector('.mobile-sidebar-btn');

        if (!sidebar) return;

        function openSidebar() {
            sidebar.classList.add('open');
            if (overlay) overlay.classList.add('active');
        }
        function closeSidebar() {
            sidebar.classList.remove('open');
            if (overlay) overlay.classList.remove('active');
        }

        if (toggleBtn) toggleBtn.addEventListener('click', openSidebar);
        if (overlay) overlay.addEventListener('click', closeSidebar);
    }

    // ─── Token Widget ────────────────────────────────────────────────────────
    async function updateTokenWidget() {
        const widget = document.querySelector('.token-count');
        if (!widget) return;
        const data = await api('/api/token-balance');
        if (data && data.tokens_balance !== undefined) {
            widget.textContent = data.tokens_balance;
            const w = widget.closest('.token-widget');
            if (w) {
                w.classList.toggle('token-low', data.tokens_balance < 10);
            }
        }
    }

    // ─── Dashboard ───────────────────────────────────────────────────────────
    function initDashboard() {
        // Usage chart
        const canvas = document.getElementById('usage-chart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const chartData = canvas.dataset.usage;
        if (!chartData) return;

        let usage;
        try { usage = JSON.parse(chartData); } catch { return; }

        const labels = usage.map(d => d.day ? d.day.slice(5) : '');
        const values = usage.map(d => d.tokens || 0);
        const maxVal = Math.max(...values, 10);

        function drawChart() {
            const w = canvas.width = canvas.parentElement.offsetWidth;
            const h = canvas.height = canvas.parentElement.offsetHeight;
            const pad = { top: 20, right: 20, bottom: 30, left: 40 };
            const cw = w - pad.left - pad.right;
            const ch = h - pad.top - pad.bottom;

            ctx.clearRect(0, 0, w, h);

            // Grid lines
            ctx.strokeStyle = 'rgba(255,255,255,0.05)';
            ctx.lineWidth = 1;
            for (let i = 0; i <= 4; i++) {
                const y = pad.top + (ch / 4) * i;
                ctx.beginPath();
                ctx.moveTo(pad.left, y);
                ctx.lineTo(w - pad.right, y);
                ctx.stroke();
            }

            // Labels
            ctx.fillStyle = 'rgba(240,240,245,0.3)';
            ctx.font = '11px Inter, sans-serif';
            ctx.textAlign = 'center';
            labels.forEach((l, i) => {
                const x = pad.left + (cw / Math.max(labels.length - 1, 1)) * i;
                ctx.fillText(l, x, h - 8);
            });

            if (values.length < 2) return;

            // Gradient fill
            const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + ch);
            grad.addColorStop(0, 'rgba(139, 92, 246, 0.3)');
            grad.addColorStop(1, 'rgba(139, 92, 246, 0)');

            ctx.beginPath();
            values.forEach((v, i) => {
                const x = pad.left + (cw / (values.length - 1)) * i;
                const y = pad.top + ch - (v / maxVal) * ch;
                i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
            });
            ctx.lineTo(pad.left + cw, pad.top + ch);
            ctx.lineTo(pad.left, pad.top + ch);
            ctx.closePath();
            ctx.fillStyle = grad;
            ctx.fill();

            // Line
            ctx.beginPath();
            values.forEach((v, i) => {
                const x = pad.left + (cw / (values.length - 1)) * i;
                const y = pad.top + ch - (v / maxVal) * ch;
                i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
            });
            ctx.strokeStyle = '#8b5cf6';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Dots
            values.forEach((v, i) => {
                const x = pad.left + (cw / (values.length - 1)) * i;
                const y = pad.top + ch - (v / maxVal) * ch;
                ctx.beginPath();
                ctx.arc(x, y, 4, 0, Math.PI * 2);
                ctx.fillStyle = '#8b5cf6';
                ctx.fill();
                ctx.strokeStyle = '#06060f';
                ctx.lineWidth = 2;
                ctx.stroke();
            });
        }
        drawChart();
        window.addEventListener('resize', drawChart);
    }

    // ─── Upload Page ─────────────────────────────────────────────────────────
    function initUpload() {
        const sourceOptions = document.querySelectorAll('.source-option');
        const igSection = document.getElementById('ig-section');
        const deviceSection = document.getElementById('device-section');
        const dropzone = document.getElementById('dropzone');
        const fileInput = document.getElementById('video-file');
        const startBtn = document.getElementById('start-upload-btn');
        const progressArea = document.getElementById('progress-area');
        const resultArea = document.getElementById('result-area');
        const editingToggle = document.getElementById('editing-enabled');
        const editingPanel = document.getElementById('editing-options');
        const costValue = document.querySelector('.cost-value');

        let currentSource = 'instagram';
        let uploadedFilePath = '';

        // Source picker
        sourceOptions.forEach(opt => {
            opt.addEventListener('click', () => {
                sourceOptions.forEach(o => o.classList.remove('active'));
                opt.classList.add('active');
                currentSource = opt.dataset.source;
                if (igSection) igSection.classList.toggle('hidden', currentSource !== 'instagram');
                if (deviceSection) deviceSection.classList.toggle('hidden', currentSource !== 'device');
                updateCost();
            });
        });

        // Editing toggle
        if (editingToggle && editingPanel) {
            editingToggle.addEventListener('change', () => {
                editingPanel.classList.toggle('hidden', !editingToggle.checked);
                updateCost();
            });
        }

        // Cost preview
        function updateCost() {
            if (!costValue) return;
            let cost = 8; // upload(5) + ai(3)
            if (editingToggle && editingToggle.checked) cost += 4;
            costValue.textContent = cost + ' tokens';
        }
        updateCost();

        // Dropzone
        if (dropzone && fileInput) {
            dropzone.addEventListener('click', () => fileInput.click());
            dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
            dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
            dropzone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropzone.classList.remove('dragover');
                if (e.dataTransfer.files.length) {
                    fileInput.files = e.dataTransfer.files;
                    handleFile(e.dataTransfer.files[0]);
                }
            });
            fileInput.addEventListener('change', () => {
                if (fileInput.files.length) handleFile(fileInput.files[0]);
            });
        }

        async function handleFile(file) {
            const formData = new FormData();
            formData.append('video', file);
            dropzone.innerHTML = '<div class="drop-icon"><div class="spinner"></div></div><h4>Uploading...</h4>';

            try {
                const resp = await fetch('/upload-video', { method: 'POST', body: formData });
                const data = await resp.json();
                if (data.success) {
                    uploadedFilePath = data.filepath;
                    dropzone.innerHTML = `<div class="drop-icon">✅</div><h4>${file.name}</h4><p>File ready. Click Start to process.</p>`;
                    toast.show('Video uploaded successfully!', 'success');
                } else {
                    dropzone.innerHTML = '<div class="drop-icon">📁</div><h4>Drop video here or click to browse</h4><p>MP4, MOV, AVI, MKV supported</p>';
                    toast.show(data.error || 'Upload failed', 'error');
                }
            } catch (e) {
                dropzone.innerHTML = '<div class="drop-icon">📁</div><h4>Drop video here or click to browse</h4><p>MP4, MOV, AVI, MKV supported</p>';
                toast.show('Upload failed', 'error');
            }
        }

        // Start upload
        if (startBtn) {
            startBtn.addEventListener('click', async () => {
                const payload = { source: currentSource };

                if (currentSource === 'instagram') {
                    const urlInput = document.getElementById('ig-url');
                    if (!urlInput || !urlInput.value.trim()) {
                        toast.show('Please enter an Instagram URL', 'error');
                        return;
                    }
                    payload.url = urlInput.value.trim();
                } else {
                    if (!uploadedFilePath) {
                        toast.show('Please upload a video first', 'error');
                        return;
                    }
                    payload.video_path = uploadedFilePath;
                }

                // Editing options
                if (editingToggle && editingToggle.checked) {
                    const musicUrl = document.getElementById('music-url');
                    const musicVol = document.getElementById('music-volume');
                    payload.editing = {
                        enabled: true,
                        music_url: musicUrl ? musicUrl.value : '',
                        music_volume: musicVol ? parseFloat(musicVol.value) : 0.3,
                    };
                }

                startBtn.disabled = true;
                startBtn.innerHTML = '<span class="spinner"></span> Processing...';

                const data = await api('/start-upload', { method: 'POST', body: payload });

                if (!data || !data.success) {
                    startBtn.disabled = false;
                    startBtn.innerHTML = '🚀 Start Processing';
                    toast.show(data?.error || 'Failed to start', 'error');
                    return;
                }

                if (progressArea) progressArea.classList.remove('hidden');
                pollTask(data.task_id);
            });
        }

        function pollTask(taskId) {
            const progressFill = document.querySelector('.progress-bar-fill');
            const progressMsg = document.querySelector('.progress-message');
            const progressPct = document.querySelector('.progress-percent');

            const interval = setInterval(async () => {
                const data = await api(`/task/${taskId}`);
                if (!data) return;

                if (progressFill) progressFill.style.width = data.progress + '%';
                if (progressMsg) progressMsg.textContent = data.message;
                if (progressPct) progressPct.textContent = data.progress + '%';

                if (data.status === 'done') {
                    clearInterval(interval);
                    if (resultArea) {
                        resultArea.classList.remove('hidden');
                        const link = resultArea.querySelector('.yt-link');
                        if (link && data.yt_url) {
                            link.href = data.yt_url;
                            link.textContent = data.yt_url;
                        }
                    }
                    toast.show('Upload complete! 🎉', 'success');
                    startBtn.disabled = false;
                    startBtn.innerHTML = '🚀 Start Processing';
                    updateTokenWidget();
                } else if (data.status === 'failed') {
                    clearInterval(interval);
                    toast.show('Upload failed: ' + (data.error || 'Unknown error'), 'error');
                    startBtn.disabled = false;
                    startBtn.innerHTML = '🚀 Start Processing';
                }
            }, 2000);
        }
    }

    // ─── YouTube OAuth ───────────────────────────────────────────────────────
    window.connectYouTube = async function() {
        const data = await api('/auth/youtube/start');
        if (data && data.auth_url) {
            window.open(data.auth_url, '_blank', 'width=600,height=700');
        } else {
            toast.show(data?.error || 'Failed to start YouTube auth', 'error');
        }
    };

    window.disconnectYouTube = async function() {
        const data = await api('/youtube/logout', { method: 'POST' });
        if (data && data.success) {
            toast.show('YouTube disconnected', 'info');
            setTimeout(() => location.reload(), 1000);
        }
    };

    // ─── Pricing / Checkout ──────────────────────────────────────────────────
    window.purchasePlan = async function(planId) {
        const data = await api('/api/create-checkout', {
            method: 'POST',
            body: { type: 'plan', id: planId }
        });
        if (!data) return;
        if (data.mock) {
            toast.show(data.message, 'success');
            setTimeout(() => location.reload(), 1500);
        } else if (data.checkout_url) {
            window.location.href = data.checkout_url;
        } else {
            toast.show(data.error || 'Checkout failed', 'error');
        }
    };

    window.purchasePack = async function(packId) {
        const data = await api('/api/create-checkout', {
            method: 'POST',
            body: { type: 'pack', id: packId }
        });
        if (!data) return;
        if (data.mock) {
            toast.show(data.message, 'success');
            setTimeout(() => location.reload(), 1500);
        } else if (data.checkout_url) {
            window.location.href = data.checkout_url;
        } else {
            toast.show(data.error || 'Checkout failed', 'error');
        }
    };

    // ─── Settings ────────────────────────────────────────────────────────────
    function initSettings() {
        const profileForm = document.getElementById('profile-form');
        if (profileForm) {
            profileForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const username = document.getElementById('settings-username')?.value;
                const data = await api('/api/profile', {
                    method: 'POST', body: { username }
                });
                if (data?.success) toast.show('Profile updated!', 'success');
                else toast.show(data?.error || 'Update failed', 'error');
            });
        }

        const pwForm = document.getElementById('password-form');
        if (pwForm) {
            pwForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const data = await api('/api/change-password', {
                    method: 'POST',
                    body: {
                        current_password: document.getElementById('current-pw')?.value,
                        new_password: document.getElementById('new-pw')?.value,
                        confirm_password: document.getElementById('confirm-pw')?.value,
                    }
                });
                if (data?.success) {
                    toast.show('Password changed!', 'success');
                    pwForm.reset();
                } else {
                    toast.show(data?.error || 'Failed', 'error');
                }
            });
        }
    }

    // ─── Auth Forms ──────────────────────────────────────────────────────────
    function initAuthForms() {
        const form = document.querySelector('.auth-form');
        if (!form) return;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = form.querySelector('button[type="submit"]');
            const originalText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Please wait...';

            const formData = new FormData(form);
            const body = Object.fromEntries(formData);

            const data = await api(form.action, { method: 'POST', body });

            if (data?.success) {
                window.location.href = data.redirect || '/dashboard';
            } else {
                btn.disabled = false;
                btn.innerHTML = originalText;
                const errors = data?.errors || [data?.error || 'Something went wrong'];
                errors.forEach(err => toast.show(err, 'error'));
            }
        });
    }

    // ─── Init ────────────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        ToastManager.init();

        const page = document.body.dataset.page;
        if (page === 'landing') initLanding();
        if (page === 'dashboard') { initSidebar(); initDashboard(); updateTokenWidget(); }
        if (page === 'upload') { initSidebar(); initUpload(); updateTokenWidget(); }
        if (page === 'settings') { initSidebar(); initSettings(); updateTokenWidget(); }
        if (page === 'pricing' && document.querySelector('.sidebar')) { initSidebar(); updateTokenWidget(); }
        if (page === 'login' || page === 'register') initAuthForms();

        // Check for success/cancel in URL (Stripe redirect)
        const params = new URLSearchParams(window.location.search);
        if (params.get('success') === '1') {
            toast.show('Payment successful! Tokens have been added.', 'success');
            history.replaceState({}, '', window.location.pathname);
        }
        if (params.get('cancelled') === '1') {
            toast.show('Payment cancelled.', 'info');
            history.replaceState({}, '', window.location.pathname);
        }
    });

})();
