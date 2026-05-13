// ===== CONFIG =====
const API_BASE = window.location.origin;
let currentDate = new Date();
let currentFilter = 'all';
let matchesData = [];
let isDemoMode = false;

// ===== UTILS =====
function formatDate(date) {
    const d = new Date(date);
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = d.getFullYear();
    return `${day}/${month}/${year}`;
}

function formatDateAPI(date) {
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function formatTime(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
}

function getStatusText(status) {
    const statuses = {
        'NS': 'No iniciado',
        '1H': '1ª Parte',
        'HT': 'Descanso',
        '2H': '2ª Parte',
        'ET': 'Prórroga',
        'P': 'Penaltis',
        'FT': 'Finalizado',
        'AET': 'Finalizado (Prórroga)',
        'PEN': 'Finalizado (Penaltis)',
        'PST': 'Aplazado',
        'CANC': 'Cancelado',
        'SUSP': 'Suspendido',
        'INT': 'Interrumpido',
        'TBD': 'Por confirmar'
    };
    return statuses[status] || status;
}

// ===== DOM ELEMENTS =====
const dateDisplay = document.getElementById('current-date');
const datePicker = document.getElementById('date-picker');
const prevDateBtn = document.getElementById('prev-date');
const nextDateBtn = document.getElementById('next-date');
const matchesContainer = document.getElementById('matches-container');
const leagueFilters = document.getElementById('league-filters');
const analysisSection = document.getElementById('analysis-section');
const backBtn = document.getElementById('back-btn-matches');

// ===== DATE HANDLING =====
function updateDateDisplay() {
    dateDisplay.textContent = formatDate(currentDate);
    datePicker.value = formatDateAPI(currentDate);
}

function changeDate(days) {
    currentDate.setDate(currentDate.getDate() + days);
    updateDateDisplay();
    loadMatches();
}

prevDateBtn.addEventListener('click', () => changeDate(-1));
nextDateBtn.addEventListener('click', () => changeDate(1));

dateDisplay.addEventListener('click', () => {
    datePicker.showPicker();
});

datePicker.addEventListener('change', (e) => {
    if (e.target.value) {
        currentDate = new Date(e.target.value + 'T00:00:00');
        updateDateDisplay();
        loadMatches();
    }
});

// ===== FILTER HANDLING =====
leagueFilters.addEventListener('click', (e) => {
    if (e.target.classList.contains('filter-btn')) {
        document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
        e.target.classList.add('active');
        currentFilter = e.target.dataset.filter;
        renderMatches();
    }
});

// ===== LOAD MATCHES =====
async function loadMatches() {
    matchesContainer.innerHTML = '<div class="loading">Cargando partidos...</div>';

    try {
        const dateStr = formatDateAPI(currentDate);
        const response = await fetch(`${API_BASE}/api/matches?date=${dateStr}&filter=${currentFilter}`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        isDemoMode = data.demo || false;

        if (data.errors && data.errors.length > 0) {
            console.warn('API Errors:', data.errors);
        }

        matchesData = data.matches || [];
        renderMatches();

        // Show demo badge if in demo mode
        if (isDemoMode) {
            showDemoBadge();
        } else {
            hideDemoBadge();
        }
    } catch (error) {
        console.error('Error loading matches:', error);
        matchesContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <div class="empty-state-text">Error al cargar los partidos. Intenta recargar.</div>
                <div style="margin-top: 12px; font-size: 12px; color: var(--text-muted);">${error.message}</div>
            </div>
        `;
    }
}

function showDemoBadge() {
    let badge = document.getElementById('demo-badge');
    if (!badge) {
        badge = document.createElement('div');
        badge.id = 'demo-badge';
        badge.style.cssText = `
            background: rgba(245, 158, 11, 0.15);
            border: 1px solid var(--warning);
            color: var(--warning);
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            text-align: center;
            margin-bottom: 12px;
        `;
        badge.textContent = '⚡ Modo Demo - Datos de ejemplo';
        document.getElementById('app').insertBefore(badge, leagueFilters);
    }
}

function hideDemoBadge() {
    const badge = document.getElementById('demo-badge');
    if (badge) badge.remove();
}

// ===== RENDER MATCHES =====
function renderMatches() {
    if (matchesData.length === 0) {
        matchesContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📅</div>
                <div class="empty-state-text">No hay partidos para esta fecha/filtro</div>
            </div>
        `;
        return;
    }

    let filtered = matchesData;
    if (currentFilter !== 'all') {
        filtered = matchesData.filter(m => m.filter === currentFilter);
    }

    if (filtered.length === 0) {
        matchesContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🔍</div>
                <div class="empty-state-text">No hay partidos para este filtro</div>
            </div>
        `;
        return;
    }

    matchesContainer.innerHTML = filtered.map(match => `
        <div class="match-card" data-id="${match.id}">
            <div class="match-league">
                <span class="match-league-flag">🏆</span>
                ${match.league_name}
                ${isDemoMode ? '<span style="margin-left: auto; font-size: 10px; color: var(--warning);">DEMO</span>' : ''}
            </div>
            <div class="match-teams-row">
                <div class="team-info">
                    <img src="${match.homeTeam.crest}" alt="${match.homeTeam.name}" class="team-logo" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>⚽</text></svg>'">
                    <span class="team-name">${match.homeTeam.shortName}</span>
                </div>
                <div class="match-center">
                    <div class="match-time">${formatTime(match.utcDate)}</div>
                    <div class="vs-text">VS</div>
                    <div class="match-status">${getStatusText(match.status)}</div>
                </div>
                <div class="team-info away">
                    <img src="${match.awayTeam.crest}" alt="${match.awayTeam.name}" class="team-logo" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>⚽</text></svg>'">
                    <span class="team-name">${match.awayTeam.shortName}</span>
                </div>
            </div>
        </div>
    `).join('');

    // Add click handlers
    document.querySelectorAll('.match-card').forEach(card => {
        card.addEventListener('click', () => {
            const matchId = card.dataset.id;
            showAnalysis(matchId);
        });
    });
}

// ===== SHOW ANALYSIS =====
async function showAnalysis(matchId) {
    analysisSection.classList.remove('hidden');
    document.getElementById('app').scrollTop = 0;

    // Reset tabs
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.querySelector('[data-tab="summary"]').classList.add('active');
    document.getElementById('tab-summary').classList.add('active');

    try {
        const response = await fetch(`${API_BASE}/api/analyze/${matchId}`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }

        renderAnalysis(data);
    } catch (error) {
        console.error('Error loading analysis:', error);
        alert('Error al cargar el análisis: ' + error.message);
    }
}

function renderAnalysis(data) {
    const info = data.match_info;

    // Header
    document.getElementById('home-logo').src = info.home_logo;
    document.getElementById('home-name').textContent = info.home_team;
    document.getElementById('away-logo').src = info.away_logo;
    document.getElementById('away-name').textContent = info.away_team;
    document.getElementById('match-meta').innerHTML = `
        ${info.league} • ${formatDate(info.date)} ${info.time} • ${info.venue}
    `;

    // Form
    document.getElementById('home-form-name').textContent = info.home_short;
    document.getElementById('away-form-name').textContent = info.away_short;
    document.getElementById('home-form').innerHTML = renderFormBadges(data.home_form);
    document.getElementById('away-form').innerHTML = renderFormBadges(data.away_form);

    // Probabilities
    const probs = data.probabilities;
    setProbBar('prob-over15', 'prob-over15-val', probs.over_1_5, '%');
    setProbBar('prob-over25', 'prob-over25-val', probs.over_2_5, '%');
    setProbBar('prob-over35', 'prob-over35-val', probs.over_3_5, '%');
    setProbBar('prob-btts', 'prob-btts-val', probs.btts, '%');
    setProbBar('prob-xg', 'prob-xg-val', probs.total_expected_goals, '');
    setProbBar('prob-corners', 'prob-corners-val', probs.expected_corners, '');
    setProbBar('prob-cards', 'prob-cards-val', probs.expected_cards, '');

    // Tables
    document.getElementById('table-home').textContent = info.home_short;
    document.getElementById('table-away').textContent = info.away_short;
    document.getElementById('corner-home').textContent = info.home_short;
    document.getElementById('corner-away').textContent = info.away_short;
    document.getElementById('card-home').textContent = info.home_short;
    document.getElementById('card-away').textContent = info.away_short;

    renderGoalsTable(data.home_stats, data.away_stats);
    renderCornersTable(data.home_stats, data.away_stats);
    renderCardsTable(data.home_stats, data.away_stats);
}

function renderFormBadges(form) {
    if (!form || form.length === 0) return '<span style="color: var(--text-muted)">Sin datos</span>';
    return form.map(f => `
        <div class="form-badge ${f.result}" title="${f.result_text} vs ${f.opponent} (${f.team_goals}-${f.opp_goals})">
            ${f.result}
        </div>
    `).join('');
}

function setProbBar(barId, valId, value, suffix) {
    const bar = document.getElementById(barId);
    const val = document.getElementById(valId);
    const maxVal = suffix === '%' ? 100 : (value > 10 ? value * 1.2 : 10);
    const pct = Math.min(100, (value / maxVal) * 100);

    bar.style.setProperty('--width', pct + '%');
    val.textContent = value + suffix;
}

function renderGoalsTable(home, away) {
    const tbody = document.getElementById('goals-table-body');
    tbody.innerHTML = `
        <tr><td>Over 1.5</td><td>${home.over_1_5_pct}%</td><td>${away.over_1_5_pct}%</td><td>${Math.round((home.over_1_5_pct + away.over_1_5_pct)/2)}%</td></tr>
        <tr><td>Over 2.5</td><td>${home.over_2_5_pct}%</td><td>${away.over_2_5_pct}%</td><td>${Math.round((home.over_2_5_pct + away.over_2_5_pct)/2)}%</td></tr>
        <tr><td>Over 3.5</td><td>${home.over_3_5_pct}%</td><td>${away.over_3_5_pct}%</td><td>${Math.round((home.over_3_5_pct + away.over_3_5_pct)/2)}%</td></tr>
        <tr><td>BTTS</td><td>${home.btts_pct}%</td><td>${away.btts_pct}%</td><td>${Math.round((home.btts_pct + away.btts_pct)/2)}%</td></tr>
        <tr><td>Media Goles</td><td>${home.avg_total_goals}</td><td>${away.avg_total_goals}</td><td>${((home.avg_total_goals + away.avg_total_goals)/2).toFixed(2)}</td></tr>
    `;
}

function renderCornersTable(home, away) {
    const tbody1 = document.getElementById('corners-table-body');
    const tbody2 = document.getElementById('corners-total-body');

    tbody1.innerHTML = `
        <tr><td>Over 8.5</td><td>${home.home.over_8_5_corners}%</td><td>${away.away.over_8_5_corners}%</td><td>${Math.round((home.home.over_8_5_corners + away.away.over_8_5_corners)/2)}%</td></tr>
        <tr><td>Over 9.5</td><td>${home.home.over_9_5_corners}%</td><td>${away.away.over_9_5_corners}%</td><td>${Math.round((home.home.over_9_5_corners + away.away.over_9_5_corners)/2)}%</td></tr>
        <tr><td>Over 10.5</td><td>${home.home.over_10_5_corners}%</td><td>${away.away.over_10_5_corners}%</td><td>${Math.round((home.home.over_10_5_corners + away.away.over_10_5_corners)/2)}%</td></tr>
    `;

    tbody2.innerHTML = `
        <tr><td>Media Total</td><td>${home.avg_corners}</td><td>${away.avg_corners}</td><td>${((home.avg_corners + away.avg_corners)).toFixed(1)}</td></tr>
        <tr><td>Local (est.)</td><td>${home.home.avg_corners}</td><td>${away.home.avg_corners}</td><td>-</td></tr>
        <tr><td>Visitante (est.)</td><td>${home.away.avg_corners}</td><td>${away.away.avg_corners}</td><td>-</td></tr>
    `;
}

function renderCardsTable(home, away) {
    const tbody = document.getElementById('cards-table-body');
    tbody.innerHTML = `
        <tr><td>Over 3.5</td><td>${home.home.over_3_5_cards}%</td><td>${away.away.over_3_5_cards}%</td><td>${Math.round((home.home.over_3_5_cards + away.away.over_3_5_cards)/2)}%</td></tr>
        <tr><td>Over 4.5</td><td>${home.home.over_4_5_cards}%</td><td>${away.away.over_4_5_cards}%</td><td>${Math.round((home.home.over_4_5_cards + away.away.over_4_5_cards)/2)}%</td></tr>
        <tr><td>Media Tarjetas</td><td>${home.avg_cards}</td><td>${away.avg_cards}</td><td>${((home.avg_cards + away.avg_cards)).toFixed(1)}</td></tr>
    `;
}

// ===== TABS =====
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

        btn.classList.add('active');
        document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
    });
});

// ===== BACK BUTTON =====
backBtn.addEventListener('click', () => {
    analysisSection.classList.add('hidden');
});

// ===== INIT =====
updateDateDisplay();
loadMatches();

// Refresh every 60 seconds
setInterval(loadMatches, 60000);
