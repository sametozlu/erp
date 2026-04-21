/**
 * OfflineManager
 * Manages IndexedDB storage for offline capabilities.
 */
class OfflineManager {
    constructor() {
        this.dbName = 'V12MapDB';
        this.dbVersion = 1;
        this.db = null;
        this.isReady = false;

        this.initPromise = this.initDB();
    }

    initDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);

            request.onerror = (event) => {
                console.error("OfflineManager: DB error", event);
                reject("Database error");
            };

            request.onsuccess = (event) => {
                this.db = event.target.result;
                this.isReady = true;
                resolve(this.db);
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;

                // Stores
                if (!db.objectStoreNames.contains('jobs')) {
                    db.createObjectStore('jobs', { keyPath: 'week' });
                }
                if (!db.objectStoreNames.contains('routes')) {
                    db.createObjectStore('routes', { keyPath: 'id' });
                }
                if (!db.objectStoreNames.contains('vehicles')) {
                    db.createObjectStore('vehicles', { keyPath: 'plate' });
                }
                if (!db.objectStoreNames.contains('requests')) {
                    // Outbox for background sync
                    db.createObjectStore('requests', { autoIncrement: true });
                }
            };
        });
    }

    async ensureDB() {
        if (!this.db) {
            await this.initPromise;
        }
        return this.db;
    }

    // --- GENERIC HELPERS ---

    async setItem(storeName, item) {
        const db = await this.ensureDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readwrite');
            const store = tx.objectStore(storeName);
            const req = store.put(item);

            req.onsuccess = () => resolve(true);
            req.onerror = () => reject(req.error);
        });
    }

    async getItem(storeName, key) {
        const db = await this.ensureDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readonly');
            const store = tx.objectStore(storeName);
            const req = store.get(key);

            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });
    }

    async getAll(storeName) {
        const db = await this.ensureDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readonly');
            const store = tx.objectStore(storeName);
            const req = store.getAll();

            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });
    }

    // --- SPECIFIC METHODS ---

    async saveJobs(week, jobsData) {
        // Store the entire jobs response for a week
        return this.setItem('jobs', {
            week: week,
            data: jobsData,
            timestamp: Date.now()
        });
    }

    async getJobs(week) {
        const result = await this.getItem('jobs', week);
        if (result && (Date.now() - result.timestamp < 24 * 60 * 60 * 1000)) {
            // Valid for 24 hours
            return result.data;
        }
        return null;
    }

    async saveAllRoutes(week, routesData) {
        return this.setItem('routes', {
            id: 'all_' + week, // Special ID for bulk routes
            data: routesData,
            timestamp: Date.now()
        });
    }

    async getAllRoutes(week) {
        const result = await this.getItem('routes', 'all_' + week);
        if (result && (Date.now() - result.timestamp < 24 * 60 * 60 * 1000)) {
            return result.data;
        }
        return null;
    }

    async saveRoute(routeId, routeData) {
        return this.setItem('routes', {
            id: routeId,
            data: routeData,
            timestamp: Date.now()
        });
    }

    async getRoute(routeId) {
        const result = await this.getItem('routes', routeId);
        if (result && (Date.now() - result.timestamp < 24 * 60 * 60 * 1000)) {
            return result.data;
        }
        return null;
    }
}

// Global instance
window.OfflineManager = OfflineManager;
