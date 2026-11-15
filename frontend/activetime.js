// Timeline: average active time per day (summary tile) and the active time of each day (chart, log, selected day).
// Calculated from the ICM-20948 readings with the shared rules of imu.js: 5-minute blocks with movement above the
// stillness limit (0.05 g) count as active time. Only days with at least 80% wear time are used (GET /api/wear); a day
// with gaps is left out, never counted as 0. Needs core.js and imu.js.

const activeDays = {};              // date -> active minutes, kept for finished days
let activeSummary = null;           // { minutes, used, total } or { minutes: null, used: 0, total }
const activeText = (minutes) => hm(minutes);

function activeTile() {
    const box = el('div', 'tile');
    box.id = 'tile-active';
    box.append(el('span', 'label', 'Average active time per day'));
    const line = el('div', 'tile-value');
    const value = el('span', '', '--');
    line.append(value);
    const note = el('span', 'note', 'Calculating...');
    box.append(line, note);
    paintActive(value, note);
    return box;
}

function paintActive(value, note) {
    if (!activeSummary) return;
    if (activeSummary.minutes === null) {
        value.textContent = '--';
        note.textContent = `Not enough data: no day has enough readings (wear time of 80% or more). ${activeSummary.total} days checked.`;
        return;
    }
    value.textContent = activeText(activeSummary.minutes);
    note.textContent = `Light, moderate and high movement, averaged over ${activeSummary.used} of ${activeSummary.total} days with enough data.`;
}

async function activeMinutesOf(date) {
    const windows = await imuWindows(date, IMU.BLOCK_MIN);
    return summarizeDay(windows, IMU.BLOCK_MIN, date === localToday() ? nowMinutes() + IMU.BLOCK_MIN : 1440).active;
}

async function loadActiveTime(dates) {
    let enough = [];
    try {
        const wear = await api(`/wear?days=${dates.length}`);
        enough = wear.per_day.filter((d) => d.enough && dates.includes(d.date)).map((d) => d.date);
        for (const date of enough) activeDays[date] = await activeMinutesOf(date);
        activeSummary = enough.length
            ? { minutes: enough.reduce((s, d) => s + activeDays[d], 0) / enough.length, used: enough.length, total: dates.length }
            : { minutes: null, used: 0, total: dates.length };
    } catch (error) {
        activeSummary = { minutes: null, used: 0, total: dates.length };
        enough = [];
    }
    const box = $('tile-active');
    if (box) paintActive(box.querySelector('.tile-value span'), box.querySelector('.note'));
    // per-day values for the chart, the log and the selected day (a day without enough data stays empty)
    days.forEach((d) => { d.active = enough.includes(d.date) ? activeDays[d.date] : null; });
    if (typeof renderMvChart === 'function') { renderMvChart(); renderLog(); const cur = days.find((d) => d.date === selectedDate); if (cur) dayDetail(cur); }
}
