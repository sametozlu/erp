/**
 * RoutingCache
 * Multi-layer caching system: In-memory and LocalStorage.
 * Designed to cache OSRM route results to reduce API calls and improve performance.
 */
class RoutingCache {
    constructor() {
        this.memoryCache = new Map();
        this.storageKey = 'v12_routing_cache_v1';
        this.cleanupInterval = 1000 * 60 * 60; // 1 hour

        this.loadFromStorage();

        // Periodic cleanup
        setInterval(() => this.cleanup(), this.cleanupInterval);
    }

    /**
     * Loads cached routes from LocalStorage into memory
     */
    loadFromStorage() {
        try {
            const stored = localStorage.getItem(this.storageKey);
            if (stored) {
                const parsed = JSON.parse(stored);
                const now = Date.now();

                Object.entries(parsed).forEach(([key, value]) => {
                    // Check expiry (verify freshness)
                    if (value.expiry && value.expiry > now) {
                        this.memoryCache.set(key, value.data);
                    }
                });
                console.log(`RoutingCache: Loaded ${this.memoryCache.size} routes from storage.`);
            }
        } catch (e) {
            console.warn('RoutingCache: Failed to load from storage', e);
            localStorage.removeItem(this.storageKey);
        }
    }

    /**
     * Saves current memory cache to LocalStorage
     * Implementation limits the size to prevent quota errors
     */
    saveToStorage() {
        try {
            const serialized = {};
            // Limit what we save to storage to avoid quota limits
            // Save max 200 most recent entries
            let count = 0;
            // Iterate and save. Note: Map iteration order is insertion order, so this preserves old entries.
            // A true LRU would be better but this is sufficient for Phase 1.
            const entries = Array.from(this.memoryCache.entries()).slice(-200);

            for (const [key, data] of entries) {
                serialized[key] = {
                    data: data,
                    expiry: Date.now() + (1000 * 60 * 60 * 24 * 7) // 7 days retention
                };
            }

            localStorage.setItem(this.storageKey, JSON.stringify(serialized));
        } catch (e) {
            console.warn('RoutingCache: Failed to save to storage', e);
        }
    }

    /**
     * Generates a unique key for a set of route points
     * @param {Array} points Array of LatLng objects or arrays
     */
    getKey(points) {
        // Normalize points to string to use as key
        // Assuming points are objects with lat, lng or arrays
        try {
            return JSON.stringify(points.map(p => {
                // Leaflet LatLng object or simple object
                if (p.lat !== undefined && p.lng !== undefined) {
                    return [Number(p.lat).toFixed(5), Number(p.lng).toFixed(5)];
                }
                // Array format [lat, lng]
                if (Array.isArray(p)) {
                    return [Number(p[0]).toFixed(5), Number(p[1]).toFixed(5)];
                }
                return p;
            }));
        } catch (e) {
            console.error("RoutingCache: Key generation failed", e);
            return null;
        }
    }

    /**
     * Retrieves a route from cache
     * @param {Array} points 
     * @returns {Object|null} Cached route data or null
     */
    get(points) {
        const key = this.getKey(points);
        if (!key) return null;

        if (this.memoryCache.has(key)) {
            // console.debug("RoutingCache: Hit");
            return this.memoryCache.get(key);
        }
        return null;
    }

    /**
     * Adds a route to the cache
     * @param {Array} points 
     * @param {Object} routeData 
     */
    set(points, routeData) {
        const key = this.getKey(points);
        if (!key) return;

        this.memoryCache.set(key, routeData);
        // Save to storage async/debounced could be added here
        // For now, save immediately for simplicity
        requestAnimationFrame(() => this.saveToStorage());
    }

    cleanup() {
        // Logic to remove very old items from memory if needed
        // Currently handled by loadFromStorage expiry check
    }

    clear() {
        this.memoryCache.clear();
        localStorage.removeItem(this.storageKey);
        console.log("RoutingCache: Cleared");
    }
}

window.RoutingCache = RoutingCache;
