// ============ TELEGRAM WEB APP ============
let tg = window.Telegram?.WebApp;
if (tg) {
    tg.expand();
    tg.ready();
    tg.setHeaderColor('#0a0e17');
    tg.setBackgroundColor('#0a0e17');
}

// ============ STATE ============
let currentDate = new Date();
let currentFilter = 'all';
let allMatches = [];

// ============ DOM ELEMENTS ============
const matchesContainer = document.getElementById('matches-container');
const analysisSection = document.getElementById('analysis-section');
const dateDisplay = document.getElementById('current-date');
const datePicker = document.getElementById('date-picker');

// ============ DATE HANDLING ============
function formatDate(date) {
    const d = date.getDate().toString().padStart(2, '0');
    const m = (date.getMonth() + 1).toString().padStart(2, '0');
    const y = date.getFullYear();
    return `${d}/${m}/${y}`;
}

function formatDateISO(date) {
    return date.toISOString().split('T')[0];
}

function updateDateDisplay() {
    dateDisplay.textContent = formatDate(currentDate);
    datePicker.value = formatDateISO(currentDate);
}

// Navegacion de fecha
document.getElementById('prev-date').addEventListener('click', () => {
    currentDate.setDate(currentDate.getDate() - 1);
    updateDateDisplay();
    loadMatches();
});

document.getElementById('next-date').addEventListener('click', () => {
    currentDate.setDate(currentDate.getDate() + 1);
    updateDateDisplay();
    loadMatches();
});

// Date picker
dateDisplay.addEventListener('click', () => {
    datePicker.showPicker();
});

datePicker.addEventListener('change', (e) => {
    currentDate = new Date(e.target.value);
    updateDateDisplay();
    loadMatches();
});

// ============ FILTERS ============
document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.filter;
        renderMatches();
    });
});

// ============ LOAD MATCHES ============
async function loadMatches() {
    const dateStr = formatDateISO(currentDate);
    matchesContainer.innerHTML = '<div class="loading">Cargando partidos...</div>';
    
    try {
        const response = await fetch(`/api/matches?date=${dateStr}`);
        allMatches = await response.json();
        renderMatches();
    } catch (e) {
        console.error(e);
        matchesContainer.innerHTML = '<div class="no-matches">Error cargando partidos</div>';
    }
}

function renderMatches() {
    let matches = allMatches;
    
    // Filtrar por pais/liga
    if (currentFilter !== 'all') {
        matches = matches.filter(m => m.country === currentFilter || m.league_name?.includes(currentFilter));
    }
    
    if (!matches || matches.length === 0) {
        matchesContainer.innerHTML = '<div class="no-matches">No hay partidos para esta fecha/filtro</div>';
        return;
    }
    
    matchesContainer.innerHTML = matches.map(match => {
        const home = match.homeTeam;
        const away = match.awayTeam;
        const time = match.utcDate ? match.utcDate.substring(11, 16) : '--:--';
        const leagueName = match.league_name || match.competition?.name || '';
        
        return `
            <div class="match-card-main" onclick="analyzeMatch(${match.id})">
                <div class="match-time">${time}</div>
                <div class="match-teams-row">
                    <div class="match-team-row">
                        <img src="${home.crest || ''}" alt="${home.name}" onerror="this.style.display='none'">
                        <span>${home.shortName || home.name}</span>
                    </div>
                    <div class="match-team-row">
                        <img src="${away.crest || ''}" alt="${away.name}" onerror="this.style.display='none'">
                        <span>${away.shortName || away.name}</span>
                    </div>
                </div>
                <div class="match-league-tag">${leagueName}</div>
            </div>
        `;
    }).join('');
}

// ============ NAVIGATION ============
function showMatches() {
    matchesContainer.parentElement.classList.remove('hidden');
    document.querySelector('.date-selector').classList.remove('hidden');
    document.querySelector('.league-filters').classList.remove('hidden');
    document.querySelector('.app-header').classList.remove('hidden');
    analysisSection.classList.add('hidden');
    window.scrollTo(0, 0);
}

