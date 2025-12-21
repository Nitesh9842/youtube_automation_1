class YouTubeUploader {
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
        this.authSection = document.getElementById('authSection');
        this.authBtn = document.getElementById('authBtn');
        this.channelInfo = document.getElementById('channelInfo');
        this.channelAvatar = document.getElementById('channelAvatar');
        this.channelName = document.getElementById('channelName');
        this.channelStats = document.getElementById('channelStats');
        this.uploadSection = document.getElementById('uploadSection');
        this.reelUrl = document.getElementById('reelUrl');
        this.uploadBtn = document.getElementById('uploadBtn');
        this.progressSection = document.getElementById('progressSection');
        this.progressTitle = document.getElementById('progressTitle');
        this.progressPercent = document.getElementById('progressPercent');
        this.progressFill = document.getElementById('progressFill');
        this.progressMessage = document.getElementById('progressMessage');
        this.metadataPreview = document.getElementById('metadataPreview');
        this.previewTitle = document.getElementById('previewTitle');
        this.previewDescription = document.getElementById('previewDescription');
        this.previewTags = document.getElementById('previewTags');
        this.previewHashtags = document.getElementById('previewHashtags');
        this.successResult = document.getElementById('successResult');
        this.errorResult = document.getElementById('errorResult');
        this.watchBtn = document.getElementById('watchBtn');
        this.errorMessage = document.getElementById('errorMessage');
        this.retryBtn = document.getElementById('retryBtn');
        this.uploadAnotherBtn = document.getElementById('uploadAnotherBtn');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.toast = document.getElementById('toast');
        
        // Navbar elements
        this.navAuthButtons = document.getElementById('navAuthButtons');
        this.navSignInBtn = document.getElementById('navSignInBtn');
        this.navUserMenu = document.getElementById('navUserMenu');
        this.navUserAvatarImg = document.getElementById('navUserAvatarImg');
        this.navUserName = document.getElementById('navUserName');
        this.navUserStats = document.getElementById('navUserStats');
        this.navLogoutBtn = document.getElementById('navLogoutBtn');
        
        // Mobile menu elements
        this.mobileSignInBtn = document.getElementById('mobileSignInBtn');
        this.mobileUserInfo = document.getElementById('mobileUserInfo');
        this.mobileUserName = document.getElementById('mobileUserName');
        this.mobileUserStats = document.getElementById('mobileUserStats');
        this.mobileLogoutBtn = document.getElementById('mobileLogoutBtn');
        
        // Main logout button (in channel info section)
        this.logoutBtnMain = document.getElementById('logoutBtnMain');
        
        // Music upload elements
        this.musicUrl = document.getElementById('musicUrl');
        this.musicVolume = document.getElementById('musicVolume');
        this.enableEditingToggle = document.getElementById('enableEditingToggle');
        
        // Music Source Tab elements
        this.musicTabUrl = document.getElementById('musicTabUrl');
        this.musicTabFile = document.getElementById('musicTabFile');
        this.musicUrlSection = document.getElementById('musicUrlSection');
        this.musicFileSection = document.getElementById('musicFileSection');
        this.musicFileInput = document.getElementById('musicFileInput');
        this.musicFileName = document.getElementById('musicFileName');
    }

    attachEventListeners() {
        this.authBtn.addEventListener('click', () => this.handleAuthentication());
        this.uploadBtn.addEventListener('click', () => this.handleUpload());
        this.retryBtn.addEventListener('click', () => this.resetForm());
        this.uploadAnotherBtn.addEventListener('click', () => this.resetForm());
        this.navLogoutBtn.addEventListener('click', () => this.handleLogout());
        
        // Main logout button handler
        if (this.logoutBtnMain) {
            this.logoutBtnMain.addEventListener('click', () => this.handleLogout());
        }
        
        this.reelUrl.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.handleUpload();
        });
        
        // Navbar sign in button
        if (this.navSignInBtn) {
            this.navSignInBtn.addEventListener('click', () => this.handleAuthentication());
        }
        
        // Mobile sign in and logout
        if (this.mobileSignInBtn) {
            this.mobileSignInBtn.addEventListener('click', () => {
                document.getElementById('mobileMenu').classList.remove('active');
                this.handleAuthentication();
            });
        }
        if (this.mobileLogoutBtn) {
            this.mobileLogoutBtn.addEventListener('click', () => {
                document.getElementById('mobileMenu').classList.remove('active');
                this.handleLogout();
            });
        }
        
        // Music Source Tab Switching
        if (this.musicTabUrl && this.musicTabFile) {
            this.musicTabUrl.addEventListener('click', () => {
                this.currentMusicSource = 'url';
                this.musicTabUrl.style.opacity = '1';
                this.musicTabFile.style.opacity = '0.6';
                this.musicUrlSection.style.display = 'block';
                this.musicFileSection.style.display = 'none';
                this.uploadedMusicFile = null;
            });

            this.musicTabFile.addEventListener('click', () => {
                this.currentMusicSource = 'file';
                this.musicTabFile.style.opacity = '1';
                this.musicTabUrl.style.opacity = '0.6';
                this.musicFileSection.style.display = 'block';
                this.musicUrlSection.style.display = 'none';
                document.getElementById('musicUrl').value = '';
            });
        }

        // Handle music file selection
        if (this.musicFileInput) {
            this.musicFileInput.addEventListener('change', async (e) => {
                const file = e.target.files[0];
                if (!file) return;

                // Validate file type
                const validTypes = ['audio/mpeg', 'audio/wav', 'audio/mp4', 'audio/x-m4a', 'audio/aac'];
                if (!validTypes.includes(file.type) && !file.name.match(/\.(mp3|wav|m4a|aac)$/i)) {
                    this.showToast('Please select a valid audio file (MP3, WAV, M4A, AAC)', 'error');
                    return;
                }

                // Check file size (max 50MB)
                if (file.size > 50 * 1024 * 1024) {
                    this.showToast('File size too large. Maximum 50MB allowed.', 'error');
                    return;
                }

                // Update UI
                this.musicFileName.value = file.name;
                this.showToast('Audio file selected. It will be uploaded when you start the upload process.', 'success');
                
                // Store file for later upload
                this.uploadedMusicFile = file;
            });
        }
    }

    async checkAuthentication() {
        try {
            const response = await fetch('/check-auth');
            const data = await response.json();
            
            if (data.authenticated) {
                this.isAuthenticated = true;
                if (data.channel) {
                    this.displayChannelInfo(data.channel);
                }
                this.showUploadSection();
            } else {
                this.isAuthenticated = false;
                this.showAuthSection();
            }
        } catch (error) {
            console.error('Auth check failed:', error);
            this.isAuthenticated = false;
            this.showAuthSection();
        }
    }

    displayChannelInfo(channel) {
        this.channelAvatar.src = channel.thumbnail || 'https://via.placeholder.com/80';
        this.channelName.textContent = channel.title;
        this.channelStats.textContent = `${this.formatNumber(channel.subscriberCount)} subscribers • ${this.formatNumber(channel.videoCount)} videos`;
        this.channelInfo.style.display = 'block';
        
        // ✅ FIXED: Ensure main logout button is visible
        if (this.logoutBtnMain) {
            this.logoutBtnMain.style.display = 'inline-flex';
        }
        
        // Update navbar user menu
        this.navUserAvatarImg.src = channel.thumbnail || 'https://via.placeholder.com/40';
        this.navUserName.textContent = channel.title;
        this.navUserStats.textContent = `${this.formatNumber(channel.subscriberCount)} subscribers`;
        this.navUserMenu.style.display = 'block';
        this.navAuthButtons.style.display = 'none';
        
        // ✅ FIXED: Ensure navbar logout button is visible
        if (this.navLogoutBtn) {
            this.navLogoutBtn.style.display = 'flex';
        }
        
        // Update mobile menu
        this.mobileUserName.textContent = channel.title;
        this.mobileUserStats.textContent = `${this.formatNumber(channel.subscriberCount)} subscribers`;
        this.mobileUserInfo.style.display = 'block';
        this.mobileLogoutBtn.style.display = 'flex'; // ✅ CHANGED: from 'block' to 'flex'
        this.mobileSignInBtn.style.display = 'none';
    }

    async handleAuthentication() {
        this.showLoading();
        
        try {
            const response = await fetch('/auth/start');
            const data = await response.json();
            
            if (data.auth_url) {
                const authWindow = window.open(data.auth_url, 'YouTube Authentication', 'width=600,height=700');
                
                const checkAuth = setInterval(async () => {
                    if (authWindow.closed) {
                        clearInterval(checkAuth);
                        this.hideLoading();
                        await this.checkAuthentication();
                    }
                }, 1000);
            }
        } catch (error) {
            this.showToast('Authentication failed: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async handleLogout() {
        if (!confirm('Are you sure you want to logout? This will end your session permanently.')) return;
        
        this.showLoading();
        
        try {
            const response = await fetch('/logout', { method: 'POST' });
            const data = await response.json();
            
            if (data.success) {
                this.showToast('Logged out successfully. Reloading...', 'success');
                this.isAuthenticated = false;
                
                // Clear local state
                this.currentTaskId = null;
                this.stopStatusPolling();
                
                // Reload page after short delay
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                throw new Error(data.error || 'Logout failed');
            }
        } catch (error) {
            this.showToast('Logout failed: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async handleUpload() {
        if (!this.isAuthenticated) {
            this.showToast('Please sign in with YouTube first', 'error');
            return;
        }
        
        // Check video source
        const currentVideoSource = window.currentVideoSource || 'instagram';
        
        let uploadEndpoint = '/auto-upload-async';
        let uploadData = {};
        
        if (currentVideoSource === 'instagram') {
            const url = this.reelUrl.value.trim();
            
            if (!url) {
                this.showToast('Please enter a valid Instagram Reel URL', 'error');
                return;
            }
            
            uploadData.url = url;
            
        } else if (currentVideoSource === 'local') {
            const videoPath = window.uploadedVideoPath;
            
            if (!videoPath) {
                this.showToast('Please select a video file first', 'error');
                return;
            }
            
            uploadEndpoint = '/upload-local-async';
            uploadData.video_filepath = videoPath;
        }
        
        // Get video editing preferences
        const enableEditing = document.getElementById('enableEditingToggle').checked;
        let editingOptions = null;
        
        if (enableEditing) {
            let musicSource = null;
            
            // Handle local music file upload
            const currentMusicSource = this.musicTabUrl.style.opacity === '1' ? 'url' : 'file';
            
            if (currentMusicSource === 'file' && this.uploadedMusicFile) {
                this.showLoading();
                try {
                    // Upload music file to server
                    const formData = new FormData();
                    formData.append('music', this.uploadedMusicFile);
                    
                    const uploadResponse = await fetch('/upload-music', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const uploadResult = await uploadResponse.json();
                    
                    if (!uploadResult.success) {
                        throw new Error(uploadResult.error || 'Music upload failed');
                    }
                    
                    musicSource = uploadResult.filepath;
                    this.showToast('Music file uploaded successfully', 'success');
                    
                } catch (error) {
                    this.hideLoading();
                    this.showToast('Failed to upload music: ' + error.message, 'error');
                    return;
                } finally {
                    this.hideLoading();
                }
            } else if (currentMusicSource === 'url') {
                musicSource = document.getElementById('musicUrl').value.trim();
            }
            
            const musicVolume = parseInt(document.getElementById('musicVolume').value) / 100;
            
            // Get all text overlays
            const textOverlays = [];
            document.querySelectorAll('.text-overlay-item').forEach(item => {
                const text = item.querySelector('.overlay-text').value.trim();
                const position = item.querySelector('.overlay-position').value;
                const duration = parseInt(item.querySelector('.overlay-duration').value);
                
                if (text) {
                    textOverlays.push({ text, position, duration });
                }
            });
            
            editingOptions = {
                enabled: true,
                music_url: currentMusicSource === 'url' ? musicSource : null,
                music_file: currentMusicSource === 'file' ? musicSource : null,
                music_volume: musicVolume,
                text_overlays: textOverlays.length > 0 ? textOverlays : null
            };
        }
        
        uploadData.editing = editingOptions;
        
        this.hideResults();
        this.showProgress();
        
        try {
            const response = await fetch(uploadEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(uploadData)
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
        
        if (task.metadata && task.status === 'uploading') {
            this.displayMetadata(task.metadata);
        }
    }

    getStatusTitle(status) {
        const titles = {
            'started': 'Starting...',
            'downloading': 'Downloading Reel',
            'editing': 'Editing Video', // ✅ NEW: Add editing status
            'generating_metadata': 'AI Analyzing Video',
            'uploading': 'Uploading to YouTube',
            'completed': 'Upload Complete',
            'failed': 'Upload Failed'
        };
        return titles[status] || 'Processing...';
    }

    displayMetadata(metadata) {
        this.previewTitle.textContent = metadata.title || '-';
        this.previewDescription.textContent = metadata.description || '-';
        
        this.previewTags.innerHTML = '';
        if (metadata.tags && metadata.tags.length > 0) {
            metadata.tags.slice(0, 15).forEach(tag => {
                const span = document.createElement('span');
                span.textContent = tag;
                this.previewTags.appendChild(span);
            });
        }
        
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
        this.authSection.style.display = 'none';
        this.uploadSection.style.display = 'block';
    }

    showAuthSection() {
        this.authSection.style.display = 'block';
        this.uploadSection.style.display = 'none';
        this.channelInfo.style.display = 'none';
        
        // ✅ ADDED: Hide main logout button when showing auth section
        if (this.logoutBtnMain) {
            this.logoutBtnMain.style.display = 'none';
        }
        
        // Update navbar
        this.navUserMenu.style.display = 'none';
        this.navAuthButtons.style.display = 'flex';
        
        // ✅ ADDED: Hide navbar logout button
        if (this.navLogoutBtn) {
            this.navLogoutBtn.style.display = 'none';
        }
        
        // Update mobile menu
        this.mobileUserInfo.style.display = 'none';
        this.mobileLogoutBtn.style.display = 'none';
        this.mobileSignInBtn.style.display = 'block';
        
        // Clear any ongoing processes
        this.stopStatusPolling();
        this.currentTaskId = null;
        this.hideResults();
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

document.addEventListener('DOMContentLoaded', () => {
    new YouTubeUploader();
});

// Helper functions
function showLoadingOverlay(message) {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.querySelector('p').textContent = message;
        overlay.style.display = 'flex';
    }
}

function hideLoadingOverlay() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    if (toast) {
        toast.textContent = message;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 3000);
    }
}

// Modified upload function to handle music file
async function startUpload() {
    const reelUrl = document.getElementById('reelUrl').value.trim();
    
    if (!reelUrl) {
        showToast('Please enter an Instagram Reel URL', 'error');
        return;
    }

    // Check if editing is enabled
    const editingEnabled = document.getElementById('enableEditingToggle').checked;
    let editingOptions = null;

    if (editingEnabled) {
        let musicPath = null;
        
        // Handle music upload if local file is selected
        if (currentMusicSource === 'file' && uploadedMusicFile) {
            showLoadingOverlay('Uploading background music...');
            
            try {
                const formData = new FormData();
                formData.append('music', uploadedMusicFile);
                
                const uploadResponse = await fetch('/upload-music', {
                    method: 'POST',
                    body: formData
                });
                
                const uploadResult = await uploadResponse.json();
                
                if (!uploadResult.success) {
                    throw new Error(uploadResult.error || 'Music upload failed');
                }
                
                musicPath = uploadResult.filepath;
                hideLoadingOverlay();
                
            } catch (error) {
                hideLoadingOverlay();
                showToast('Failed to upload music file: ' + error.message, 'error');
                return;
            }
        } else if (currentMusicSource === 'url') {
            musicPath = document.getElementById('musicUrl').value.trim();
        }

        // Collect text overlays
        const textOverlays = [];
        document.querySelectorAll('.text-overlay-item').forEach(item => {
            const text = item.querySelector('.overlay-text').value.trim();
            if (text) {
                textOverlays.push({
                    text: text,
                    position: item.querySelector('.overlay-position').value,
                    duration: parseInt(item.querySelector('.overlay-duration').value) || 5
                });
            }
        });

        editingOptions = {
            enabled: true,
            music_url: currentMusicSource === 'url' ? musicPath : null,
            music_file: currentMusicSource === 'file' ? musicPath : null,
            music_volume: parseInt(document.getElementById('musicVolume').value) / 100,
            text_overlays: textOverlays
        };
    }

    // Start async upload
    try {
        showLoadingOverlay('Starting upload process...');
        
        const response = await fetch('/auto-upload-async', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: reelUrl,
                editing: editingOptions
            })
        });

        const result = await response.json();
        hideLoadingOverlay();

        if (result.success) {
            // Start polling for status
            pollTaskStatus(result.task_id);
        } else {
            showToast(result.error || 'Failed to start upload', 'error');
        }

    } catch (error) {
        hideLoadingOverlay();
        showToast('Error: ' + error.message, 'error');
    }
}

// ✅ NEW: Add beforeunload warning if upload in progress
window.addEventListener('beforeunload', (e) => {
    const uploader = window.youtubeUploaderInstance;
    if (uploader && uploader.currentTaskId) {
        e.preventDefault();
        e.returnValue = 'Upload in progress. Are you sure you want to leave?';
        return e.returnValue;
    }
});

document.addEventListener('DOMContentLoaded', () => {
    window.youtubeUploaderInstance = new YouTubeUploader();
});
