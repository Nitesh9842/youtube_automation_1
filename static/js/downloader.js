class InstagramDownloader {
    constructor() {
        this.currentFilename = null;
        this.init();
    }

    init() {
        this.cacheElements();
        this.attachEventListeners();
    }

    cacheElements() {
        this.downloadUrl = document.getElementById('downloadUrl');
        this.downloadBtn = document.getElementById('downloadBtn');
        this.progressSection = document.getElementById('progressSection');
        this.progressTitle = document.getElementById('progressTitle');
        this.progressPercent = document.getElementById('progressPercent');
        this.progressFill = document.getElementById('progressFill');
        this.progressMessage = document.getElementById('progressMessage');
        this.successResult = document.getElementById('successResult');
        this.errorResult = document.getElementById('errorResult');
        this.errorMessage = document.getElementById('errorMessage');
        this.retryBtn = document.getElementById('retryBtn');
        this.downloadAgainBtn = document.getElementById('downloadAgainBtn');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.toast = document.getElementById('toast');
    }

    attachEventListeners() {
        this.downloadBtn.addEventListener('click', () => this.handleDownload());
        this.retryBtn.addEventListener('click', () => this.resetForm());
        this.downloadAgainBtn.addEventListener('click', () => this.resetForm());
        this.downloadUrl.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.handleDownload();
        });
    }

    async handleDownload() {
        const url = this.downloadUrl.value.trim();
        
        if (!url) {
            this.showToast('Please enter a valid Instagram Reel URL', 'error');
            return;
        }
        
        this.hideResults();
        this.showProgress('Downloading...', 30, 'Preparing to download reel...');
        
        try {
            // Step 1: Request download from server
            this.updateProgress('Downloading...', 40, 'Downloading from Instagram...');
            
            const response = await fetch('/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            
            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.error || data.details || 'Download failed');
            }
            
            this.currentFilename = data.filename;
            
            // Step 2: Download the file using fetch and blob
            this.updateProgress('Downloading...', 70, 'Preparing file for download...');
            
            try {
                const videoResponse = await fetch(`/get-video/${data.filename}`);
                
                if (!videoResponse.ok) {
                    throw new Error('Failed to fetch video file from server');
                }
                
                // Get the video as a blob
                const blob = await videoResponse.blob();
                
                // Create a download URL from the blob
                const downloadUrl = window.URL.createObjectURL(blob);
                
                // Create and trigger download
                const link = document.createElement('a');
                link.href = downloadUrl;
                link.download = data.filename;
                link.style.display = 'none';
                document.body.appendChild(link);
                link.click();
                
                // Cleanup
                setTimeout(() => {
                    document.body.removeChild(link);
                    window.URL.revokeObjectURL(downloadUrl);
                }, 100);
                
                // Step 3: Show success
                this.updateProgress('Complete!', 100, 'Download completed successfully!');
                
                setTimeout(() => {
                    this.showSuccess();
                    this.showToast('Download completed! Check your downloads folder.', 'success');
                    
                    // Clean up file after 30 seconds
                    setTimeout(() => this.cleanupFile(data.filename), 30000);
                }, 500);
                
            } catch (downloadError) {
                console.error('Download error:', downloadError);
                throw new Error('Failed to download video file. Please try again.');
            }
            
        } catch (error) {
            console.error('Download error:', error);
            this.showError(error.message);
        }
    }

    async cleanupFile(filename) {
        try {
            await fetch(`/cleanup/${filename}`, { method: 'POST' });
        } catch (error) {
            console.log('Cleanup error (non-critical):', error);
        }
    }

    updateProgress(title, percent, message) {
        this.progressTitle.textContent = title;
        this.progressPercent.textContent = `${percent}%`;
        this.progressFill.style.width = `${percent}%`;
        this.progressMessage.textContent = message;
    }

    showProgress(title = 'Downloading...', percent = 0, message = 'Starting...') {
        this.progressSection.style.display = 'block';
        this.updateProgress(title, percent, message);
    }

    showSuccess() {
        this.progressSection.style.display = 'none';
        this.successResult.style.display = 'block';
    }

    showError(message) {
        this.progressSection.style.display = 'none';
        this.errorResult.style.display = 'block';
        this.errorMessage.textContent = message;
        this.showToast('Download failed: ' + message, 'error');
    }

    hideResults() {
        this.successResult.style.display = 'none';
        this.errorResult.style.display = 'none';
        this.progressSection.style.display = 'none';
    }

    resetForm() {
        this.downloadUrl.value = '';
        this.hideResults();
        this.currentFilename = null;
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
}

document.addEventListener('DOMContentLoaded', () => {
    new InstagramDownloader();
});