function showAnalysis() {
    matchesContainer.parentElement.classList.add('hidden');
    document.querySelector('.date-selector').classList.add('hidden');
    document.querySelector('.league-filters').classList.add('hidden');
    document.querySelector('.app-header').classList.add('hidden');
    analysisSection.classList.remove('hidden');
    window.scrollTo(0, 0);
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
    const homeStats = data.home_stats;
    const awayStats = data.away_stats;
    
    // Header
    document.getElementById('home-name').textContent = info.home_team;
    document.getElementById('away-name').textContent = info.away_team;
    document.getElementById('home-logo').src = info.home_logo || 'https://via.placeholder.com/56?text=?';
    document.getElementById('away-logo').src = info.away_logo || 'https://via.placeholder.com/56?text=?';
    document.getElementById('match-meta').textContent = `${info.date} | ${info.league} | ${info.time}`;
    
    // Table headers
    document.getElementById('table-home').textContent = info.home_short.substring(0, 12);
    document.getElementById('table-away').textContent = info.away_short.substring(0, 12);
    document.getElementById('corner-home').textContent = info.home_short.substring(0, 12);
    document.getElementById('corner-away').textContent = info.away_short.substring(0, 12);
    document.getElementById('card-home').textContent = info.home_short.substring(0, 12);
    document.getElementById('card-away').textContent = info.away_short.substring(0, 12);
    document.getElementById('home-form-name').textContent = info.home_team.substring(0, 15);
    document.getElementById('away-form-name').textContent = info.away_team.substring(0, 15);
    
    // Form
    renderForm(data.home_form, 'home-form');
    renderForm(data.away_form, 'away-form');
    
    // Probabilidades con animacion
    setTimeout(() => {
        setProbBar('prob-over15', probs.over_1_5);
        setProbBar('prob-over25', probs.over_2_5);
        setProbBar('prob-over35', probs.over_3_5);
        setProbBar('prob-btts', probs.btts);
        setProbBar('prob-xg', Math.min(probs.total_expected_goals * 15, 100), probs.total_expected_goals);
        setProbBar('prob-corners', Math.min(probs.expected_corners * 5, 100), probs.expected_corners);
        setProbBar('prob-cards', Math.min(probs.expected_cards * 12, 100), probs.expected_cards);
    }, 100);
    
    // Goals table
    renderGoalsTable(homeStats, awayStats);
    
    // Corners table
    renderCornersTable(homeStats, awayStats);
    
    // Cards table
    renderCardsTable(homeStats, awayStats);
}

function renderForm(form, elementId) {
    const container = document.getElementById(elementId);
    if (!form || form.length === 0) {
        container.innerHTML = '<span style="color: var(--text-muted); font-size: 12px;">Sin datos</span>';
        return;
    }
    container.innerHTML = form.map(f => 
        `<div class="badge ${f.result}" title="${f.result_text}: ${f.team_goals}-${f.opp_goals} vs ${f.opponent}">${f.result === 'W' ? 'V' : f.result === 'D' ? 'E' : 'D'}</div>`
    ).join('');
}

function setProbBar(id, value, displayValue = null) {
    const bar = document.getElementById(id);
    const val = document.getElementById(id + '-val');
    const pct = Math.min(value, 100);
    
    bar.style.width = pct + '%';
    bar.className = 'prob-bar';
    if (pct < 45) bar.classList.add('low');
    else if (pct < 70) bar.classList.add('medium');
    
    val.textContent = displayValue !== null ? displayValue : pct + '%';
}

