// ============ TELEGRAM WEB APP ============
let tg = window.Telegram?.WebApp;
if (tg) {
    tg.expand();
    tg.ready();
}

// ============ STATE ============
let currentLeagueId = null;
let currentLeagueName = '';
let currentMatches = [];

// ============ DOM ELEMENTS ============
const leagueSection = document.getElementById('league-section');
const matchesSection = document.getElementById('matches-section');
const analysisSection = document.getElementById('analysis-section');
const leaguesGrid = document.getElementById('leagues-grid');
const matchesList = document.getElementById('matches-list');
const matchesTitle = document.getElementById('matches-title');

// ============ EVENT LISTENERS ============
document.querySelectorAll('.league-card').forEach(card => {
    card.addEventListener('click', () => {
        const id = card.dataset.id;
        const name = card.dataset.name;
        loadMatches(id, name);
    });
});

// Tabs
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    });
});

// ============ NAVIGATION ============
function showLeagues() {
    leagueSection.classList.remove('hidden');
    matchesSection.classList.add('hidden');
    analysisSection.classList.add('hidden');
}

function showMatches() {
    leagueSection.classList.add('hidden');
    matchesSection.classList.remove('hidden');
    analysisSection.classList.add('hidden');
}

function showAnalysis() {
    leagueSection.classList.add('hidden');
    matchesSection.classList.add('hidden');
    analysisSection.classList.remove('hidden');
}

// ============ LOAD MATCHES ============
async function loadMatches(leagueId, leagueName) {
    currentLeagueId = leagueId;
    currentLeagueName = leagueName;
    matchesTitle.textContent = leagueName + ' - Partidos de hoy';
    showMatches();
    matchesList.innerHTML = '<div class="loading">Cargando partidos...</div>';

    try {
        const response = await fetch(`/api/matches/${leagueId}`);
        const matches = await response.json();
        currentMatches = matches;
        renderMatches(matches);
    } catch (e) {
        matchesList.innerHTML = '<div class="no-matches">Error cargando partidos</div>';
    }
}

function renderMatches(matches) {
    if (!matches || matches.length === 0) {
        matchesList.innerHTML = '<div class="no-matches">No hay partidos hoy en esta liga</div>';
        return;
    }

    matchesList.innerHTML = matches.map(match => {
        const home = match.homeTeam;
        const away = match.awayTeam;
        const time = match.utcDate ? match.utcDate.substring(11, 16) : '--:--';

        return `
            <div class="match-card" onclick="analyzeMatch(${match.id})">
                <div class="match-card-teams">
                    <div class="match-card-team">
                        <img src="${home.crest || ''}" alt="${home.name}" onerror="this.style.display='none'">
                        <span>${home.shortName || home.name}</span>
                    </div>
                    <div class="match-card-vs">VS</div>
                    <div class="match-card-team away">
                        <img src="${away.crest || ''}" alt="${away.name}" onerror="this.style.display='none'">
                        <span>${away.shortName || away.name}</span>
                    </div>
                </div>
                <div class="match-card-time">${time} | ${match.competition?.name || ''}</div>
            </div>
        `;
    }).join('');
}

// ============ ANALYZE MATCH ============
async function analyzeMatch(matchId) {
    showAnalysis();

    // Reset tabs
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector('[data-tab="summary"]').classList.add('active');
    document.getElementById('tab-summary').classList.add('active');

    try {
        const response = await fetch(`/api/analyze/${matchId}`);
        const data = await response.json();

        if (data.error) {
            alert(data.error);
            showMatches();
            return;
        }

        renderAnalysis(data);
    } catch (e) {
        console.error(e);
        alert('Error analizando partido');
        showMatches();
    }
}

