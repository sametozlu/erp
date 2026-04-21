/**
 * VehicleManager
 * Manages vehicle markers, viewport-based loading, and periodic updates.
 */
class VehicleManager {
    constructor(map) {
        this.map = map;
        this.layer = L.layerGroup();
        this.isVisible = false;
        this.autoUpdateInterval = null;
        this.boundCheckInterval = null;
        this.lastBounds = null;
        this.params = {
            viewportMode: true, // Enable viewport-based loading
            updateInterval: 30000, // 30 seconds auto-refresh
            debounceTime: 500
        };

        // Bind methods
        this.loadVehicles = this.loadVehicles.bind(this);
        this.onMapMove = this.debounce(this.onMapMove.bind(this), this.params.debounceTime);

        // Init logic
        if (this.params.viewportMode) {
            this.map.on('moveend', this.onMapMove);
        }
    }

    destroy() {
        this.stopAutoUpdate();
        this.map.off('moveend', this.onMapMove);
        if (this.layer) this.layer.clearLayers();
    }

    toggle() {
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
        return this.isVisible;
    }

    show() {
        if (!this.map.hasLayer(this.layer)) {
            this.layer.addTo(this.map);
        }
        this.isVisible = true;
        this.loadVehicles();
        this.startAutoUpdate();
    }

    hide() {
        if (this.map.hasLayer(this.layer)) {
            this.map.removeLayer(this.layer);
        }
        this.isVisible = false;
        this.stopAutoUpdate();
    }

    startAutoUpdate() {
        this.stopAutoUpdate();
        this.autoUpdateInterval = setInterval(() => {
            if (this.isVisible) this.loadVehicles();
        }, this.params.updateInterval);
    }

    stopAutoUpdate() {
        if (this.autoUpdateInterval) {
            clearInterval(this.autoUpdateInterval);
            this.autoUpdateInterval = null;
        }
    }

    onMapMove() {
        if (!this.isVisible) return;
        // Check if moved significantly? For now just reload.
        this.loadVehicles();
    }

    async loadVehicles() {
        const btn = document.getElementById('arventoVehiclesBtn');
        const btnText = document.getElementById('arventoVehiclesBtnText');
        if (btn) btn.disabled = true;
        if (btnText) btnText.textContent = 'Yükleniyor...';

        try {
            let url = '/api/arvento/vehicles';

            // Viewport parameters
            if (this.params.viewportMode) {
                const bounds = this.map.getBounds();
                const params = new URLSearchParams({
                    min_lat: bounds.getSouth(),
                    min_lng: bounds.getWest(),
                    max_lat: bounds.getNorth(),
                    max_lng: bounds.getEast()
                });
                url += `?${params.toString()}`;
            }

            // Retry logic wrap
            let data;
            if (window.RetryHelper) {
                const res = await new RetryHelper().fetch(url);
                data = await res.json();
            } else {
                const res = await fetch(url);
                data = await res.json();
            }

            if (!data.ok) throw new Error(data.error || 'Araçlar alınamadı');

            this.renderVehicles(data.vehicles || []);

            // Update button text
            if (btnText) btnText.textContent = `Araçları Gizle (${data.count || 0})`;

            // Notify layer control if exists
            if (typeof updateLayerCounts === 'function') {
                // Hacky way to update count if logic exists elsewhere
                const el = document.getElementById('vehiclesCount');
                if (el) el.textContent = data.count || 0;
            }

        } catch (e) {
            console.error('Vehicle load error:', e);
            if (window.toast) toast('Araçlar güncellenemedi');
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    renderVehicles(vehicles) {
        this.layer.clearLayers();

        vehicles.forEach(v => {
            if (v.lat && v.lng) {
                const icon = this.createIcon(v);
                const marker = L.marker([v.lat, v.lng], { icon: icon });
                marker.bindPopup(this.createPopup(v), {
                    className: 'modern-popup',
                    maxWidth: 250
                });
                this.layer.addLayer(marker);
            }
        });
    }

    createIcon(vehicle) {
        // Re-use logic from map.html if possible or redefine here.
        // For independence, defining basic or copying logic is better.
        // Assuming global `createVehicleIcon` exists in map.html, or we can copy it later.
        if (typeof window.createVehicleIcon === 'function') {
            return window.createVehicleIcon(vehicle);
        }
        return L.divIcon({ html: '🚗' }); // Fallback
    }

    createPopup(vehicle) {
        if (typeof window.createVehiclePopup === 'function') {
            return window.createVehiclePopup(vehicle);
        }
        return vehicle.plate;
    }

    debounce(func, wait) {
        let timeout;
        return function (...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), wait);
        };
    }
}

window.VehicleManager = VehicleManager;
