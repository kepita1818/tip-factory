// ============ STATE ============
let currentDate = new Date();
let currentFilter = 'all';
let allMatches = [];
let liveRefreshInterval = null;

// ============ DOM ELEMENTS ============
const matchesContainer = document.getElementById('matches-container');
const analysisSection = document.getElementById('analysis-section');
const dateDisplay = document.getElementById('current-date');
const datePicker = document.getElementById('date-picker');
const liveIndicator = document.getElementById('live-indicator');

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

document.getElementById('prev-date').addEventListener('click', () => {
    currentDate.setDate(currentDate.getDate() - 1);
    updateDateDisplay();
    loadMatches();
    stopLiveRefresh();
});

document.getElementById('next-date').addEventListener('click', () => {
    currentDate.setDate(currentDate.getDate() + 1);
    updateDateDisplay();
    loadMatches();
    stopLiveRefresh();
});

dateDisplay.addEventListener('click', () => datePicker.showPicker());
datePicker.addEventListener('change', (e) => {
    currentDate = new Date(e.target.value);
    updateDateDisplay();
    loadMatches();
    stopLiveRefresh();
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
    const isToday = dateStr === new Date().toISOString().split('T')[0];
    
    matchesContainer.innerHTML = '<div class="loading">Cargando partidos...</div>';
    
    try {
        const response = await fetch(`/api/matches?date=${dateStr}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        allMatches = await response.json();
        
        if (!Array.isArray(allMatches)) {
            throw new Error('Respuesta inválida del servidor');
        }
        
        if (allMatches.length === 0) {
            matchesContainer.innerHTML = `
                <div class="no-matches">
                    No hay partidos para ${formatDate(currentDate)}<br>
                    <small>Las ligas europeas han terminado la temporada.<br>
                    Prueba con fechas de junio-julio (finales de copas)<br>
                    o agosto (nueva temporada).</small>
                </div>`;
            return;
        }
        
        renderMatches();
        
        if (isToday && !liveRefreshInterval) {
            liveIndicator.classList.add('active');
            startLiveRefresh();
        }
        
    } catch (e) {
        console.error('Error:', e);
        matchesContainer.innerHTML = `<div class="no-matches">Error: ${e.message}<br><small>Intenta recargar la página</small></div>`;
    }
}

function renderMatches() {
    let matches = allMatches;
    
    if (currentFilter !== 'all') {
        matches = matches.filter(m => 
            m.country === currentFilter || 
            m.league_name?.includes(currentFilter)
        );
    }
    
    if (!matches.length) {
        matchesContainer.innerHTML = '<div class="no-matches">No hay partidos para este filtro</div>';
        return;
    }
    
    matchesContainer.innerHTML = matches.map(match => {
        const home = match.homeTeam;
        const away = match.awayTeam;
        const time = match.utcDate ? match.utcDate.substring(11, 16) : '--:--';
        const isLive = match.status === 'inprogress' || match.status === '1H' || match.status === '2H' || match.status === 'HT';
        const scoreText = (match.homeScore !== null && match.awayScore !== null) 
            ? `${match.homeScore} - ${match.awayScore}` 
            : '';
        
        return `
            <div class="match-card-main ${isLive ? 'live' : ''}" data-match-id="${match.id}">
                <div class="match-time">
                    ${isLive ? `🔴 ${match.minute || ''}'` : time}
                    ${scoreText ? `<span class="match-score-live">${scoreText}</span>` : ''}
                </div>
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
                <div class="match-league-tag">${match.league_name || ''}</div>
            </div>
        `;
    }).join('');
    
    document.querySelectorAll('.match-card-main').forEach(card => {
        card.addEventListener('click', () => analyzeMatch(card.dataset.matchId));
    });
}

// ============ LIVE REFRESH ============
function startLiveRefresh() {
    liveRefreshInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/live');
            if (!response.ok) return;
            
            const liveMatches = await response.json();
            if (!Array.isArray(liveMatches)) return;
            
            liveMatches.forEach(live => {
                const idx = allMatches.findIndex(m => m.id === live.id);
                if (idx !== -1) {
                    allMatches[idx] = { ...allMatches[idx], ...live };
                }
            });
            
            renderMatches();
        } catch (e) {
            console.error('Live refresh error:', e);
        }
    }, 30000);
}

function stopLiveRefresh() {
    if (liveRefreshInterval) {
        clearInterval(liveRefreshInterval);
        liveRefreshInterval = null;
    }
    liveIndicator.classList.remove('active');
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

document.getElementById('back-btn-matches').addEventListener('click', showMatches);

// ============ TABS ============
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
    });
});

// ============ ANALYZE MATCH ============
async function analyzeMatch(matchId) {
    showAnalysis();
    
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector('[data-tab="summary"]').classList.add('active');
    document.getElementById('tab-summary').classList.add('active');
    
    try {
        const response = await fetch(`/api/analyze/${matchId}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        if (data.error) {
            alert(data.error);
            showMatches();
            return;
        }
        
        renderAnalysis(data);
    } catch (e) {
        console.error('Error:', e);
        alert('Error analizando partido');
        showMatches();
    }
}

function renderAnalysis(data) {
    const info = data.match_info;
    const probs = data.probabilities;
    const homeStats = data.home_stats;
    const awayStats = data.away_stats;
    
    document.getElementById('home-name').textContent = info.home_team;
    document.getElementById('away-name').textContent = info.away_team;
    document.getElementById('home-logo').src = info.home_logo;
    document.getElementById('away-logo').src = info.away_logo;
    
    const scoreDisplay = document.getElementById('score-display');
    if (info.home_score !== null && info.away_score !== null) {
        scoreDisplay.textContent = `${info.home_score} - ${info.away_score}`;
    } else {
        scoreDisplay.textContent = 'VS';
    }
    
    document.getElementById('match-meta').textContent = `${info.date} | ${info.league} | ${info.time}`;
    
    const liveStatus = document.getElementById('live-status');
    if (info.minute > 0) {
        liveStatus.textContent = `🔴 EN VIVO ${info.minute}'`;
        liveStatus.classList.add('active');
    } else {
        liveStatus.classList.remove('active');
    }
    
    const homeShort = info.home_short.substring(0, 12);
    const awayShort = info.away_short.substring(0, 12);
    document.getElementById('table-home').textContent = homeShort;
    document.getElementById('table-away').textContent = awayShort;
    document.getElementById('corner-home').textContent = homeShort;
    document.getElementById('corner-away').textContent = awayShort;
    document.getElementById('card-home').textContent = homeShort;
    document.getElementById('card-away').textContent = awayShort;
    document.getElementById('home-form-name').textContent = info.home_team.substring(0, 15);
    document.getElementById('away-form-name').textContent = info.away_team.substring(0, 15);
    
    renderForm(data.home_form, 'home-form');
    renderForm(data.away_form, 'away-form');
    
    setTimeout(() => {
        setProbBar('prob-over15', probs.over_1_5);
        setProbBar('prob-over25', probs.over_2_5);
        setProbBar('prob-over35', probs.over_3_5);
        setProbBar('prob-btts', probs.btts);
        setProbBar('prob-xg', Math.min(probs.total_expected_goals * 15, 100), probs.total_expected_goals);
        setProbBar('prob-corners', Math.min(probs.expected_corners * 5, 100), probs.expected_corners);
        setProbBar('prob-cards', Math.min(probs.expected_cards * 12, 100), probs.expected_cards);
    }, 100);
    
    renderGoalsTable(homeStats, awayStats);
    renderCornersTable(homeStats, awayStats);
    renderCardsTable(homeStats, awayStats);
    
    const incidentsCard = document.getElementById('live-incidents-card');
    const incidentsDiv = document.getElementById('live-incidents');
    if (data.live_incidents && data.live_incidents.length > 0) {
        incidentsCard.classList.remove('hidden');
        incidentsDiv.innerHTML = data.live_incidents.map(inc => `
            <div class="incident-item">
                <span class="incident-minute">${inc.minute}'</span>
                <span class="incident-type ${inc.type.toLowerCase()}">${inc.type}</span>
                <span>${inc.text} ${inc.player}</span>
            </div>
        `).join('');
    } else {
        incidentsCard.classList.add('hidden');
    }
}

function renderForm(form, elementId) {
    const container = document.getElementById(elementId);
    if (!form || !form.length) {
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
    const pct = Math.min(value || 0, 100);
    
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
        const homeVal = r.isPct ? (r.home + '%') : r.home;
        const awayVal = r.isPct ? (r.away + '%') : r.away;
        const avgVal = r.isPct ? (avg + '%') : avg;
        
        const homeClass = r.home >= 60 ? 'value-high' : r.home >= 40 ? 'value-medium' : 'value-low';
        const awayClass = r.away >= 60 ? 'value-high' : r.away >= 40 ? 'value-medium' : 'value-low';
        
        return `<tr><td>${r.label}</td><td class="${homeClass}">${homeVal}</td><td class="${awayClass}">${awayVal}</td><td>${avgVal}</td></tr>`;
    }).join('');
}

function renderCornersTable(home, away) {
    const tbody = document.getElementById('corners-table-body');
    const h = home.home || home;
    const a = away.away || away;
    
    tbody.innerHTML = `
        <tr><td>Corners/Partido</td><td class="value-high">${(h.avg_corners || 0).toFixed(1)}</td><td class="value-high">${(a.avg_corners || 0).toFixed(1)}</td><td>${(((h.avg_corners || 0) + (a.avg_corners || 0))/2).toFixed(1)}</td></tr>
        <tr><td>Over 8.5</td><td class="value-medium">${h.over_8_5_corners || 0}%</td><td class="value-medium">${a.over_8_5_corners || 0}%</td><td>${Math.round((h.over_8_5_corners + a.over_8_5_corners)/2)}%</td></tr>
        <tr><td>Over 9.5</td><td class="value-low">${h.over_9_5_corners || 0}%</td><td class="value-low">${a.over_9_5_corners || 0}%</td><td>${Math.round((h.over_9_5_corners + a.over_9_5_corners)/2)}%</td></tr>
        <tr><td>Over 10.5</td><td class="value-low">${h.over_10_5_corners || 0}%</td><td class="value-low">${a.over_10_5_corners || 0}%</td><td>${Math.round((h.over_10_5_corners + a.over_10_5_corners)/2)}%</td></tr>
    `;
}

function renderCardsTable(home, away) {
    const tbody = document.getElementById('cards-table-body');
    const h = home.home || home;
    const a = away.away || away;
    
    tbody.innerHTML = `
        <tr><td>Tarjetas/Partido</td><td class="value-high">${(h.avg_cards || 0).toFixed(2)}</td><td class="value-high">${(a.avg_cards || 0).toFixed(2)}</td><td>${(((h.avg_cards || 0) + (a.avg_cards || 0))/2).toFixed(2)}</td></tr>
        <tr><td>Over 3.5</td><td class="value-high">${h.over_3_5_cards || 0}%</td><td class="value-high">${a.over_3_5_cards || 0}%</td><td>${Math.round((h.over_3_5_cards + a.over_3_5_cards)/2)}%</td></tr>
        <tr><td>Over 4.5</td><td class="value-medium">${h.over_4_5_cards || 0}%</td><td class="value-medium">${a.over_4_5_cards || 0}%</td><td>${Math.round((h.over_4_5_cards + a.over_4_5_cards)/2)}%</td></tr>
        <tr><td>Over 5.5</td><td class="value-low">${Math.max(0, (h.over_4_5_cards || 0) - 20)}%</td><td class="value-low">${Math.max(0, (a.over_4_5_cards || 0) - 20)}%</td><td>${Math.max(0, Math.round((h.over_4_5_cards + a.over_4_5_cards)/2) - 20)}%</td></tr>
    `;
}

// ============ INIT ============
updateDateDisplay();
loadMatches();
