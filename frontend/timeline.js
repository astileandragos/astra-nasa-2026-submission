// Timeline page: summary, heart rate against your baseline, active time, the exact daily log,
// and the selected day. Charts and numbers come from the same two API calls. Needs core.js and chart.js.

let rangeDays = 7;
let days = [];            // one object per day: date, hr {median,avg,min,max,n}, spo2, movement, checkin, readings
let baseline = null;
let selectedDate = null;
let hrChart = null;
let mvChart = null;

const SVG_NS = 'http://www.w3.org/2000/svg';
const fullDate = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' });

function svgEl(tag, attrs, text) {
    const node = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs || {}).forEach(([k, v]) => node.setAttribute(k, v));
    if (text !== undefined) node.textContent = text;
    return node;
}

// ---- Baseline ribbon: usual range, baseline median and today ----
function ribbon(base, today) {
    const W = 560, H = 100, pad = 28;
    const values = [base.q1, base.q3, base.median, ...(today === null ? [] : [today])];
    const lo = Math.floor(Math.min(...values) - 6), hi = Math.ceil(Math.max(...values) + 6);
    const x = (v) => pad + ((v - lo) / (hi - lo)) * (W - 2 * pad);
    const label = (v, text, y, cls) => svgEl('text', { x: Math.max(40, Math.min(W - 40, x(v))), y, 'text-anchor': 'middle', class: cls || '' }, text);
    const description = today === null
        ? `Your usual heart rate range is ${base.q1} to ${base.q3} bpm, baseline ${base.median} bpm. No heart rate reading today yet.`
        : `Today's median heart rate is ${today} bpm. Your usual range is ${base.q1} to ${base.q3} bpm, baseline ${base.median} bpm.`;
    const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, class: 'ribbon', role: 'img', 'aria-label': description });
    svg.append(svgEl('line', { x1: pad, x2: W - pad, y1: 56, y2: 56, stroke: '#E3E7EC', 'stroke-width': 2 }),
        svgEl('rect', { x: x(base.q1), y: 44, width: x(base.q3) - x(base.q1), height: 24, rx: 4, fill: '#E4F3F4', stroke: '#0E7C86', 'stroke-width': 1 }),
        svgEl('line', { x1: x(base.median), x2: x(base.median), y1: 38, y2: 74, stroke: '#0B1B33', 'stroke-width': 2 }),
        label(base.q1, String(base.q1), 92), label(base.median, `${base.median} baseline`, 92, 'r-strong'), label(base.q3, String(base.q3), 92));
    if (today !== null) {
        svg.append(svgEl('circle', { cx: x(today), cy: 56, r: 9, fill: '#0E7C86', stroke: '#FFFFFF', 'stroke-width': 3 }),
            label(today, `Today ${today}`, 28, 'r-strong'));
    }
    return { svg, description };
}

// ---- Summary tiles ----
function tile(label, value, unit, sub) {
    const box = el('div', 'tile');
    box.append(el('span', 'label', label));
    const line = el('div', 'tile-value');
    line.append(el('span', '', value));
    if (unit && value !== '--') line.append(el('span', 'unit', unit));
    box.append(line, el('span', 'note', sub || ''));
    return box;
}

function renderSummary() {
    const withHr = days.filter((d) => d.hr.n > 0);
    const n = withHr.reduce((sum, d) => sum + d.hr.n, 0);
    const avg = n ? withHr.reduce((sum, d) => sum + d.hr.avg * d.hr.n, 0) / n : null;
    const high = withHr.length ? withHr.reduce((a, b) => (b.hr.max > a.hr.max ? b : a)) : null;
    const low = withHr.length ? withHr.reduce((a, b) => (b.hr.min < a.hr.min ? b : a)) : null;
    const spo = days.filter((d) => d.spo2.n > 0);
    const sn = spo.reduce((sum, d) => sum + d.spo2.n, 0);
    const spoAvg = sn ? spo.reduce((sum, d) => sum + d.spo2.avg * d.spo2.n, 0) / sn : null;
    const r1 = (v) => (v === null ? '--' : String(Math.round(v * 10) / 10));
    $('sum-range').textContent = `${shortDate(days[0].date)} to ${shortDate(days[days.length - 1].date)} · ${withHr.length} of ${days.length} days with heart rate data · ${n} good readings`;
    $('sum-tiles').replaceChildren(
        tile('Average heart rate', r1(avg), 'bpm', 'over all good readings'),
        tile('Highest heart rate', high ? String(high.hr.max) : '--', 'bpm', high ? `on ${shortDate(high.date)}` : 'no data'),
        tile('Lowest heart rate', low ? String(low.hr.min) : '--', 'bpm', low ? `on ${shortDate(low.date)}` : 'no data'),
        tile('Average SpO2 (estimate)', r1(spoAvg), '%', 'over all good readings'),
        activeTile());
    loadActiveTime(days.map((d) => d.date));
}

// ---- Charts ----
function pickDay(event, chart) {
    const hit = chart.getElementsAtEventForMode(event, 'index', { intersect: false }, true)[0];
    if (hit) select(days[hit.index]);
}