function renderAnalysis(data) {
    const info = data.match_info;
    const probs = data.probabilities;
    const homeStats = data.home_goal_stats;
    const awayStats = data.away_goal_stats;

    // Header
    document.getElementById('home-name').textContent = info.home_team;
    document.getElementById('away-name').textContent = info.away_team;
    document.getElementById('home-logo').src = info.home_logo;
    document.getElementById('away-logo').src = info.away_logo;
    document.getElementById('match-meta').textContent = `${info.date} | ${info.league} | ${info.time}`;

    // Table headers
    document.getElementById('table-home').textContent = info.home_team.substring(0, 12);
    document.getElementById('table-away').textContent = info.away_team.substring(0, 12);
    document.getElementById('corner-home').textContent = info.home_team.substring(0, 12);
    document.getElementById('corner-away').textContent = info.away_team.substring(0, 12);
    document.getElementById('card-home').textContent = info.home_team.substring(0, 12);
    document.getElementById('card-away').textContent = info.away_team.substring(0, 12);
    document.getElementById('home-form-name').textContent = info.home_team.substring(0, 15);
    document.getElementById('away-form-name').textContent = info.away_team.substring(0, 15);

    // Form
    renderForm(data.home_form, 'home-form');
    renderForm(data.away_form, 'away-form');

    // Probabilities
    setProbBar('prob-over15', probs.over_1_5);
    setProbBar('prob-over25', probs.over_2_5);
    setProbBar('prob-btts', probs.btts);
    setProbBar('prob-xg', Math.min(probs.total_expected_goals * 20, 100), probs.total_expected_goals);

    // Goals table
    renderGoalsTable(homeStats, awayStats);

    // Corners table (simulated with available data)
    renderCornersTable(homeStats, awayStats);

    // Cards table (simulated)
    renderCardsTable(homeStats, awayStats);
}

function renderForm(form, elementId) {
    const container = document.getElementById(elementId);
    if (!form || form.length === 0) {
        container.innerHTML = '<span style="color: var(--text-muted)">Sin datos</span>';
        return;
    }
    container.innerHTML = form.map(f => 
        `<div class="badge ${f.result}">${f.result === 'W' ? 'V' : f.result === 'D' ? 'E' : 'D'}</div>`
    ).join('');
}

function setProbBar(id, value, displayValue = null) {
    const bar = document.getElementById(id);
    const val = document.getElementById(id + '-val');
    const pct = Math.min(value, 100);

    bar.style.width = pct + '%';
    bar.className = 'prob-bar';
    if (pct >= 70) bar.classList.add('high');
    else if (pct >= 45) bar.classList.add('medium');
    else bar.classList.add('low');

    val.textContent = displayValue !== null ? displayValue : pct + '%';
}

function renderGoalsTable(home, away) {
    const tbody = document.getElementById('goals-table-body');
    const rows = [
        { label: 'Goles/Partido', home: home.avg_total_goals || 0, away: away.avg_total_goals || 0 },
        { label: 'Over 2.5', home: home.over_2_5_pct || 0, away: away.over_2_5_pct || 0, isPct: true },
        { label: 'Over 1.5', home: home.over_1_5_pct || 0, away: away.over_1_5_pct || 0, isPct: true },
        { label: 'BTTS', home: home.btts_pct || 0, away: away.btts_pct || 0, isPct: true },
    ];

    tbody.innerHTML = rows.map(r => {
        const avg = ((parseFloat(r.home) + parseFloat(r.away)) / 2).toFixed(1);
        const homeVal = r.isPct ? r.home + '%' : r.home;
        const awayVal = r.isPct ? r.away + '%' : r.away;
        const avgVal = r.isPct ? avg + '%' : avg;

        const homeClass = r.home >= 60 ? 'value-high' : r.home >= 40 ? 'value-medium' : 'value-low';
        const awayClass = r.away >= 60 ? 'value-high' : r.away >= 40 ? 'value-medium' : 'value-low';

        return `
            <tr>
                <td>${r.label}</td>
                <td class="${homeClass}">${homeVal}</td>
                <td class="${awayClass}">${awayVal}</td>
                <td>${avgVal}</td>
            </tr>
        `;
    }).join('');
}

