// Overview: six cards (radiation, heart rate, SpO2, activity, sleep and recovery when reliable, sensors), then
// notifications and daily suggestions. Needs core.js. Device cards come from one source (SOURCE).
// A reading is shown as a value only when its signal quality is good; poor or missing is shown as such, never as 0.

const STILL_G = 0.05;                 // same threshold as the rest analysis (backend/rest.py)

function setCard(id, key) {
    const node = $(id);
    [...node.classList].filter((c) => /^scard-(normal|elevated|high|severe|unknown)$/.test(c)).forEach((c) => node.classList.remove(c));
    node.classList.add(`scard-${key}`);
}
const flux2 = (v) => (v === null || v === undefined ? '--' : v >= 100 ? Math.round(v).toLocaleString('en-US') : String(Math.round(v * 100) / 100));

// ---- radiation (both radiation sources are read; the one with the higher level is shown, like the notification) ----
async function loadRadiation() {
    const results = [];
    for (const source of ['external']) {   // real NOAA data only; the simulated storm exists only in the Radiation page demo
        try { results.push({ source, data: await api(`/radiation/status?source=${source}`, false) }); } catch (error) { /* offline: handled below */ }
    }
    // the simulated scenario counts only while it has data; the real feed is always a candidate
    const usable = results.filter((r) => r.source === 'external' || radState(r.data).key !== 'unknown');
    const best = usable.reduce((a, b) => (!a || b.data.state.level > a.data.state.level ? b : a), null);
    if (!best) {
        setCard('c-rad', 'unknown');
        $('c-rad-value').textContent = RAD_STATE_TEXT.unknown.title;
        $('c-rad-sub').textContent = 'Insufficient data';
        return;
    }
    const s = best.data;
    const st = radState(s);
    $('c-rad').href = `radiation.html?source=${SOURCE}&rad=${best.source}`;
    setCard('c-rad', st.key);
    const value = $('c-rad-value');
    value.replaceChildren(el('span', '', st.title));
    if (st.key !== 'unknown') {
        const cls = s.state.s_class_now;
        value.append(el('span', 'unit', cls === null ? '' : cls === 0 ? 'no solar storm' : `storm level S${cls}`));
    }
    const words = { normal: 'Quiet Sun, normal radiation', elevated: 'Small solar storm', high: 'Strong solar storm', severe: 'Very strong solar storm', unknown: 'No data' };
    const note = !st.current && st.key !== 'unknown' ? ' (last known)' : '';
    $('c-rad-sub').textContent = `${words[st.key]}${st.key !== 'unknown' && best.source === 'simulated' ? ' (simulated)' : ''}${note}`;
    try {   // the early heads-up: watch or prepare while the particle level is still quiet
        const o = await api('/radiation/outlook?source=external', false);
        if (st.key === 'normal' && (o.stage.key === 'watch' || o.stage.key === 'prepare')) $('c-rad-sub').textContent = o.stage.key === 'watch' ? 'Watch: the Sun is active' : 'Get ready: levels may rise';
    } catch (error) { /* the outlook is optional */ }
}

// ---- heart rate, SpO2, activity, sensors ----
function movementOf(r) {
    if ([r.accel_x_g, r.accel_y_g, r.accel_z_g].some((v) => v === null || v === undefined)) return null;
    return Math.abs(Math.hypot(r.accel_x_g, r.accel_y_g, r.accel_z_g) - 1);
}

// Status under each value: how it compares with the person's own baseline, from the existing calculations.
// Without a reliable value or a baseline the card says "Insufficient data". Nothing is classed normal without data.
const INSUFFICIENT = 'Insufficient data';
let baselineStatus = { hr: INSUFFICIENT, spo2: INSUFFICIENT, rest: INSUFFICIENT, activity: INSUFFICIENT };