function renderGoalsTable(home, away) {
    const tbody = document.getElementById('goals-table-body');
    const rows = [
        { label: 'Goles/Partido', home: home.avg_total_goals || 0, away: away.avg_total_goals || 0 },
        { label: 'Over 1.5', home: home.over_1_5_pct || 0, away: away.over_1_5_pct || 0, isPct: true },
        { label: 'Over 2.5', home: home.over_2_5_pct || 0, away: away.over_2_5_pct || 0, isPct: true },
        { label: 'Over 3.5', home: home.over_3_5_pct || 0, away: away.over_3_5_pct || 0, isPct: true },
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
    const tbody = document.getElementById('corners-table-body');
    const tbodyTotal = document.getElementById('corners-total-body');
    
    const homeCorners = home.avg_corners || 0;
    const awayCorners = away.avg_corners || 0;
    
    tbody.innerHTML = `
        <tr><td>Corners/Partido</td><td class="value-high">${homeCorners.toFixed(1)}</td><td class="value-high">${awayCorners.toFixed(1)}</td><td>${((homeCorners + awayCorners)/2).toFixed(1)}</td></tr>
        <tr><td>Over 8.5</td><td class="value-medium">${home.over_8_5_corners || 0}%</td><td class="value-medium">${away.over_8_5_corners || 0}%</td><td>${Math.round((home.over_8_5_corners + away.over_8_5_corners)/2)}%</td></tr>
        <tr><td>Over 9.5</td><td class="value-low">${home.over_9_5_corners || 0}%</td><td class="value-low">${away.over_9_5_corners || 0}%</td><td>${Math.round((home.over_9_5_corners + away.over_9_5_corners)/2)}%</td></tr>
        <tr><td>Over 10.5</td><td class="value-low">${home.over_10_5_corners || 0}%</td><td class="value-low">${away.over_10_5_corners || 0}%</td><td>${Math.round((home.over_10_5_corners + away.over_10_5_corners)/2)}%</td></tr>
    `;
    
    tbodyTotal.innerHTML = `
        <tr><td>Over 8.5</td><td class="value-high">${home.over_8_5_corners || 0}%</td><td class="value-high">${away.over_8_5_corners || 0}%</td><td>${Math.round((home.over_8_5_corners + away.over_8_5_corners)/2)}%</td></tr>
        <tr><td>Over 9.5</td><td class="value-medium">${home.over_9_5_corners || 0}%</td><td class="value-medium">${away.over_9_5_corners || 0}%</td><td>${Math.round((home.over_9_5_corners + away.over_9_5_corners)/2)}%</td></tr>
        <tr><td>Over 10.5</td><td class="value-medium">${home.over_10_5_corners || 0}%</td><td class="value-medium">${away.over_10_5_corners || 0}%</td><td>${Math.round((home.over_10_5_corners + away.over_10_5_corners)/2)}%</td></tr>
        <tr><td>Over 11.5</td><td class="value-low">${Math.max(0, (home.over_10_5_corners || 0) - 15)}%</td><td class="value-low">${Math.max(0, (away.over_10_5_corners || 0) - 15)}%</td><td>${Math.max(0, Math.round((home.over_10_5_corners + away.over_10_5_corners)/2) - 15)}%</td></tr>
    `;
}

function renderCardsTable(home, away) {
    const tbody = document.getElementById('cards-table-body');
    
    tbody.innerHTML = `
        <tr><td>Tarjetas/Partido</td><td class="value-high">${(home.avg_cards || 0).toFixed(2)}</td><td class="value-high">${(away.avg_cards || 0).toFixed(2)}</td><td>${((home.avg_cards + away.avg_cards)/2).toFixed(2)}</td></tr>
        <tr><td>Over 3.5</td><td class="value-high">${home.over_3_5_cards || 0}%</td><td class="value-high">${away.over_3_5_cards || 0}%</td><td>${Math.round((home.over_3_5_cards + away.over_3_5_cards)/2)}%</td></tr>
        <tr><td>Over 4.5</td><td class="value-medium">${home.over_4_5_cards || 0}%</td><td class="value-medium">${away.over_4_5_cards || 0}%</td><td>${Math.round((home.over_4_5_cards + away.over_4_5_cards)/2)}%</td></tr>
        <tr><td>Over 5.5</td><td class="value-low">${Math.max(0, (home.over_4_5_cards || 0) - 20)}%</td><td class="value-low">${Math.max(0, (away.over_4_5_cards || 0) - 20)}%</td><td>${Math.max(0, Math.round((home.over_4_5_cards + away.over_4_5_cards)/2) - 20)}%</td></tr>
    `;
}

// ============ INIT ============
updateDateDisplay();
loadMatches();