function renderHrChart() {
    const labels = days.map((d) => shortDate(d.date));
    const medians = days.map((d) => d.hr.median);
    const q1 = baseline ? labels.map(() => baseline.q1) : [];
    const q3 = baseline ? labels.map(() => baseline.q3) : [];
    const datasets = [
        { type: 'line', label: 'range low', data: q1, order: 5, pointRadius: 0, borderWidth: 0 },
        { type: 'line', label: 'Your usual range', data: q3, order: 5, pointRadius: 0, borderWidth: 0, fill: '-1', backgroundColor: '#E4F3F4' },
        { type: 'line', label: 'Baseline', data: baseline ? labels.map(() => baseline.median) : [], order: 3, borderColor: '#0B1B33', borderDash: [6, 4], borderWidth: 1.5, pointRadius: 0 },
        { type: 'bar', label: 'Daily low to high', data: days.map((d) => (d.hr.min === null ? null : [d.hr.min, d.hr.max])), order: 4, backgroundColor: '#C9D3DE', barPercentage: 0.45 },
        { type: 'line', label: 'Daily median', data: medians, order: 1, borderColor: '#0E7C86', backgroundColor: '#0E7C86', borderWidth: 2, pointRadius: days.length > 14 ? 2.5 : 4, pointHoverRadius: 6, spanGaps: false, tension: 0 },
    ];
    const lows = days.filter((d) => d.hr.min !== null).map((d) => d.hr.min);
    const highs = days.filter((d) => d.hr.max !== null).map((d) => d.hr.max);
    const all = lows.concat(highs, baseline ? [baseline.q1, baseline.q3] : []);
    const options = {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        onClick: (event, _items, chart) => pickDay(event, chart),
        plugins: {
            legend: { display: true, labels: { filter: (item) => item.text !== 'range low', usePointStyle: true, boxWidth: 8 } },
            tooltip: {
                filter: (item) => item.dataset.label === 'Daily median',
                callbacks: {
                    title: (items) => fullDate(days[items[0].dataIndex].date),
                    label: (item) => {
                        const d = days[item.dataIndex];
                        return [`Median ${d.hr.median} bpm`, `Average ${d.hr.avg} bpm`, `Low ${d.hr.min} · High ${d.hr.max} bpm`, `${d.hr.n} good readings`];
                    },
                },
            },
        },
        scales: { x: { offset: true }, y: { beginAtZero: false, min: all.length ? Math.floor(Math.min(...all)) - 4 : 50, max: all.length ? Math.ceil(Math.max(...all)) + 4 : 100, title: { display: true, text: 'beats per minute' } } },
    };
    const data = { labels, datasets };
    if (hrChart) { hrChart.data = data; hrChart.options = options; hrChart.update(); } else {
        hrChart = new Chart($('hr-chart').getContext('2d'), { type: 'bar', data, options });
    }
}

function renderMvChart() {
    const labels = days.map((d) => shortDate(d.date));
    const datasets = [
        { type: 'bar', label: 'Active time, hours (sensor)', data: days.map((d) => (d.active === null || d.active === undefined ? null : Math.round(d.active / 6) / 10)), backgroundColor: '#0E7C86', borderRadius: 2, yAxisID: 'y', order: 2 },
    ];
    const options = {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        onClick: (event, _items, chart) => pickDay(event, chart),
        plugins: { legend: { display: true, labels: { usePointStyle: true, boxWidth: 8 } },
                   tooltip: { callbacks: { title: (items) => fullDate(days[items[0].dataIndex].date),
                                           label: (item) => (item.parsed.y === null ? null : `${item.dataset.label}: ${item.parsed.y} h`) } } },
        scales: { x: { offset: true }, y: { beginAtZero: true, suggestedMax: 10, title: { display: true, text: 'hours' } } },
    };
    const data = { labels, datasets };
    if (mvChart) { mvChart.data = data; mvChart.options = options; mvChart.update(); } else {
        mvChart = new Chart($('mv-chart').getContext('2d'), { type: 'bar', data, options });
    }
}

// ---- Daily log ----
function renderLog() {
    const body = $('log-rows');
    body.replaceChildren();
    const today = days[days.length - 1].date;
    days.slice().reverse().forEach((d) => {
        const c = d.checkin;
        const row = el('tr');
        if (d.date === today) row.className = 'today';
        const first = el('td');
        const button = el('button', 'link-button', shortDate(d.date));
        button.type = 'button';
        button.dataset.date = d.date;
        button.setAttribute('aria-pressed', String(d.date === selectedDate));
        button.addEventListener('click', () => select(d));
        first.append(button);
        row.append(first, el('td', '', String(d.readings)),
            el('td', '', show(d.hr.avg)), el('td', '', show(d.hr.min)), el('td', '', show(d.hr.max)), el('td', '', show(d.hr.median)),
            el('td', '', show(d.spo2.avg)), el('td', '', d.active === null || d.active === undefined ? '--' : hm(d.active)),
            el('td', '', c ? show(c.mood) : '--'), el('td', '', c ? show(c.energy) : '--'),
            el('td', '', c ? show(c.stress) : '--'), el('td', '', c ? show(c.fatigue) : '--'));
        body.append(row);
    });
}

