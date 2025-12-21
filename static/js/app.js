class YouTubeAutomation {
    constructor() {
        this.isAuthenticated = false;
        this.currentTaskId = null;
        this.statusCheckInterval = null;
        this.init();
    }

    init() {
        this.cacheElements();
        this.attachEventListeners();
        this.checkAuthentication();
    }

    cacheElements() {
        // Auth elements
        this.authBtn = document.getElementById('authBtn');
        this.authStatus = document.getElementById('authStatus');
        this.logoutBtn = document.getElementById('logoutBtn');
        
        // Channel info
        this.channelInfo = document.getElementById('channelInfo');
        this.channelAvatar = document.getElementById('channelAvatar');
        this.channelName = document.getElementById('channelName');
        this.channelStats = document.getElementById('channelStats');
        
        // Upload section
        this.uploadSection = document.getElementById('uploadSection');
        this.reelUrl = document.getElementById('reelUrl');
        this.uploadBtn = document.getElementById('uploadBtn');
        this.downloadBtn = document.getElementById('downloadBtn');
        this.previewBtn = document.getElementById('previewBtn');
        
        // Progress
        this.progressSection = document.getElementById('progressSection');
        this.progressTitle = document.getElementById('progressTitle');
        this.progressPercent = document.getElementById('progressPercent');
        this.progressFill = document.getElementById('progressFill');
        this.progressMessage = document.getElementById('progressMessage');
        
        // Metadata preview
        this.metadataPreview = document.getElementById('metadataPreview');
        this.previewTitle = document.getElementById('previewTitle');
        this.previewDescription = document.getElementById('previewDescription');
        this.previewTags = document.getElementById('previewTags');
        this.previewHashtags = document.getElementById('previewHashtags');
        
        // Results
        this.successResult = document.getElementById('successResult');
        this.errorResult = document.getElementById('errorResult');
        this.watchBtn = document.getElementById('watchBtn');
        this.errorMessage = document.getElementById('errorMessage');
        this.retryBtn = document.getElementById('retryBtn');
        
        // Overlay
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.toast = document.getElementById('toast');
        
        // Navbar elements
        this.navSignInBtn = document.getElementById('navSignInBtn');
        this.navAuthButtons = document.getElementById('navAuthButtons');
        this.navUserMenu = document.getElementById('navUserMenu');
        this.navUserAvatar = document.getElementById('navUserAvatar');
        this.navUserAvatarImg = document.getElementById('navUserAvatarImg');
        this.navUserName = document.getElementById('navUserName');
        this.navUserStats = document.getElementById('navUserStats');
        this.navLogoutBtn = document.getElementById('navLogoutBtn');
        this.navDashboard = document.getElementById('navDashboard');
        this.navSettings = document.getElementById('navSettings');
        
        // Mobile menu
        this.mobileMenuToggle = document.getElementById('mobileMenuToggle');
        this.mobileMenu = document.getElementById('mobileMenu');
        this.mobileSignInBtn = document.getElementById('mobileSignInBtn');
        
        // Modal elements
        this.signInModal = document.getElementById('signInModal');
        this.closeSignInModal = document.getElementById('closeSignInModal');
        this.modalSignInBtn = document.getElementById('modalSignInBtn');
    }

    attachEventListeners() {
        this.authBtn.addEventListener('click', () => this.handleAuthentication());
        this.logoutBtn.addEventListener('click', () => this.handleLogout());
        this.uploadBtn.addEventListener('click', () => this.handleUpload());
        this.downloadBtn.addEventListener('click', () => this.handleDownload());
        this.previewBtn.addEventListener('click', () => this.handlePreview());
        this.retryBtn.addEventListener('click', () => this.resetForm());
        
        // Enter key for URL input
        this.reelUrl.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.handleUpload();
            }
        });
        
        // Navbar authentication
        if (this.navSignInBtn) {
            this.navSignInBtn.addEventListener('click', () => this.openSignInModal());
        }
        if (this.navLogoutBtn) {
            this.navLogoutBtn.addEventListener('click', () => this.handleLogout());
        }
        if (this.navDashboard) {
            this.navDashboard.addEventListener('click', () => this.scrollToUploadSection());
        }
        
        // Mobile menu
        if (this.mobileMenuToggle) {
            this.mobileMenuToggle.addEventListener('click', () => this.toggleMobileMenu());
        }
        if (this.mobileSignInBtn) {
            this.mobileSignInBtn.addEventListener('click', () => {
                this.closeMobileMenu();
                this.openSignInModal();
            });
        }
        
        // Modal
        if (this.closeSignInModal) {
            this.closeSignInModal.addEventListener('click', () => this.closeSignInModal_());
        }
        if (this.modalSignInBtn) {
            this.modalSignInBtn.addEventListener('click', () => {
                this.closeSignInModal_();
                this.handleAuthentication();
            });
        }
        if (this.signInModal) {
            this.signInModal.addEventListener('click', (e) => {
                if (e.target === this.signInModal) {
                    this.closeSignInModal_();
                }
            });
        }
        
        // Close mobile menu when clicking outside
        document.addEventListener('click', (e) => {
            if (this.mobileMenu && 
                this.mobileMenu.classList.contains('active') &&
                !this.mobileMenu.contains(e.target) &&
                !this.mobileMenuToggle.contains(e.target)) {
                this.closeMobileMenu();
            }
        });
    }

    async checkAuthentication() {
        try {
            const response = await fetch('/check-auth');
            const data = await response.json();
            
            if (data.authenticated) {
                this.isAuthenticated = true;
                await this.loadChannelInfo();
                this.showUploadSection();
                this.updateNavbarAuth(true);
            } else {
                this.showAuthButton();
                this.updateNavbarAuth(false);
            }
        } catch (error) {
            console.error('Auth check failed:', error);
            this.showAuthButton();
            this.updateNavbarAuth(false);
        }
    }

    updateNavbarAuth(isAuthenticated) {
        if (isAuthenticated) {
            this.navAuthButtons.style.display = 'none';
            this.navUserMenu.style.display = 'block';
        } else {
            this.navAuthButtons.style.display = 'flex';
            this.navUserMenu.style.display = 'none';
        }
    }

    async loadChannelInfo() {
        try {
            const response = await fetch('/get-channel-info');
            const data = await response.json();
            
            if (data.authenticated && data.channel) {
                const channel = data.channel;
                
                // Update main channel info
                this.channelAvatar.src = channel.thumbnail || 'https://via.placeholder.com/80';
                this.channelName.textContent = channel.title;
                this.channelStats.textContent = `${this.formatNumber(channel.subscriberCount)} subscribers • ${this.formatNumber(channel.videoCount)} videos`;
                this.channelInfo.style.display = 'block';
                
                // Update navbar user info
                this.navUserAvatarImg.src = channel.thumbnail || 'https://via.placeholder.com/40';
                this.navUserName.textContent = channel.title;
                this.navUserStats.textContent = `${this.formatNumber(channel.subscriberCount)} subscribers`;
            }
        } catch (error) {
            console.error('Failed to load channel info:', error);
        }
    }

    openSignInModal() {
        this.signInModal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    closeSignInModal_() {
        this.signInModal.classList.remove('active');
        document.body.style.overflow = 'auto';
    }

    toggleMobileMenu() {
        this.mobileMenu.classList.toggle('active');
    }

    closeMobileMenu() {
        this.mobileMenu.classList.remove('active');
    }

    scrollToUploadSection() {
        if (this.uploadSection && this.uploadSection.style.display !== 'none') {
            this.uploadSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    async handleAuthentication() {
        this.showLoading();
        
        try {
            // First try to start OAuth flow for server environments
            const response = await fetch('/auth/start');
            const data = await response.json();
            
            if (data.auth_url) {
                // Open auth URL in new window
                const authWindow = window.open(data.auth_url, 'YouTube Authentication', 'width=600,height=700');
                
                // Poll for authentication completion
                const checkAuth = setInterval(async () => {
                    if (authWindow.closed) {
                        clearInterval(checkAuth);
                        this.hideLoading();
                        await this.checkAuthentication();
                    }
                }, 1000);
            } else {
                // Fallback to local authentication
                const authResponse = await fetch('/authenticate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                const authData = await authResponse.json();
                
                if (authData.success) {
                    this.showToast('Authentication successful!', 'success');
                    await this.checkAuthentication();
                } else {
                    throw new Error(authData.error || 'Authentication failed');
                }
            }
        } catch (error) {
            console.error('Authentication error:', error);
            this.showToast('Authentication failed: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async handleLogout() {
        if (!confirm('Are you sure you want to logout?')) return;
        
        this.showLoading();
        
        try {
            const response = await fetch('/logout', { method: 'POST' });
            const data = await response.json();
            
            if (data.success) {
                this.showToast('Logged out successfully', 'success');
                this.isAuthenticated = false;
                this.channelInfo.style.display = 'none';
                this.uploadSection.style.display = 'none';
                this.showAuthButton();
                this.updateNavbarAuth(false);
            }
        } catch (error) {
            this.showToast('Logout failed: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async handlePreview() {
        const url = this.reelUrl.value.trim();
        
        if (!url) {
            this.showToast('Please enter a valid Instagram Reel URL', 'error');
            return;
        }
        
        this.showLoading();
        this.hideResults();
        
        try {
            const response = await fetch('/generate-preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.displayMetadataPreview(data);
                this.showToast('AI metadata generated successfully!', 'success');
            } else {
                throw new Error(data.error || 'Preview generation failed');
            }
        } catch (error) {
            this.showToast('Preview failed: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async handleUpload() {
        if (!this.isAuthenticated) {
            this.showToast('Please sign in with YouTube first', 'error');
            return;
        }
        
        const url = this.reelUrl.value.trim();
        
        if (!url) {
            this.showToast('Please enter a valid Instagram Reel URL', 'error');
            return;
        }
        
        this.hideResults();
        this.showProgress();
        
        try {
            const response = await fetch('/auto-upload-async', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentTaskId = data.task_id;
                this.startStatusPolling();
            } else {
                throw new Error(data.error || 'Upload failed');
            }
        } catch (error) {
            this.showError(error.message);
        }
    }

    async handleDownload() {
        const url = this.reelUrl.value.trim();
        
        if (!url) {
            this.showToast('Please enter a valid Instagram Reel URL', 'error');
            return;
        }
        
        this.showLoading();
        
        try {
            const response = await fetch('/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showToast('Download completed! Check your downloads folder.', 'success');
                
                // Trigger file download
                window.location.href = `/get-video/${data.filename}`;
            } else {
                throw new Error(data.error || 'Download failed');
            }
        } catch (error) {
            this.showToast('Download failed: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    startStatusPolling() {
        this.statusCheckInterval = setInterval(async () => {
            await this.checkTaskStatus();
        }, 2000);
    }

    async checkTaskStatus() {
        if (!this.currentTaskId) return;
        
        try {
            const response = await fetch(`/task-status/${this.currentTaskId}`);
            const data = await response.json();
            
            if (data.success) {
                const task = data.task;
                this.updateProgress(task);
                
                if (task.status === 'completed') {
                    this.stopStatusPolling();
                    this.showSuccess(task);
                } else if (task.status === 'failed') {
                    this.stopStatusPolling();
                    this.showError(task.error || 'Upload failed');
                }
            }
        } catch (error) {
            console.error('Status check failed:', error);
        }
    }

    stopStatusPolling() {
        if (this.statusCheckInterval) {
            clearInterval(this.statusCheckInterval);
            this.statusCheckInterval = null;
        }
    }

    updateProgress(task) {
        this.progressTitle.textContent = this.getStatusTitle(task.status);
        this.progressPercent.textContent = `${task.progress}%`;
        this.progressFill.style.width = `${task.progress}%`;
        this.progressMessage.textContent = task.message;
        
        // Show metadata if available
        if (task.metadata && task.status === 'uploading') {
            this.displayMetadataPreview(task.metadata);
        }
    }

    getStatusTitle(status) {
        const titles = {
            'started': 'Starting...',
            'downloading': 'Downloading Reel',
            'generating_metadata': 'AI Analyzing Video',
            'uploading': 'Uploading to YouTube',
            'completed': 'Upload Complete',
            'failed': 'Upload Failed'
        };
        return titles[status] || 'Processing...';
    }

    displayMetadataPreview(metadata) {
        this.previewTitle.textContent = metadata.title || '-';
        this.previewDescription.textContent = metadata.description || '-';
        
        // Display tags
        this.previewTags.innerHTML = '';
        if (metadata.tags && metadata.tags.length > 0) {
            metadata.tags.slice(0, 15).forEach(tag => {
                const span = document.createElement('span');
                span.textContent = tag;
                this.previewTags.appendChild(span);
            });
        }
        
        // Display hashtags
        this.previewHashtags.innerHTML = '';
        if (metadata.hashtags && metadata.hashtags.length > 0) {
            metadata.hashtags.slice(0, 20).forEach(hashtag => {
                const span = document.createElement('span');
                span.textContent = hashtag;
                this.previewHashtags.appendChild(span);
            });
        }
        
        this.metadataPreview.style.display = 'block';
    }

    showProgress() {
        this.progressSection.style.display = 'block';
        this.metadataPreview.style.display = 'none';
        this.successResult.style.display = 'none';
        this.errorResult.style.display = 'none';
    }

    showSuccess(task) {
        this.progressSection.style.display = 'none';
        this.successResult.style.display = 'block';
        
        if (task.youtube_url) {
            this.watchBtn.href = task.youtube_url;
        }
        
        this.showToast('Video uploaded successfully! 🎉', 'success');
    }

    showError(message) {
        this.progressSection.style.display = 'none';
        this.errorResult.style.display = 'block';
        this.errorMessage.textContent = message;
        this.showToast('Upload failed: ' + message, 'error');
    }

    hideResults() {
        this.successResult.style.display = 'none';
        this.errorResult.style.display = 'none';
        this.metadataPreview.style.display = 'none';
    }

    resetForm() {
        this.reelUrl.value = '';
        this.hideResults();
        this.progressSection.style.display = 'none';
        this.currentTaskId = null;
        this.stopStatusPolling();
    }

    showUploadSection() {
        if (this.authBtn) this.authBtn.style.display = 'none';
        this.uploadSection.style.display = 'block';
    }

    showAuthButton() {
        if (this.authBtn) this.authBtn.style.display = 'inline-flex';
        this.uploadSection.style.display = 'none';
    }

    showLoading() {
        this.loadingOverlay.style.display = 'flex';
    }

    hideLoading() {
        this.loadingOverlay.style.display = 'none';
    }

    showToast(message, type = 'info') {
        this.toast.textContent = message;
        this.toast.className = 'toast show';
        
        if (type === 'success') {
            this.toast.style.borderLeft = '4px solid var(--success)';
        } else if (type === 'error') {
            this.toast.style.borderLeft = '4px solid var(--error)';
        } else {
            this.toast.style.borderLeft = '4px solid var(--secondary)';
        }
        
        setTimeout(() => {
            this.toast.classList.remove('show');
        }, 4000);
    }

    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num;
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new YouTubeAutomation();
});
