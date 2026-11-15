// Sensors page: is each sensor working, is the signal good, when was the last good measurement, what is missing.
// Needs core.js. Reliable means: recent readings (not stale) and a good signal quality. Missing is never shown as 0.

const SENSOR_ALERTS = {
    poor: { badge: 'elevated', title: 'POOR SENSOR SIGNAL', text: 'Your heart rate and SpO2 readings may be unreliable.',
            steps: ['Check that your finger is correctly positioned.', 'Keep your hand still.', 'Check sensor contact.', 'Wait a few seconds and measure again.'] },
    no_finger: { badge: 'elevated', title: 'NO FINGER DETECTED', text: 'Place your finger on the sensor to resume measurements.',
                 steps: ['Place your fingertip flat on the MAX30102 sensor.', 'Keep your hand still.'] },
    unavailable: { badge: 'unknown', title: 'SENSOR UNAVAILABLE', text: 'Measurements are temporarily unavailable. Check the sensor connection.',
                   steps: ['Check that the device is powered and connected.', 'Check the cable and the data connection.', 'Until readings return, do not rely on the last values shown elsewhere.'] },
    none: { badge: 'unknown', title: 'NO READINGS YET', text: 'There are no readings from this data source yet, so nothing can be judged.',
            steps: ['Start the device or the simulator for this data source.'] },
    good: { badge: 'normal', title: 'READINGS RELIABLE', text: 'The last reading had a good signal. Heart rate and SpO2 can be shown.', steps: [] },
};

function fact(list, term, value) { list.append(el('dt', '', term), el('dd', '', value)); }