function renderNow(latest, history, stale) {
    const quality = latest ? latest.signal_quality : null;
    const reliable = quality === 'good' && !stale;
    $('hr-value').textContent = reliable ? show(latest.heart_rate_bpm) : '--';
    $('spo2-value').textContent = reliable ? show(latest.spo2_percent) : '--';
    $('c-hr-note').textContent = reliable ? baselineStatus.hr : INSUFFICIENT;
    $('c-spo2-note').textContent = reliable ? baselineStatus.spo2 : INSUFFICIENT;
    const key = !latest || stale ? 'unknown' : quality === 'good' ? 'normal' : 'elevated';
    setCard('c-hr', reliable && baselineStatus.hr === 'Above personal baseline' ? 'elevated' : reliable && baselineStatus.hr === 'Below personal baseline' ? 'elevated' : reliable && baselineStatus.hr === INSUFFICIENT ? 'unknown' : key);
    setCard('c-spo2', !reliable ? key : baselineStatus.spo2 === INSUFFICIENT ? 'unknown' : baselineStatus.spo2 === 'Within normal range' ? 'normal' : 'elevated');

    const moves = history.map(movementOf).filter((v) => v !== null);
    if (!moves.length || stale) {
        $('c-act-value').textContent = '--';
        $('c-act-note').textContent = INSUFFICIENT;
        setCard('c-act', 'unknown');
    } else {
        const mean = moves.reduce((a, b) => a + b, 0) / moves.length;
        $('c-act-value').textContent = mean > STILL_G ? 'MOVING' : 'STILL';
        $('c-act-note').textContent = baselineStatus.activity;
        setCard('c-act', baselineStatus.activity === INSUFFICIENT ? 'unknown' : baselineStatus.activity === 'Normal activity' ? 'normal' : 'elevated');
    }

    let value = 'NO DATA'; let text = INSUFFICIENT; let k = 'unknown';
    if (latest && stale) { value = 'NO NEW DATA'; text = 'Sensors not sending'; }
    else if (latest && quality === 'good') { value = 'RELIABLE'; text = 'Reliable signal'; k = 'normal'; }
    else if (latest) { value = quality === 'no_finger' ? 'NO FINGER' : 'POOR SIGNAL'; text = 'Unreliable signal'; k = 'elevated'; }
    $('c-sens-value').textContent = value;
    $('c-sens-note').textContent = text;
    setCard('c-sens', k);
}

async function loadBaselineStatus() {
    // heart rate: today's median against the personal baseline (GET /api/observation, rule hr_vs_baseline)
    try {
        const obs = await api(`/observation?date=${localToday()}`);
        const hr = obs.observations.find((o) => o.id === 'hr_vs_baseline');
        if (!hr) baselineStatus.hr = INSUFFICIENT;
        else if (hr.level !== 'notable') baselineStatus.hr = 'Within normal range';
        else baselineStatus.hr = hr.based_on.difference > 0 ? 'Above personal baseline' : 'Below personal baseline';
        const sp = obs.observations.find((o) => o.id === 'spo2_vs_baseline');
        baselineStatus.spo2 = !sp ? INSUFFICIENT : sp.level !== 'notable' ? 'Within normal range' : sp.based_on.difference > 0 ? 'Above personal baseline' : 'Below personal baseline';
        const rest = obs.observations.find((o) => o.id === 'rest_start_vs_usual');
        baselineStatus.rest = !rest ? INSUFFICIENT : rest.level === 'notable' ? 'Different from usual rest' : 'Usual rest pattern';
    } catch (error) { baselineStatus.hr = INSUFFICIENT; baselineStatus.spo2 = INSUFFICIENT; baselineStatus.rest = INSUFFICIENT; }
    // activity: yesterday's mean movement against the earlier days (same rule as the Activity page)
    try {
        const days = lastDays(7).slice(1);
        const means = await Promise.all(days.map(async (d) => {
            const data = await api(`/activity?window_min=60&date=${d}`);
            const values = data.windows.map((w) => w.movement_index).filter((v) => v !== null);
            return { mean: values.length ? values.reduce((a, b) => a + b, 0) / values.length : null, hours: values.length };
        }));
        const [yesterday, ...earlier] = means;
        const usable = earlier.filter((d) => d.mean !== null && d.hours >= 6);
        if (yesterday.mean === null || yesterday.hours < 6 || usable.length < 3) baselineStatus.activity = INSUFFICIENT;
        else {
            const ratio = yesterday.mean / (usable.reduce((a, d) => a + d.mean, 0) / usable.length);
            baselineStatus.activity = ratio < 0.6 ? 'Low activity' : ratio > 1.6 ? 'High activity' : 'Normal activity';
        }
    } catch (error) { baselineStatus.activity = INSUFFICIENT; }
    loadNow();
    loadSleep();
}

