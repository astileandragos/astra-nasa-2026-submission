// Activity page: minutes of light, moderate and high movement in each hour of one day (ICM-20948). Needs core.js, imu.js.
// An hour without readings is left empty, not shown as 0 minutes.

let actChart = null;

function lastDays(n) {
    const out = [];
    const now = new Date();
    for (let i = 0; i < n; i += 1) {
        const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i);
        out.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`);
    }
    return out;
}

async function loadActivity() {
    const date = $('day-select').value;
    try {
        const windows = await imuWindows(date, IMU.BLOCK_MIN);
        const perHour = Array.from({ length: 24 }, () => ({ light: 0, moderate: 0, high: 0, data: 0 }));
        windows.forEach((w) => {
            const level = intensityOf(w.movement_index);
            if (level === null) return;
            const bucket = perHour[Math.floor(minutesOf(w) / 60)];
            bucket.data += IMU.BLOCK_MIN;
            if (level !== 'still') bucket[level] += IMU.BLOCK_MIN;
        });
        const labels = perHour.map((_, h) => `${String(h).padStart(2, '0')}:00`);
        const series = (key) => perHour.map((b) => (b.data ? b[key] : null));          // no data: empty, not 0
        const datasets = ['light', 'moderate', 'high'].map((k) => ({ label: INTENSITY_NAMES[k], data: series(k), backgroundColor: INTENSITY_COLORS[k], borderRadius: 2 }));
        const options = {
            responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
            plugins: { legend: { display: true, labels: { usePointStyle: true, boxWidth: 8 } },
                       tooltip: { callbacks: { label: (item) => (item.parsed.y === null ? null : `${item.dataset.label}: ${item.parsed.y} min`),
                                               footer: (items) => `Data in this hour: ${perHour[items[0].dataIndex].data} min` } } },
            scales: { x: { stacked: true, ticks: { maxTicksLimit: 12 } }, y: { stacked: true, beginAtZero: true, max: 60, title: { display: true, text: 'active minutes in the hour' } } },
        };
        if (actChart) { actChart.data = { labels, datasets }; actChart.options = options; actChart.update(); } else {
            actChart = new Chart($('act-chart').getContext('2d'), { type: 'bar', data: { labels, datasets }, options });
        }
        const m = summarizeDay(windows, IMU.BLOCK_MIN);
        const summary = $('act-summary');
        if (!m.withData) {
            summary.textContent = `No motion readings on ${date} for this data source.`;
        } else {
            const best = perHour.reduce((a, b, i) => (b.light + b.moderate + b.high > a.v ? { v: b.light + b.moderate + b.high, h: i } : a), { v: -1, h: 0 });
            summary.textContent = `Active time ${hm(m.active)} (light ${hmShort(m.light)}, moderate ${hmShort(m.moderate)}, high ${hmShort(m.high)}) from ${hmShort(m.withData)} of data. Most active hour: ${String(best.h).padStart(2, '0')}:00 with ${best.v} min.`;
        }
        $('act-error').textContent = '';
    } catch (error) {
        $('act-error').textContent = 'Could not load activity (server not reachable?).';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    buildShell('activity.html', 'Activity');
    const select = $('day-select');
    lastDays(7).forEach((d, i) => {
        const option = el('option', '', i === 0 ? `${d} (today)` : d);
        option.value = d;
        select.append(option);
    });
    select.addEventListener('change', loadActivity);
    loadActivity();
    setInterval(loadActivity, 20000);
});
