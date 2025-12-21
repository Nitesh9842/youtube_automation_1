class MetadataGenerator {
    constructor() {
        this.currentVideoFile = null;
        this.currentMode = 'instagram'; // 'instagram' or 'gallery'
        this.init();
    }

    init() {
        this.cacheElements();
        this.attachEventListeners();
        this.loadGalleryVideos();
    }

    cacheElements() {
        this.metadataUrl = document.getElementById('metadataUrl');
        this.gallerySelect = document.getElementById('gallerySelect');
        this.deviceVideoUpload = document.getElementById('deviceVideoUpload');
        this.uploadProgress = document.getElementById('uploadProgress');
        this.uploadProgressFill = document.getElementById('uploadProgressFill');
        this.uploadStatus = document.getElementById('uploadStatus');
        this.generateBtn = document.getElementById('generateBtn');
        this.downloadBtn = document.getElementById('downloadBtn');
        this.refreshGalleryBtn = document.getElementById('refreshGalleryBtn');
        this.tabInstagram = document.getElementById('tabInstagram');
        this.tabGallery = document.getElementById('tabGallery');
        this.instagramSection = document.getElementById('instagramSection');
        this.gallerySection = document.getElementById('gallerySection');
        this.metadataPreview = document.getElementById('metadataPreview');
        this.previewTitle = document.getElementById('previewTitle');
        this.previewDescription = document.getElementById('previewDescription');
        this.previewTags = document.getElementById('previewTags');
        this.previewHashtags = document.getElementById('previewHashtags');
        this.previewAnalysis = document.getElementById('previewAnalysis');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.toast = document.getElementById('toast');
    }

    attachEventListeners() {
        this.generateBtn.addEventListener('click', () => this.handleGenerate());
        this.downloadBtn.addEventListener('click', () => this.handleDownload());
        this.refreshGalleryBtn.addEventListener('click', () => this.loadGalleryVideos());
        this.deviceVideoUpload.addEventListener('change', (e) => this.handleDeviceUpload(e));
        
        // Tab switching
        this.tabInstagram.addEventListener('click', () => this.switchTab('instagram'));
        this.tabGallery.addEventListener('click', () => this.switchTab('gallery'));
        
        this.metadataUrl.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.handleGenerate();
        });

        // Copy button listeners
        document.addEventListener('click', (e) => {
            if (e.target.closest('.btn-copy-small')) {
                const btn = e.target.closest('.btn-copy-small');
                const targetId = btn.getAttribute('data-copy-target');
                this.copyToClipboard(targetId, btn);
            }
        });
    }

    switchTab(mode) {
        this.currentMode = mode;
        
        if (mode === 'instagram') {
            this.tabInstagram.classList.add('btn-preview');
            this.tabInstagram.classList.remove('btn-secondary');
            this.tabGallery.classList.remove('btn-preview');
            this.tabGallery.classList.add('btn-secondary');
            this.instagramSection.style.display = 'block';
            this.gallerySection.style.display = 'none';
        } else {
            this.tabGallery.classList.add('btn-preview');
            this.tabGallery.classList.remove('btn-secondary');
            this.tabInstagram.classList.remove('btn-preview');
            this.tabInstagram.classList.add('btn-secondary');
            this.instagramSection.style.display = 'none';
            this.gallerySection.style.display = 'block';
        }
        
        // Hide download button when switching tabs
        this.downloadBtn.style.display = 'none';
        this.metadataPreview.style.display = 'none';
    }

    async handleDeviceUpload(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        // Validate file type
        if (!file.type.startsWith('video/')) {
            this.showToast('Please select a valid video file', 'error');
            return;
        }
        
        // Show progress
        this.uploadProgress.style.display = 'block';
        this.uploadProgressFill.style.width = '0%';
        this.uploadStatus.textContent = 'Uploading video to gallery...';
        
        try {
            const formData = new FormData();
            formData.append('video', file);
            
            const response = await fetch('/upload-to-gallery', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.uploadProgressFill.style.width = '100%';
                this.uploadStatus.textContent = 'Upload complete! Generating metadata...';
                
                // Now generate metadata for the uploaded video
                await this.generateFromGalleryFile(data.filename);
                
                // Refresh gallery list
                await this.loadGalleryVideos();
                
                // Hide progress
                setTimeout(() => {
                    this.uploadProgress.style.display = 'none';
                }, 2000);
                
                this.showToast('Video uploaded and analyzed successfully! ✨', 'success');
            } else {
                throw new Error(data.error || 'Upload failed');
            }
        } catch (error) {
            this.uploadProgress.style.display = 'none';
            this.showToast('Upload failed: ' + error.message, 'error');
        }
        
        // Reset file input
        event.target.value = '';
    }

    async generateFromGalleryFile(videoFile) {
        try {
            const response = await fetch('/generate-metadata-gallery', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ video_file: videoFile })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentVideoFile = data.video_file;
                this.displayMetadata(data);
                this.downloadBtn.style.display = 'none';
            } else {
                throw new Error(data.error || 'Generation failed');
            }
        } catch (error) {
            throw error;
        }
    }

    async loadGalleryVideos() {
        try {
            const response = await fetch('/list-gallery-videos');
            const data = await response.json();
            
            this.gallerySelect.innerHTML = '<option value="">Select existing video from gallery...</option>';
            
            if (data.success && data.videos.length > 0) {
                data.videos.forEach(video => {
                    const option = document.createElement('option');
                    option.value = video;
                    option.textContent = video;
                    this.gallerySelect.appendChild(option);
                });
                if (this.currentMode === 'gallery') {
                    this.showToast(`Found ${data.videos.length} videos in gallery`, 'success');
                }
            } else {
                if (this.currentMode === 'gallery') {
                    this.showToast('Gallery is empty', 'warning');
                }
            }
        } catch (error) {
            this.showToast('Failed to load gallery: ' + error.message, 'error');
        }
    }

    async handleGenerate() {
        if (this.currentMode === 'instagram') {
            await this.generateFromInstagram();
        } else {
            await this.generateFromGallery();
        }
    }

    async generateFromInstagram() {
        const url = this.metadataUrl.value.trim();
        
        if (!url) {
            this.showToast('Please enter a valid Instagram Reel URL', 'error');
            return;
        }
        
        this.showLoading('AI is downloading video to gallery and analyzing...');
        
        try {
            const response = await fetch('/generate-metadata-instagram', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentVideoFile = data.video_file;
                this.displayMetadata(data);
                this.downloadBtn.style.display = 'none'; // No download button needed - it's in gallery
                this.showToast('Video saved to gallery & metadata generated! ✨', 'success');
                // Refresh gallery list
                await this.loadGalleryVideos();
            } else {
                throw new Error(data.error || 'Generation failed');
            }
        } catch (error) {
            this.showToast('Generation failed: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async generateFromGallery() {
        const videoFile = this.gallerySelect.value;
        
        if (!videoFile) {
            this.showToast('Please select a video from gallery', 'error');
            return;
        }
        
        this.showLoading('AI is analyzing your gallery video...');
        
        try {
            const response = await fetch('/generate-metadata-gallery', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ video_file: videoFile })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentVideoFile = data.video_file;
                this.displayMetadata(data);
                this.downloadBtn.style.display = 'none'; // Already in gallery
                this.showToast('AI metadata generated successfully! ✨', 'success');
            } else {
                throw new Error(data.error || 'Generation failed');
            }
        } catch (error) {
            this.showToast('Generation failed: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async handleDownload() {
        if (!this.currentVideoFile) {
            this.showToast('No video file available to download', 'error');
            return;
        }

        try {
            this.showLoading('Preparing your download...');
            
            // Download the video file
            const response = await fetch(`/get-video/${this.currentVideoFile}`);
            
            if (!response.ok) {
                throw new Error('Download failed');
            }

            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = this.currentVideoFile;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(downloadUrl);

            this.showToast('Video downloaded successfully! 🎉', 'success');
            
            // Cleanup server file
            await fetch(`/cleanup/${this.currentVideoFile}`, { method: 'POST' });
            
        } catch (error) {
            this.showToast('Download failed: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    displayMetadata(data) {
        this.previewTitle.textContent = data.title || '-';
        this.previewDescription.textContent = data.description || '-';
        
        // Display video analysis if available
        if (this.previewAnalysis && data.video_analysis) {
            this.previewAnalysis.textContent = data.video_analysis;
        }
        
        // Display tags
        this.previewTags.innerHTML = '';
        if (data.tags && data.tags.length > 0) {
            data.tags.slice(0, 15).forEach(tag => {
                const span = document.createElement('span');
                span.textContent = tag;
                this.previewTags.appendChild(span);
            });
        }
        
        // Display hashtags
        this.previewHashtags.innerHTML = '';
        if (data.hashtags && data.hashtags.length > 0) {
            data.hashtags.slice(0, 20).forEach(hashtag => {
                const span = document.createElement('span');
                span.textContent = hashtag;
                this.previewHashtags.appendChild(span);
            });
        }
        
        this.metadataPreview.style.display = 'block';
    }

    async copyToClipboard(elementId, button) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const text = element.textContent;
        
        try {
            await navigator.clipboard.writeText(text);
            
            // Visual feedback
            const originalHTML = button.innerHTML;
            button.innerHTML = '<i class="fas fa-check"></i> Copied!';
            button.style.background = 'linear-gradient(135deg, var(--success) 0%, #00C853 100%)';
            
            setTimeout(() => {
                button.innerHTML = originalHTML;
                button.style.background = '';
            }, 2000);
            
            this.showToast('Copied to clipboard! 📋', 'success');
        } catch (error) {
            this.showToast('Failed to copy: ' + error.message, 'error');
        }
    }

    showLoading(message = 'Loading...') {
        this.loadingOverlay.style.display = 'flex';
        const loadingText = this.loadingOverlay.querySelector('p');
        if (loadingText) {
            loadingText.textContent = message;
        }
    }

    hideLoading() {
        this.loadingOverlay.style.display = 'none';
    }

    showToast(message, type = 'info') {
        this.toast.textContent = message;
        this.toast.className = 'toast show';
        
        if (type === 'success') {
            this.toast.classList.add('toast-success');
        } else if (type === 'error') {
            this.toast.classList.add('toast-error');
        } else if (type === 'warning') {
            this.toast.classList.add('toast-warning');
        }
        
        setTimeout(() => {
            this.toast.classList.remove('show');
        }, 4000);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const generator = new MetadataGenerator();
    // Initialize with Instagram tab active
    generator.switchTab('instagram');
});