function fullTime(iso) {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '--' : d.toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function setState(id, key) {
    const node = $(id);
    [...node.classList].filter((c) => /^scard-/.test(c)).forEach((c) => node.classList.remove(c));
    node.classList.add(`scard-${key}`);
}

async function loadSensors() {
    let latest = null; let history = []; let status = null;
    try { latest = await api('/measurements/latest'); } catch (error) { /* 404 = none */ }
    try { history = await api('/measurements?limit=200'); } catch (error) { /* optional */ }
    try { status = await api(`/status?stale_after=${STALE_AFTER_S}`); } catch (error) { status = { stale: true, seconds_since_last: null }; }
    const stale = !latest || status.stale;
    const quality = latest ? latest.signal_quality : null;

    // overall: can the readings be trusted
    const state = !latest ? 'none' : stale ? 'unavailable' : quality === 'good' ? 'good' : quality === 'no_finger' ? 'no_finger' : 'poor';
    const a = SENSOR_ALERTS[state];
    $('alert-badge').replaceChildren(stateBadge(a.badge));
    $('alert-title').textContent = a.title;
    $('alert-text').textContent = a.text;
    const steps = $('alert-steps');
    steps.replaceChildren();
    if (a.steps.length) {
        steps.append(el('span', 'label', 'What to do'));
        const list = el('ol', 'steps');
        a.steps.forEach((x) => list.append(el('li', '', x)));
        steps.append(list);
    }
    $('alert-panel').className = `panel scard-${a.badge === 'normal' ? 'normal' : a.badge}`;

    // MAX30102
    const goodHr = history.find((r) => r.signal_quality === 'good' && r.heart_rate_bpm !== null);
    const hasMotion = (r) => [r.accel_x_g, r.accel_y_g, r.accel_z_g].every((v) => v !== null && v !== undefined);
    const lastMotion = history.find(hasMotion);
    const maxText = { good: 'WORKING', poor: 'POOR SIGNAL', no_finger: 'NO FINGER', unavailable: 'UNAVAILABLE', none: 'NO DATA' }[state];
    $('s-max-value').textContent = maxText;
    setState('s-max', { good: 'normal', poor: 'elevated', no_finger: 'elevated', unavailable: 'unknown', none: 'unknown' }[state]);
    const maxFacts = $('s-max-facts');
    maxFacts.replaceChildren();
    fact(maxFacts, 'Current signal quality', latest ? `${{ good: 'Good', poor: 'Poor', no_finger: 'No finger', unknown: 'Unknown' }[quality] || '--'}${stale ? ' (not current)' : ''}` : '--');
    fact(maxFacts, 'Last reading', latest ? `${fullTime(latest.received_at)}${status.seconds_since_last ? ` (${formatAge(status.seconds_since_last)} ago)` : ''}` : '--');
    fact(maxFacts, 'Last successful measurement', goodHr ? `${fullTime(goodHr.received_at)} (${goodHr.heart_rate_bpm} bpm)` : 'none in the recent readings');
    fact(maxFacts, 'Measurements reliable', state === 'good' ? 'Yes' : 'No');

    // ICM-20948
    const imuText = !latest ? 'NO DATA' : stale ? 'UNAVAILABLE' : lastMotion && hasMotion(latest) ? 'WORKING' : 'NO MOTION DATA';
    $('s-imu-value').textContent = imuText;
    setState('s-imu', imuText === 'WORKING' ? 'normal' : 'unknown');
    const imuFacts = $('s-imu-facts');
    imuFacts.replaceChildren();
    fact(imuFacts, 'Last motion reading', lastMotion ? fullTime(lastMotion.received_at) : 'none in the recent readings');
    fact(imuFacts, 'Motion data in the last reading', latest ? (hasMotion(latest) ? 'Available' : 'Missing') : '--');
    fact(imuFacts, 'Reliable', imuText === 'WORKING' ? 'Yes' : 'No');

    // missing data, last 7 days
    try {
        const q = await api('/quality?days=7');
        const t = q.total;
        const share = (n) => (t ? `${Math.round((n / t) * 100)}%` : '--');
        $('miss-tiles').replaceChildren(
            tile('Readings', String(t), '', `last 7 days, ${SOURCE_NAMES[SOURCE].toLowerCase()}`),
            tile('Good signal', share(q.signal_quality.good), '', `${q.signal_quality.good} readings`),
            tile('Poor or no finger', share(q.signal_quality.poor + q.signal_quality.no_finger), '', `${q.signal_quality.poor} poor, ${q.signal_quality.no_finger} no finger`),
            tile('Heart rate missing', String(q.missing.heart_rate_bpm), '', 'readings without a value'),
            tile('SpO2 missing', String(q.missing.spo2_percent), '', 'readings without a value'),
            tile('Motion missing', String(q.missing.motion), '', 'readings without acceleration'));
        $('miss-error').textContent = '';
    } catch (error) { $('miss-error').textContent = 'Could not load the data quality (server not reachable?).'; }
}

function tile(label, value, unit, sub) {
    const box = el('div', 'tile');
    box.append(el('span', 'label', label), el('div', 'tile-value', value), el('span', 'note', sub || ''));
    return box;
}

document.addEventListener('DOMContentLoaded', () => {
    buildShell('sensors.html', 'Sensors');
    loadSensors();
    setInterval(loadSensors, 3000);
});


// ---- live demo: what the view is made of, and a reset of today ----
async function renderDemo() {
    await loadDemo();
    const live = DEMO.today_source === 'live_hardware';
    $('demo-state').textContent = `Earlier days: ${DEMO.baseline_days ?? '--'} simulated days (pre-recorded baseline). Today: ${live ? 'live sensor' : 'simulator'}, ${DEMO.today_readings ?? '--'} readings so far.`;
}
$('demo-reset').addEventListener('click', async () => {
    if (!window.confirm("Remove today's readings and check-in? The earlier simulated days stay.")) return;
    try {
        const response = await fetch(`${API}/demo/reset-today`, { method: 'POST' });
        const r = await response.json();
        $('demo-msg').textContent = response.ok ? `Removed ${r.removed_readings} readings. Today starts again from zero.` : 'Could not reset.';
    } catch (error) { $('demo-msg').textContent = 'Server not reachable.'; }
    renderDemo();
});
renderDemo();
setInterval(renderDemo, 10000);
