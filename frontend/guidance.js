// Activity page: NASA-based guidance, linked to the data when there are data.
// - Sleep and circadian rhythm: general guidance. Shown as general guidance when rest data are unavailable.
// - Sensorimotor awareness: a simple 30-second steadiness check from the motion sensor. No diagnosis.
// General guidance is labelled as such. Needs core.js and rest.js (loaded before this file).

const SLEEP_GUIDE = [
    ['Consistent sleep schedule', 'Try to maintain consistent sleep and wake times to support your internal body clock.'],
    ['Lighting', 'Reduce unnecessary bright light before your planned sleep period. Use the appropriate habitat lighting settings.'],
    ['Sleeping environment', 'Keep your sleeping area as dark, quiet and comfortable as possible.'],
    ['Physical activity', 'Follow your scheduled exercise routine. Avoid unnecessarily placing demanding exercise immediately before planned sleep.'],
    ['Recovery', 'If you have had insufficient sleep, use an appropriate recovery opportunity when your mission schedule permits.'],
    ['Relaxation', 'Allow time to wind down before sleeping. Consider a simple relaxation routine.'],
    ['Fatigue and alertness', 'When available, use an appropriate attention or vigilance self-assessment to help evaluate alertness.'],
    ['Journal and support', 'Record sleep observations in the daily journal. Report persistent sleep difficulties through established mission channels. Make time for meaningful recreational or personal activities.'],
];

function guideCard(title, text) {
    const box = el('div', 'guide');
    box.append(el('span', 'guide-title', title), el('p', 'note', text));
    return box;
}

function statusBlock(badgeKey, title, what, todo) {
    const box = el('div', 'log-item');
    const top = el('div', 'panel-head');
    top.append(el('h3', '', title), stateBadge(badgeKey));
    box.append(top, el('p', '', what));
    if (todo) box.append(el('p', 'note', `Suggested action: ${todo}`));
    return box;
}

// ---- sleep and circadian rhythm ----
async function loadSleepGuide() {
    $('sleep-grid').replaceChildren(...SLEEP_GUIDE.map(([t, x]) => guideCard(t, x)));
    try {
        const data = await api('/rest?nights=7');
        const last = data.per_night[data.per_night.length - 1];
        $('sleep-lead').textContent = last.status === 'ok'
            ? `Last night's recorded rest: ${last.rest_start} to ${last.rest_end} (${last.duration_h} h), estimated from movement.`
            : 'No rest period could be found for last night (too little motion data).';
    } catch (error) { $('sleep-lead').textContent = 'Sleep data are unavailable.'; }
}

// ---- sensorimotor awareness: a 30-second steadiness check ----
const CHECK_SECONDS = 30;
const CHECK_KEY = 'astra-steadiness-checks';

function savedChecks() {
    try { return JSON.parse(localStorage.getItem(CHECK_KEY) || '[]'); } catch (error) { return []; }
}
function saveCheck(entry) {
    try { localStorage.setItem(CHECK_KEY, JSON.stringify([...savedChecks(), entry].slice(-10))); } catch (error) { /* storage can be blocked */ }
}

function runCheck() {
    const button = $('check-run');
    const out = $('check-out');
    button.disabled = true;
    const startedAt = Date.now();
    const tick = setInterval(() => {
        const left = Math.max(0, CHECK_SECONDS - Math.round((Date.now() - startedAt) / 1000));
        out.textContent = `Keep the device in your hand and hold still... ${left} s`;
    }, 500);
    setTimeout(async () => {
        clearInterval(tick);
        button.disabled = false;
        try {
            const rows = (await api('/measurements?limit=60')).filter((r) => new Date(r.received_at).getTime() >= startedAt);
            const moves = rows.filter((r) => [r.accel_x_g, r.accel_y_g, r.accel_z_g].every((v) => v !== null && v !== undefined))
                .map((r) => Math.abs(Math.hypot(r.accel_x_g, r.accel_y_g, r.accel_z_g) - 1));
            if (moves.length < 5) {
                out.textContent = 'Not enough motion readings during the check. Make sure the device is connected and try again.';
                return;
            }
            const mean = moves.reduce((a, b) => a + b, 0) / moves.length;
            const previous = savedChecks();
            const prevMean = previous.length >= 3 ? previous.reduce((a, c) => a + c.mean, 0) / previous.length : null;
            saveCheck({ at: new Date().toISOString(), mean });
            let text = `Movement during the check: ${mean.toFixed(3)} g (${moves.length} readings, ${SOURCE_NAMES[SOURCE].toLowerCase()} data).`;
            if (prevMean === null) text += ' Do the check a few more times to build your own reference.';
            else if (mean > Math.max(prevMean * 2, 0.03)) text += ` This is higher than your earlier checks (about ${prevMean.toFixed(3)} g). Repeat the check. Follow the prescribed exercise and sensorimotor training schedule, and report persistent dizziness or coordination difficulties through mission medical procedures.`;
            else text += ` This is similar to your earlier checks (about ${prevMean.toFixed(3)} g).`;
            out.textContent = text;
        } catch (error) { out.textContent = 'Could not read the measurements (server not reachable?).'; }
    }, CHECK_SECONDS * 1000);
}

document.addEventListener('DOMContentLoaded', () => {
    loadSleepGuide();
    $('check-run').addEventListener('click', runCheck);
});
