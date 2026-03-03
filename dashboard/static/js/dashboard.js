/* =========================================================================
   BirdListener Dashboard — Main Application Logic
   Handles tab switching, API calls, DOM rendering, auto-refresh,
   and Wikipedia image fetching.
   ========================================================================= */

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
let REFRESH_INTERVAL_MS = 300_000;    // Default: 300s (matches default chunk_seconds), updated from API
const WIKIPEDIA_API = 'https://en.wikipedia.org/api/rest_v1/page/summary';
const FALLBACK_BIRD_EMOJI = '🐦';

// ---------------------------------------------------------------------------
// Image cache — avoids repeated Wikipedia API calls per session
// ---------------------------------------------------------------------------
const imageCache = new Map();   // scientific_name → image URL or null

async function fetchBirdImage(scientificName) {
    if (imageCache.has(scientificName)) {
        return imageCache.get(scientificName);
    }

    try {
        const slug = scientificName.replace(/ /g, '_');
        const resp = await fetch(`${WIKIPEDIA_API}/${encodeURIComponent(slug)}`);
        if (!resp.ok) {
            imageCache.set(scientificName, null);
            return null;
        }
        const data = await resp.json();
        const url = data.thumbnail?.source || null;
        imageCache.set(scientificName, url);
        return url;
    } catch {
        imageCache.set(scientificName, null);
        return null;
    }
}

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------
function confidenceClass(conf) {
    if (conf >= 0.85) return 'confidence-high';
    if (conf >= 0.7)  return 'confidence-mid';
    return 'confidence-low';
}

function formatTime(isoString) {
    try {
        const dt = new Date(isoString);
        return dt.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
        return isoString;
    }
}

function formatDate(isoString) {
    try {
        const dt = new Date(isoString);
        return dt.toLocaleDateString('en-GB', { year: 'numeric', month: 'short', day: 'numeric' });
    } catch {
        return isoString;
    }
}

function todayISO() {
    return new Date().toISOString().slice(0, 10);
}

async function apiFetch(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    return resp.json();
}

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------
const tabButtons = document.querySelectorAll('.tab-btn');
const tabPanels  = document.querySelectorAll('.tab-content');

tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        const target = btn.dataset.tab;

        tabButtons.forEach(b => { b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); });
        tabPanels.forEach(p => p.classList.remove('active'));

        btn.classList.add('active');
        btn.setAttribute('aria-selected', 'true');
        document.getElementById(`tab-${target}`).classList.add('active');

        // Load data for the activated tab
        if (target === 'overview') loadOverview();
        if (target === 'daily')    loadDaily();
        if (target === 'weekly')   loadWeekly();
        if (target === 'species')  loadSpecies();
    });
});

// ---------------------------------------------------------------------------
// OVERVIEW TAB
// ---------------------------------------------------------------------------
async function loadOverview() {
    const grid      = document.getElementById('overview-grid');
    const empty     = document.getElementById('overview-empty');
    const tsLabel   = document.getElementById('overview-timestamp');
    const indicator = document.getElementById('status-indicator');

    try {
        const data = await apiFetch('/api/detections/latest');
        indicator.classList.add('online');
        indicator.classList.remove('offline');
        indicator.title = 'Connected';

        if (!data.detections || data.detections.length === 0) {
            grid.innerHTML = '';
            empty.style.display = 'block';
            tsLabel.textContent = '—';
            return;
        }

        empty.style.display = 'none';
        tsLabel.textContent = `Last analysis: ${formatTime(data.chunk_timestamp)} UTC · ${formatDate(data.chunk_timestamp)}`;

        // Build bird cards (without images first, then load images async)
        grid.innerHTML = data.detections.map((d, i) => `
            <article class="bird-card" data-idx="${i}">
                <div class="bird-card-img placeholder" id="bird-img-${i}">${FALLBACK_BIRD_EMOJI}</div>
                <div class="bird-card-body">
                    <h3>${escapeHtml(d.common_name)}</h3>
                    <p class="scientific">${escapeHtml(d.scientific_name)}</p>
                    <div class="bird-card-meta">
                        <span class="confidence-badge ${confidenceClass(d.confidence)}">
                            ${(d.confidence * 100).toFixed(1)}%
                        </span>
                        <span class="muted">${formatTime(d.timestamp_utc)}</span>
                    </div>
                </div>
            </article>
        `).join('');

        // Load images asynchronously
        data.detections.forEach(async (d, i) => {
            const url = await fetchBirdImage(d.scientific_name);
            const el = document.getElementById(`bird-img-${i}`);
            if (url && el) {
                const img = document.createElement('img');
                img.src = url;
                img.alt = d.common_name;
                img.className = 'bird-card-img';
                img.loading = 'lazy';
                el.replaceWith(img);
            }
        });

    } catch (err) {
        indicator.classList.add('offline');
        indicator.classList.remove('online');
        indicator.title = 'Connection error';
        console.error('Overview load failed:', err);
    }
}

// ---------------------------------------------------------------------------
// DAILY TAB
// ---------------------------------------------------------------------------
const dailyPicker = document.getElementById('daily-date-picker');
dailyPicker.value = todayISO();
dailyPicker.addEventListener('change', loadDaily);

