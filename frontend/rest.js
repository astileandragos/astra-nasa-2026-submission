// Rest panel of the Activity page: rest period of each night, from the movement of the ICM-20948.
// Needs core.js and imu.js. A missing night is shown empty, never as 0 hours.

const NIGHT_FROM_MIN = 18 * 60;      // the night axis starts at 18:00 (same as the API)
const NIGHT_CELLS = 36;              // 18:00 to 12:00 in half hours
const STAGE_COLORS = { deep: '#1F2A6B', light: '#6F8FD6', rem: '#B05FC6' };     // used only if a source provides sleep stages
const STAGE_NAMES = { deep: 'Deep sleep', light: 'Light sleep', rem: 'REM' };

function axisClock(minutes) {
    const total = (NIGHT_FROM_MIN + minutes) % 1440;
    return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

const dayBefore = (date) => {
    const d = new Date(`${date}T12:00:00`);
    d.setDate(d.getDate() - 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

// One row per night: the movement of every half hour (colored by intensity, from the ICM-20948) with the estimated rest
// period marked underneath. Sleep stages (deep, light, REM) are NOT inferred from movement: a night shows them only if a
// source delivers them (night.sleep_stages), which the current hardware does not.
async function renderRestStrip(nights) {
    const box = $('rest-strip');
    const rows = [];
    const header = el('div', 'strip-row strip-head');
    header.append(el('span', 'strip-label', ''));
    const scale = el('div', 'strip-cells strip-scale');
    for (let i = 0; i < NIGHT_CELLS; i += 1) scale.append(el('span', '', i % 6 === 0 ? axisClock(i * 30) : ''));
    header.append(scale);
    rows.push(header);
    let anyStages = false;
    for (const n of nights) {
        const previous = await imuWindows(dayBefore(n.date), 30);
        const same = await imuWindows(n.date, 30);
        const cells = el('div', 'strip-cells');
        const restFrom = n.status === 'ok' ? n.start_minutes : null;
        const restTo = n.status === 'ok' ? n.start_minutes + Math.round(n.duration_h * 60) : null;
        for (let i = 0; i < NIGHT_CELLS; i += 1) {
            const minute = NIGHT_FROM_MIN + i * 30;
            const w = (minute < 1440 ? previous : same).find((x) => minutesOf(x) === minute % 1440);
            const level = w ? intensityOf(w.movement_index) : null;
            const cell = el('span', 'strip-cell');
            cell.style.background = INTENSITY_COLORS[level || 'none'];
            if (restFrom !== null && i * 30 >= restFrom && i * 30 < restTo) cell.classList.add('in-rest');
            cell.title = `${axisClock(i * 30)} ${level ? INTENSITY_NAMES[level] : 'no data'}`;
            cells.append(cell);
        }
        const row = el('div', 'strip-row');
        row.append(el('span', 'strip-label', shortDate(n.date)), cells);
        rows.push(row);
        if (Array.isArray(n.sleep_stages) && n.sleep_stages.length) {
            anyStages = true;
            const stages = el('div', 'strip-cells strip-stages');
            n.sleep_stages.forEach((seg) => {
                const part = el('span', 'strip-cell');
                part.style.background = STAGE_COLORS[seg.stage] || INTENSITY_COLORS.none;
                part.style.flex = String(seg.minutes);
                part.title = `${STAGE_NAMES[seg.stage] || seg.stage} ${seg.minutes} min`;
                stages.append(part);
            });
            const stageRow = el('div', 'strip-row');
            stageRow.append(el('span', 'strip-label', 'Stages'), stages);
            rows.push(stageRow);
        }
    }
    box.replaceChildren(...rows);
    const legend = $('rest-legend');
    intensityLegend(legend, false);
    const rest = el('span', 'legend-item');
    const sw = el('span', 'swatch');
    sw.style.background = '#fff';
    sw.style.borderBottom = '4px solid #0E7C86';
    rest.append(sw, document.createTextNode('Estimated rest period'));
    legend.append(rest);
    if (anyStages) {
        Object.keys(STAGE_NAMES).forEach((k) => {
            const item = el('span', 'legend-item');
            const swatch = el('span', 'swatch');
            swatch.style.background = STAGE_COLORS[k];
            item.append(swatch, document.createTextNode(STAGE_NAMES[k]));
            legend.append(item);
        });
    }
    $('rest-stages').textContent = anyStages ? 'Sleep stages come from a separate source.'
        : 'Deep sleep, light sleep and REM are not shown: the motion sensor cannot measure sleep stages. They appear here only if a compatible source, such as a smartwatch, provides them.';
}

function renderRestTable(nights) {
    const body = $('rest-rows');
    body.replaceChildren();
    nights.slice().reverse().forEach((n) => {
        const ok = n.status === 'ok';
        const hr = ok && n.resting_heart_rate ? `${n.resting_heart_rate.median} bpm` : '--';
        const row = el('tr');
        row.append(el('td', '', shortDate(n.date)), el('td', '', ok ? n.rest_start : '--'), el('td', '', ok ? n.rest_end : '--'),
            el('td', '', ok ? `${n.duration_h} h` : '--'), el('td', '', ok ? String(n.wake_ups) : '--'), el('td', '', hr));
        if (!ok) row.title = n.reason;
        body.append(row);
    });
}

function renderRestSummary(data) {
    const last = data.per_night[data.per_night.length - 1];
    const facts = $('rest-facts');
    facts.replaceChildren();
    if (last.status === 'ok') {
        $('rest-summary').textContent = `Last night you rested from ${last.rest_start} to ${last.rest_end} (${last.duration_h} h).`;
        const hr = last.resting_heart_rate ? `${last.resting_heart_rate.median} bpm (median of ${last.resting_heart_rate.n} good readings)` : '--';
        [['Wake-ups', String(last.wake_ups)], ['Resting heart rate', hr], ['Night covered by data', `${Math.round(last.coverage * 100)}%`]]
            .forEach(([term, value]) => facts.append(el('dt', '', term), el('dd', '', value)));
    } else {
        $('rest-summary').textContent = 'No rest period found for last night.';
        facts.append(el('dt', '', 'Why'), el('dd', '', last.reason));
    }
    const u = data.usual;
    $('rest-usual').textContent = u
        ? `Your usual rest starts around ${u.start_median} and ends around ${u.end_median}. Over ${u.nights_used} earlier nights the start varied by about ${Math.round(u.start_spread_min)} min (standard deviation; earliest to latest: ${u.start_range_min} min).`
        : 'Your usual rest times appear after 3 earlier nights with enough data.';
    $('rest-limits').textContent = `${data.limits} How it is found: ${data.method}.`;
}

async function loadRest() {
    $('rest-chip').replaceChildren(chip(SOURCE));
    try {
        const data = await api('/rest?nights=7');
        renderRestSummary(data);
        renderRestStrip(data.per_night);
        renderRestTable(data.per_night);
        $('rest-error').textContent = '';
    } catch (error) {
        $('rest-error').textContent = 'Could not load rest (server not reachable?).';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadRest();
    setInterval(loadRest, 30000);
});