function renderCornersTable(home, away) {
    // Simulado basado en posesión/ofensiva (la API gratuita no da corners)
    const tbody = document.getElementById('corners-table-body');
    const tbodyTotal = document.getElementById('corners-total-body');

    const homeCorners = (home.avg_total_goals || 0) * 2.8;
    const awayCorners = (away.avg_total_goals || 0) * 2.8;

    tbody.innerHTML = `
        <tr><td>Corners/Partido</td><td class="value-high">${homeCorners.toFixed(1)}</td><td class="value-high">${awayCorners.toFixed(1)}</td><td>${((homeCorners + awayCorners)/2).toFixed(1)}</td></tr>
        <tr><td>Over 9.5</td><td class="value-medium">${Math.min(homeCorners * 8, 85).toFixed(0)}%</td><td class="value-medium">${Math.min(awayCorners * 8, 85).toFixed(0)}%</td><td>${Math.min((homeCorners + awayCorners) * 4, 80).toFixed(0)}%</td></tr>
        <tr><td>Over 10.5</td><td class="value-low">${Math.min(homeCorners * 6, 70).toFixed(0)}%</td><td class="value-low">${Math.min(awayCorners * 6, 70).toFixed(0)}%</td><td>${Math.min((homeCorners + awayCorners) * 3, 65).toFixed(0)}%</td></tr>
    `;

    tbodyTotal.innerHTML = `
        <tr><td>Over 8.5</td><td class="value-high">${Math.min(homeCorners * 10, 90).toFixed(0)}%</td><td class="value-high">${Math.min(awayCorners * 10, 90).toFixed(0)}%</td><td>${Math.min((homeCorners + awayCorners) * 5, 85).toFixed(0)}%</td></tr>
        <tr><td>Over 9.5</td><td class="value-medium">${Math.min(homeCorners * 8, 80).toFixed(0)}%</td><td class="value-medium">${Math.min(awayCorners * 8, 80).toFixed(0)}%</td><td>${Math.min((homeCorners + awayCorners) * 4, 75).toFixed(0)}%</td></tr>
        <tr><td>Over 10.5</td><td class="value-low">${Math.min(homeCorners * 6, 65).toFixed(0)}%</td><td class="value-low">${Math.min(awayCorners * 6, 65).toFixed(0)}%</td><td>${Math.min((homeCorners + awayCorners) * 3, 60).toFixed(0)}%</td></tr>
        <tr><td>Over 11.5</td><td class="value-low">${Math.min(homeCorners * 4, 50).toFixed(0)}%</td><td class="value-low">${Math.min(awayCorners * 4, 50).toFixed(0)}%</td><td>${Math.min((homeCorners + awayCorners) * 2, 45).toFixed(0)}%</td></tr>
    `;
}

function renderCardsTable(home, away) {
    const tbody = document.getElementById('cards-table-body');
    // Simulado basado en intensidad del partido
    const intensity = ((home.avg_total_goals || 0) + (away.avg_total_goals || 0)) / 2;
    const baseCards = 3.5 + intensity * 0.8;

    tbody.innerHTML = `
        <tr><td>Tarjetas/Partido</td><td class="value-high">${(baseCards * 0.9).toFixed(2)}</td><td class="value-high">${(baseCards * 1.1).toFixed(2)}</td><td>${baseCards.toFixed(2)}</td></tr>
        <tr><td>Over 3.5</td><td class="value-high">${Math.min(baseCards * 18, 88).toFixed(0)}%</td><td class="value-high">${Math.min(baseCards * 20, 90).toFixed(0)}%</td><td>${Math.min(baseCards * 19, 89).toFixed(0)}%</td></tr>
        <tr><td>Over 4.5</td><td class="value-medium">${Math.min(baseCards * 14, 72).toFixed(0)}%</td><td class="value-medium">${Math.min(baseCards * 16, 75).toFixed(0)}%</td><td>${Math.min(baseCards * 15, 73).toFixed(0)}%</td></tr>
        <tr><td>Over 5.5</td><td class="value-low">${Math.min(baseCards * 10, 55).toFixed(0)}%</td><td class="value-low">${Math.min(baseCards * 12, 58).toFixed(0)}%</td><td>${Math.min(baseCards * 11, 56).toFixed(0)}%</td></tr>
    `;
}
