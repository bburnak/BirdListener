/* =========================================================================
   BirdListener Dashboard — Chart Configurations (Chart.js)
   ========================================================================= */

/**
 * Earthy color palette for chart series.
 * Each species gets a different color; cycles if more species than colors.
 */
const CHART_COLORS = [
    '#4a7c59', '#d4a259', '#87CEEB', '#8b6f47', '#c76b6b',
    '#6fa87e', '#b08dcc', '#cc9966', '#5fa3c7', '#e6a8a0',
    '#7cb5a0', '#d4c062', '#a0785e', '#6b8fa3', '#c4a7d4',
];

function getChartColor(index) {
    return CHART_COLORS[index % CHART_COLORS.length];
}

/**
 * Build or update the daily stacked bar chart.
 * @param {string} canvasId - Canvas element ID
 * @param {object} data - API response from /api/stats/daily
 * @returns {Chart} The Chart.js instance
 */
let dailyChartInstance = null;

function renderDailyChart(canvasId, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');

    if (dailyChartInstance) {
        dailyChartInstance.destroy();
    }

    const datasets = data.series.map((s, i) => ({
        label: s.common_name,
        data: s.data,
        backgroundColor: getChartColor(i),
        borderRadius: 3,
        maxBarThickness: 28,
    }));

    dailyChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.hours.map(h => `${String(h).padStart(2, '0')}:00`),
            datasets: datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        boxWidth: 12,
                        padding: 12,
                        font: { size: 11 },
                    },
                },
                tooltip: {
                    callbacks: {
                        title: (items) => `Hour: ${items[0].label}`,
                    },
                },
            },
            scales: {
                x: {
                    stacked: true,
                    title: { display: true, text: 'Hour (UTC)', font: { size: 12 } },
                    ticks: { font: { size: 10 } },
                    grid: { display: false },
                },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    title: { display: true, text: 'Detections', font: { size: 12 } },
                    ticks: {
                        stepSize: 1,
                        font: { size: 10 },
                    },
                },
            },
        },
    });

    return dailyChartInstance;
}


/**
 * Build or update the weekly stacked bar chart.
 * @param {string} canvasId - Canvas element ID
 * @param {object} data - API response from /api/stats/weekly
 * @returns {Chart} The Chart.js instance
 */
let weeklyChartInstance = null;

function renderWeeklyChart(canvasId, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');

    if (weeklyChartInstance) {
        weeklyChartInstance.destroy();
    }

    const dayLabels = data.days.map(d => {
        const dt = new Date(d + 'T00:00:00');
        return dt.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
    });

    const datasets = data.series.map((s, i) => ({
        label: s.common_name,
        data: s.data,
        backgroundColor: getChartColor(i),
        borderRadius: 4,
        maxBarThickness: 48,
    }));

    weeklyChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: dayLabels,
            datasets: datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        boxWidth: 12,
                        padding: 12,
                        font: { size: 11 },
                    },
                },
            },
            scales: {
                x: {
                    stacked: true,
                    title: { display: true, text: 'Day', font: { size: 12 } },
                    grid: { display: false },
                },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    title: { display: true, text: 'Detections', font: { size: 12 } },
                    ticks: {
                        stepSize: 1,
                        font: { size: 10 },
                    },
                },
            },
        },
    });

    return weeklyChartInstance;
}
