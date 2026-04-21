/**
 * Map Worker
 * Handles heavy data processing for the map module off the main thread.
 */

self.onmessage = function (e) {
    const { type, data, options } = e.data;

    switch (type) {
        case 'PROCESS_MARKERS':
            processMarkers(data, options);
            break;
        case 'PROCESS_ROUTES':
            processRoutes(data);
            break;
        default:
            console.warn('Unknown worker message type:', type);
    }
};

/**
 * Processes raw job data into map-ready format.
 * - Groups by location
 * - Calculates offsets for overlapping markers
 * - Prepares popup content data
 */
function processMarkers(allJobs, options = {}) {
    const start = performance.now();
    const byLocation = {};
    const processed = [];
    let markerIndex = 1;

    // 1. Group by location
    allJobs.forEach(job => {
        if (job.lat == null || job.lon == null) return;
        // Fix coordinates to 4 decimal places for grouping
        const key = `${Number(job.lat).toFixed(4)},${Number(job.lon).toFixed(4)}`;
        if (!byLocation[key]) byLocation[key] = [];
        byLocation[key].push(job);
    });

    // 2. Flatten and apply offsets
    Object.values(byLocation).forEach(jobs => {
        jobs.forEach((job, idx) => {
            // Apply slight offset for markers at exact same location
            // Spiral or linear offset could be used, here using simple linear for now
            const offset = idx * 0.0005;

            processed.push({
                ...job,
                originalLat: job.lat,
                originalLon: job.lon,
                lat: Number(job.lat) + offset,
                lon: Number(job.lon) + offset,
                markerIndex: markerIndex++,
                isStart: job.type === 'start'
            });
        });
    });

    // 3. Return processed data
    const end = performance.now();
    self.postMessage({
        type: 'MARKERS_PROCESSED',
        data: processed,
        stats: {
            total: processed.length,
            groups: Object.keys(byLocation).length,
            time: end - start
        }
    });
}

/**
 * Processes route data
 * (Placeholder for future complex route calculations)
 */
function processRoutes(routes) {
    // Future: Calculate bounds, stats, etc.
    self.postMessage({
        type: 'ROUTES_PROCESSED',
        data: routes
    });
}
