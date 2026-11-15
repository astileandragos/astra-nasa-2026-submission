// Journal page: suggestions from the latest self-reported check-in, and quick environment notes.
// Self-reported only. These are not psychological or medical diagnoses. Needs core.js (and journal.js on the same page).

const ENV_NOTES = ['Uncomfortable temperature', 'Noise disturbance', 'Poor sleeping conditions', 'Environmental discomfort'];

function wellbeingSuggestions(e) {
    const out = [];
    if ((e.mood !== null && e.mood <= 2) || (e.energy !== null && e.energy <= 2)) {
        out.push(['LOW MOTIVATION OR MOOD', 'You reported a low mood or low energy.', 'Consider scheduling a meaningful recreational or personal activity.']);
    }
    if (e.mood !== null && e.mood <= 2) {
        out.push(['ISOLATION', 'A low mood can be more difficult in a small, isolated space.', 'Use available opportunities to communicate with your crew and support network.']);
    }
    if (e.fatigue !== null && e.fatigue >= 4) {
        out.push(['FATIGUE', 'You reported high fatigue.', 'Review your workload and use an appropriate recovery opportunity when mission activities allow.']);
    }
    if (e.stress !== null && e.stress >= 4) {
        out.push(['STRESS', 'You reported high stress.', 'Allow time to wind down and consider a simple relaxation routine. Talk to your crew or support network if it continues.']);
    }
    return out;
}

async function loadWellbeing() {
    const box = $('wb-list');
    try {
        const data = await api('/journal?limit=1', false);
        if (!data.items.length) {
            $('wb-lead').textContent = 'No check-in yet. Fill in the daily check-in and suggestions appear here.';
            box.replaceChildren();
            return;
        }
        const entry = data.items[0];
        const list = wellbeingSuggestions(entry);
        $('wb-lead').textContent = list.length
            ? `Based on your check-in for ${entry.date} (${entry.source === 'simulated' ? 'SIMULATED demo entry' : 'self-reported'}).`
            : `Your check-in for ${entry.date} does not point to anything in particular. Keep following your planned schedule.`;
        box.replaceChildren(...list.map(([title, what, todo]) => {
            const card = el('div', 'guide');
            card.append(el('span', 'guide-title', title), el('p', '', what), el('p', 'note', `Suggested action: ${todo}`));
            return card;
        }));
    } catch (error) {
        $('wb-lead').textContent = 'Could not load the latest check-in (server not reachable?).';
    }
}

function setupEnvNotes() {
    const row = $('env-notes');
    ENV_NOTES.forEach((text) => {
        const button = el('button', 'button button-quiet', text);
        button.type = 'button';
        button.addEventListener('click', () => {
            const note = $('j-note');
            if (!note.value.includes(text)) note.value = (note.value ? `${note.value.trim()}. ` : '') + text;
            note.focus();
        });
        row.append(button);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    setupEnvNotes();
    loadWellbeing();
    $('journal-form').addEventListener('submit', () => setTimeout(loadWellbeing, 800));
});