// ---- Selected day ----
function dayDetail(day) {
    const host = $('day-detail');
    host.replaceChildren(el('h3', '', fullDate(day.date)));
    const sensor = el('div', 'insight-part');
    const head = el('div', 'panel-head');
    head.append(el('span', 'label', 'Sensor data'), chip(SOURCE));
    sensor.append(head);
    const dl = el('dl', 'facts');
    const hr = day.hr;
    dl.append(el('dt', '', 'Readings'), el('dd', '', String(day.readings)),
        el('dt', '', 'Heart rate'), el('dd', '', hr.n ? `average ${hr.avg}, median ${hr.median}, low ${hr.min}, high ${hr.max} bpm (${hr.n} good readings)` : '--'),
        el('dt', '', 'SpO2 (estimate)'), el('dd', '', day.spo2.n ? `average ${day.spo2.avg}, low ${day.spo2.min}, high ${day.spo2.max} %` : '--'),
        el('dt', '', 'Active time'), el('dd', '', day.active === null || day.active === undefined ? '-- (not enough data)' : hm(day.active)));
    sensor.append(dl);
    host.append(sensor);

    const check = el('div', 'insight-part');
    const head2 = el('div', 'panel-head');
    head2.append(el('span', 'label', 'Check-in'));
    if (day.checkin) head2.append(chip(day.checkin.source));
    check.append(head2);
    if (day.checkin) {
        const c = day.checkin;
        const d2 = el('dl', 'facts');
        d2.append(el('dt', '', 'Mood'), el('dd', '', show(c.mood, ' of 5')),
            el('dt', '', 'Energy'), el('dd', '', show(c.energy, ' of 5')),
            el('dt', '', 'Stress'), el('dd', '', show(c.stress, ' of 5')),
            el('dt', '', 'Fatigue'), el('dd', '', show(c.fatigue, ' of 5')));
        check.append(d2);
    } else {
        check.append(el('p', 'note', 'No check-in for this day.'));
    }
    host.append(check, el('p', 'note', 'Sensor values are estimates from the prototype. The check-in is what the person typed and is never mixed with sensor data.'));
}

function select(day) {
    selectedDate = day.date;
    document.querySelectorAll('#log-rows .link-button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.date === day.date)));
    dayDetail(day);
}

// ---- Load ----
function merge(timeline, stats) {
    return timeline.per_day.map((t, i) => {
        const s = stats.per_day[i];
        return { date: t.date, readings: t.readings, movement: t.movement_index, active: activeDays[t.date] === undefined ? null : activeDays[t.date], checkin: t.checkin,
                 hr: { ...s.heart_rate_bpm }, spo2: { ...s.spo2_percent } };
    });
}

async function load() {
    $('hr-chip').replaceChildren(chip(SOURCE));
    try {
        const [timeline, stats] = await Promise.all([api(`/timeline?days=${rangeDays}`), api(`/stats/daily?days=${rangeDays}`)]);
        days = merge(timeline, stats);
        baseline = timeline.baseline;
        renderSummary();
        const box = $('ribbon-box');
        box.replaceChildren();
        const today = days[days.length - 1].hr.median;
        if (baseline) {
            const { svg, description } = ribbon(baseline, today);
            box.append(svg, el('p', 'note', description));
            $('hr-note').textContent = `Teal line: median heart rate of each day. Grey bars: the day's lowest to highest good reading. Dashed line and shaded band: your baseline and usual range from ${baseline.days_used} earlier days (today is not part of its own baseline).`;
        } else {
            box.append(el('p', 'insight-statement', 'Your baseline is not ready yet.'),
                el('p', 'note', 'ASTRA needs 3 days with enough good readings to learn what is usual for you.'));
            $('hr-note').textContent = 'Teal line: median heart rate of each day. Grey bars: the day\'s lowest to highest good reading.';
        }
        renderHrChart();
        renderMvChart();
        const keep = days.find((d) => d.date === selectedDate) || days[days.length - 1];
        renderLog();
        select(keep);
        $('log-csv').href = `${API}/export.csv?source=${SOURCE}&days=${rangeDays}`;
        ['sum-error', 'hr-error', 'mv-error', 'log-error'].forEach((id) => { $(id).textContent = ''; });
    } catch (error) {
        ['sum-error', 'hr-error', 'mv-error', 'log-error'].forEach((id) => { $(id).textContent = 'Could not load the timeline (server not reachable?).'; });
    }
}

function setRange(n) {
    rangeDays = n;
    document.querySelectorAll('.range-btn').forEach((b) => b.setAttribute('aria-pressed', String(Number(b.dataset.days) === n)));
    load();
}

document.addEventListener('DOMContentLoaded', () => {
    buildShell('timeline.html', 'Timeline');
    document.querySelectorAll('.range-btn').forEach((b) => b.addEventListener('click', () => setRange(Number(b.dataset.days))));
    load();
    setInterval(load, 15000);
});
