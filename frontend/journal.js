// Journal page: the daily check-in form and the last 7 entries. Needs core.js.
// A skipped question is sent as null (never 0). At least one answer is required.

const SCALES = ['mood', 'energy', 'stress', 'fatigue'];

function buildScales() {
    SCALES.forEach((name) => {
        const host = $(`scale-${name}`);
        for (let n = 1; n <= 5; n += 1) {
            const input = el('input');
            input.type = 'radio';
            input.name = name;
            input.value = String(n);
            input.id = `${name}-${n}`;
            const label = el('label', '', String(n));
            label.htmlFor = input.id;
            host.append(input, label);
        }
    });
}

function setForm(entry) {
    $('j-note').value = entry && entry.note ? entry.note : '';
    SCALES.forEach((name) => {
        document.querySelectorAll(`input[name="${name}"]`).forEach((r) => {
            r.checked = Boolean(entry) && entry[name] !== null && String(entry[name]) === r.value;
        });
    });
}

async function loadDay() {
    const date = $('j-date').value;
    if (!date) return;
    try {
        const response = await fetch(`${API}/journal?date=${date}`);
        setForm(response.ok ? await response.json() : null);
    } catch (error) { /* keep what the user typed */ }
}

function payload() {
    const data = { date: $('j-date').value };
    SCALES.forEach((name) => {
        const checked = document.querySelector(`input[name="${name}"]:checked`);
        data[name] = checked ? Number(checked.value) : null;
    });
    const note = $('j-note').value.trim();
    data.note = note === '' ? null : note;
    return data;
}

function say(text, level) {
    const m = $('j-message');
    m.textContent = text;
    m.className = `message ${level ? `message-${level}` : ''}`;
}

async function save(event) {
    event.preventDefault();
    const data = payload();
    if (!data.date) { say('Choose the day first.', 'error'); return; }
    if (SCALES.map((s) => data[s]).every((v) => v === null)) {
        say('Answer at least one question.', 'error');
        return;
    }
    try {
        const response = await fetch(`${API}/journal`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        const body = await response.json();
        if (response.ok) {
            say(`Saved for ${body.date}.`, 'ok');
            loadList();
        } else {
            say(body.message || `The server answered ${response.status}.`, 'error');
        }
    } catch (error) {
        say('Could not reach the server. Nothing was saved.', 'error');
    }
}

async function loadList() {
    const body = $('j-rows');
    try {
        const data = await api('/journal?limit=7', false);
        body.replaceChildren();
        $('j-empty').textContent = data.count ? '' : 'No check-ins saved yet.';
        const today = localToday();
        data.items.forEach((e) => {
            const row = el('tr', e.date === today ? 'today' : '');
            [e.date, show(e.mood), show(e.energy), show(e.stress), show(e.fatigue)]
                .forEach((v) => row.append(el('td', '', v)));
            const cell = el('td');
            cell.append(chip(e.source));
            row.append(cell);
            body.append(row);
        });
        $('j-error').textContent = '';
    } catch (error) {
        $('j-error').textContent = 'Could not load the check-ins (server not reachable?).';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    buildShell('journal.html', 'Journal');
    buildScales();
    const date = $('j-date');
    date.value = localToday();
    date.max = localToday();
    date.addEventListener('change', loadDay);
    $('journal-form').addEventListener('submit', save);
    loadDay();
    loadList();
});