function lastDays(n) {
    const out = [];
    const now = new Date();
    for (let i = 0; i < n; i += 1) {
        const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i);
        out.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`);
    }
    return out;
}

async function loadNow() {
    let latest = null; let history = []; let stale = false;
    try { latest = await api('/measurements/latest'); } catch (error) { /* 404: no readings */ }
    try { history = await api('/measurements?limit=30'); } catch (error) { /* optional */ }
    try { stale = (await api(`/status?stale_after=${STALE_AFTER_S}`)).stale; } catch (error) { stale = true; }
    renderNow(latest, history, stale);
}

// ---- sleep and recovery: shown only when last night has reliable rest data ----
async function loadSleep() {
    const card = $('c-sleep');
    try {
        const data = await api('/rest?nights=7');
        const last = data.per_night[data.per_night.length - 1];
        if (last.status !== 'ok') { card.hidden = true; return; }
        card.hidden = false;
        $('c-sleep-value').textContent = `${last.duration_h} h`;
        $('c-sleep-note').textContent = baselineStatus.rest;
        setCard('c-sleep', baselineStatus.rest === 'Usual rest pattern' ? 'normal' : baselineStatus.rest === INSUFFICIENT ? 'unknown' : 'elevated');
    } catch (error) { card.hidden = true; }
}

// ---- Notifications (traffic light) and daily suggestions. Each row opens the page where the advice is. ----
function noticeRow(item, level) {
    const li = el('li');
    const link = el('a', `notice notice-${level}`);
    link.href = noticeHref(item);
    const text = el('span');
    text.append(el('span', 'notice-title', item.title), el('span', 'notice-msg', item.message || item.text));
    link.append(...(level === 'suggestion' ? [] : [levelBadge(level)]), text, el('span', 'notice-go', '›'));
    if (level !== 'suggestion') link.setAttribute('aria-label', `${LEVEL_TEXT[level]}: ${item.title}. ${item.message}`);
    li.append(link);
    return li;
}

async function loadNotices() {
    try {
        const data = await api('/notifications');
        const s = data.summary;
        $('notif-summary').textContent = s.danger || s.warning
            ? `${s.danger} action needed · ${s.warning} warning · ${s.ok} ok`
            : 'Everything looks normal';
        $('notif-list').replaceChildren(...data.notifications.map((n) => noticeRow(n, n.level)));
        $('sugg-list').replaceChildren(...data.suggestions.map((x) => noticeRow(x, 'suggestion')));
        $('notif-error').textContent = '';
        $('sugg-error').textContent = '';
    } catch (error) {
        $('notif-error').textContent = 'Could not load the notifications (server not reachable?).';
        $('sugg-error').textContent = 'Could not load the suggestions (server not reachable?).';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    buildShell('index.html', 'Overview', { shortSourceLine: true });
    loadNow(); loadNotices(); loadRadiation(); loadSleep(); loadBaselineStatus();
    setInterval(loadNow, 2000);
    setInterval(loadRadiation, 10000);
    setInterval(loadSleep, 30000);
    setInterval(loadBaselineStatus, 60000);
    setInterval(loadNotices, 5000);
});