async function loadDaily() {
    const date = dailyPicker.value || todayISO();
    try {
        // Fetch chart data and detail table data in parallel
        const [statsData, detData] = await Promise.all([
            apiFetch(`/api/stats/daily?date=${date}`),
            apiFetch(`/api/detections?date=${date}&limit=500`),
        ]);

        renderDailyChart('daily-chart', statsData);

        // Populate detail table
        const tbody = document.querySelector('#daily-table tbody');
        if (detData.detections.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">No detections for this date.</td></tr>';
        } else {
            tbody.innerHTML = detData.detections.map(d => `
                <tr>
                    <td>${formatTime(d.timestamp_utc)}</td>
                    <td>${escapeHtml(d.common_name)} <small class="muted"><i>${escapeHtml(d.scientific_name)}</i></small></td>
                    <td><span class="confidence-badge ${confidenceClass(d.confidence)}">${(d.confidence * 100).toFixed(1)}%</span></td>
                    <td>${d.chunk_start_sec.toFixed(0)}s – ${d.chunk_end_sec.toFixed(0)}s</td>
                </tr>
            `).join('');
        }
    } catch (err) {
        console.error('Daily load failed:', err);
    }
}

// ---------------------------------------------------------------------------
// WEEKLY TAB
// ---------------------------------------------------------------------------
const weeklyPicker = document.getElementById('weekly-date-picker');
weeklyPicker.value = todayISO();
weeklyPicker.addEventListener('change', loadWeekly);

async function loadWeekly() {
    const date = weeklyPicker.value || todayISO();
    try {
        const data = await apiFetch(`/api/stats/weekly?date=${date}`);

        const rangeEl = document.getElementById('weekly-range');
        rangeEl.textContent = `Week of ${data.week_start} to ${data.week_end}`;

        renderWeeklyChart('weekly-chart', data);

        // Summary stats
        const totalDetections = data.series.reduce((sum, s) => sum + s.data.reduce((a, b) => a + b, 0), 0);
        const uniqueSpecies = data.series.length;
        const activeDays = data.days.filter((_, i) =>
            data.series.some(s => s.data[i] > 0)
        ).length;

        const summaryEl = document.getElementById('weekly-summary');
        summaryEl.innerHTML = `
            <div class="stat-card">
                <div class="stat-value">${totalDetections}</div>
                <div class="stat-label">Total detections</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${uniqueSpecies}</div>
                <div class="stat-label">Species this week</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${activeDays}/7</div>
                <div class="stat-label">Active days</div>
            </div>
        `;
    } catch (err) {
        console.error('Weekly load failed:', err);
    }
}

// ---------------------------------------------------------------------------
// SPECIES TAB
// ---------------------------------------------------------------------------
async function loadSpecies() {
    const grid  = document.getElementById('species-grid');
    const empty = document.getElementById('species-empty');
    const countEl = document.getElementById('species-count');

    try {
        const data = await apiFetch('/api/species');

        if (!data.species || data.species.length === 0) {
            grid.innerHTML = '';
            empty.style.display = 'block';
            countEl.textContent = '0 species';
            return;
        }

        empty.style.display = 'none';
        countEl.textContent = `${data.count} species detected`;

        grid.innerHTML = data.species.map((s, i) => `
            <div class="species-row" data-idx="${i}">
                <div class="species-thumb placeholder" id="species-img-${i}">${FALLBACK_BIRD_EMOJI}</div>
                <div class="species-info">
                    <h4>${escapeHtml(s.common_name)}</h4>
                    <p class="scientific">${escapeHtml(s.scientific_name)}</p>
                </div>
                <div class="species-stats">
                    <div class="count">${s.total_detections}</div>
                    <div class="last-seen">Last: ${formatDate(s.last_seen)}</div>
                    <div class="muted">Avg: ${(s.avg_confidence * 100).toFixed(0)}%</div>
                </div>
            </div>
        `).join('');

        // Load thumbnails asynchronously
        data.species.forEach(async (s, i) => {
            const url = await fetchBirdImage(s.scientific_name);
            const el = document.getElementById(`species-img-${i}`);
            if (url && el) {
                const img = document.createElement('img');
                img.src = url;
                img.alt = s.common_name;
                img.className = 'species-thumb';
                img.loading = 'lazy';
                el.replaceWith(img);
            }
        });
    } catch (err) {
        console.error('Species load failed:', err);
    }
}

// ---------------------------------------------------------------------------
// HTML escaping (prevent XSS from species names)
// ---------------------------------------------------------------------------
function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}

// ---------------------------------------------------------------------------
// Auto-refresh & initial load
// ---------------------------------------------------------------------------

/**
 * Fetch the BirdListener config from the API and set the refresh interval
 * to match chunk_seconds. Falls back to the default if the API is unreachable.
 */
let refreshTimer = null;

async function initRefreshInterval() {
    try {
        const config = await apiFetch('/api/config');
        if (config.chunk_seconds && config.chunk_seconds > 0) {
            REFRESH_INTERVAL_MS = config.chunk_seconds * 1000;
        }
    } catch {
        // Keep the default
    }
    console.log(`Auto-refresh interval: ${REFRESH_INTERVAL_MS / 1000}s (matching chunk_seconds)`);

    // Clear any existing timer and start a new one
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(() => {
        if (document.getElementById('tab-overview').classList.contains('active')) {
            loadOverview();
        }
    }, REFRESH_INTERVAL_MS);
}

loadOverview();
initRefreshInterval();
