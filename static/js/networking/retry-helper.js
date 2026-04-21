/**
 * RetryHelper
 * Provides exponential backoff retry logic for fetch requests.
 */
class RetryHelper {
    constructor(options = {}) {
        this.maxRetries = options.maxRetries || 3;
        this.baseDelay = options.baseDelay || 1000; // 1 second
        this.backoffFactor = options.backoffFactor || 2;
    }

    /**
     * Performs a fetch request with retry logic
     * @param {string} url 
     * @param {object} options 
     */
    async fetch(url, options = {}) {
        let attempt = 0;

        while (attempt <= this.maxRetries) {
            try {
                const response = await fetch(url, options);

                // If response is successful, return it
                if (response.ok) {
                    return response;
                }

                // Don't retry 4xx errors (client errors), except 429 and 408
                // 408: Request Timeout, 429: Too Many Requests
                if (response.status >= 400 && response.status < 500 && ![408, 429].includes(response.status)) {
                    return response;
                }

                // If 5xx or specific 4xx, we retry
                console.warn(`Request failed with status ${response.status}. Attempt ${attempt + 1}/${this.maxRetries + 1}`);
                throw new Error(`Request failed with status ${response.status}`);

            } catch (error) {
                attempt++;
                if (attempt > this.maxRetries) {
                    throw error;
                }

                const delay = this.baseDelay * Math.pow(this.backoffFactor, attempt - 1);
                console.log(`Retrying in ${delay}ms... (Error: ${error.message})`);
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }
    }
}

// Export as global for non-module usage
window.RetryHelper = RetryHelper;
