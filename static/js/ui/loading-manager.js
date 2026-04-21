/**
 * LoadingManager
 * Manages the loading overlay, progress bar, and status messages for the map.
 */
class LoadingManager {
    constructor() {
        this.overlay = document.getElementById('mapLoadingOverlay');
        this.progressBar = document.getElementById('mapProgressFill');
        this.loadingText = document.getElementById('mapLoadingText');
        this.subText = document.getElementById('mapLoadingSubtext');

        // Initial state
        this.isHidden = true;
    }

    /**
     * Shows the loading overlay with a message
     * @param {string} message Main status message
     */
    show(message = "Yükleniyor...") {
        if (this.overlay) {
            this.overlay.style.display = 'flex';
            this.isHidden = false;
            this.updateStatus(message);
            this.setProgress(0);
            this.subText.textContent = "";
        }
    }

    /**
     * Hides the loading overlay
     */
    hide() {
        if (this.overlay) {
            // Add a small fade out effect check via class or just hide
            // For now direct hide as per css
            this.overlay.style.display = 'none';
            this.isHidden = true;
        }
    }

    /**
     * Updates the progress bar and subtext
     * @param {number} percent 0-100
     * @param {string} subMessage Optional detailed status (e.g. "10/50 processed")
     */
    setProgress(percent, subMessage = "") {
        if (this.progressBar) {
            this.progressBar.style.width = `${Math.min(100, Math.max(0, percent))}%`;
        }
        if (subMessage !== null && this.subText) {
            this.subText.textContent = subMessage;
        }
    }

    /**
     * Updates the main status text
     * @param {string} message 
     */
    updateStatus(message) {
        if (this.loadingText) {
            this.loadingText.textContent = message;
            this.loadingText.style.color = ""; // Reset color
        }
    }

    /**
     * Shows an error message in the loading screen
     * @param {string} message Error description
     * @param {boolean} autoHide Whether to hide after delay
     */
    error(message, autoHide = true) {
        if (this.loadingText) {
            this.loadingText.textContent = "Hata: " + message;
            this.loadingText.style.color = "#ef4444"; // Red-500
        }
        if (this.progressBar) {
            this.progressBar.style.width = "100%";
            this.progressBar.style.backgroundColor = "#ef4444";
        }

        if (autoHide) {
            setTimeout(() => {
                this.hide();
                // Reset progress bar color
                if (this.progressBar) this.progressBar.style.backgroundColor = "";
            }, 3000);
        }
    }
}

window.LoadingManager = LoadingManager;
