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
    return d + '/' + m + '/' + y;
}

function formatDateISO(date) {
    return date.toISOString().split('T')[0];
}

function formatLocalTime(utcDateString) {
    if (!utcDateString) return '--:--';
    const date = new Date(utcDateString);
    return date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function updateDateDisplay() {
    if (dateDisplay) dateDisplay.textContent = formatDate(currentDate);
    if (datePicker) datePicker.value = formatDateISO(currentDate);
}

const prevBtn = document.getElementById('prev-date');
const nextBtn = document.getElementById('next-date');

if (prevBtn) {
    prevBtn.addEventListener('click', () => {
        currentDate.setDate(currentDate.getDate() - 1);
        updateDateDisplay();
        loadMatches();
    });
}

if (nextBtn) {
    nextBtn.addEventListener('click', () => {
        currentDate.setDate(currentDate.getDate() + 1);
        updateDateDisplay();
        loadMatches();
    });
}

if (dateDisplay) {
    dateDisplay.addEventListener('click', () => {
        if (datePicker) datePicker.showPicker();
    });
}

if (datePicker) {
    datePicker.addEventListener('change', (e) => {
        currentDate = new Date(e.target.value);
        updateDateDisplay();
        loadMatches();
    });
}

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

    if (matchesContainer) {
        matchesContainer.innerHTML = '<div class="loading">Cargando partidos...</div>';
    }

    try {
        const response = await fetch('/api/matches?date=' + dateStr);
        if (!response.ok) throw new Error('HTTP ' + response.status);

        allMatches = await response.json();

        if (!Array.isArray(allMatches)) {
            throw new Error('Respuesta invalida del servidor');
        }

        if (allMatches.length === 0) {
            if (matchesContainer) {
                matchesContainer.innerHTML = '<div class="no-matches"><div class="no-matches-icon">📅</div>No hay partidos para ' + formatDate(currentDate) + '<br><small>Prueba con otra fecha o filtro.<br>Las ligas europeas vuelven en agosto.</small></div>';
            }
            return;
        }

        renderMatches();

    } catch (e) {
        console.error('Error:', e);
        if (matchesContainer) {
            matchesContainer.innerHTML = '<div class="no-matches"><div class="no-matches-icon">⚠️</div>Error: ' + e.message + '<br><small>Intenta recargar la pagina</small></div>';
        }
    }
}

function renderMatches() {
    let matches = allMatches;

    if (currentFilter !== 'all') {
        matches = matches.filter(m => {
            const country = (m.country || '').toLowerCase();
            const league = (m.league_name || '').toLowerCase();
            const filter = currentFilter.toLowerCase();
            return country.includes(filter) || league.includes(filter);
        });
    }

    if (!matches.length) {
        if (matchesContainer) matchesContainer.innerHTML = '<div class="no-matches">No hay partidos para este filtro</div>';
        return;
    }

    // Ordenar: en vivo primero, luego por hora
    matches.sort((a, b) => {
        const statusOrder = { '1H': 0, 'HT': 0, 'LIVE': 0, '2H': 0, 'NS': 1, 'FT': 2, 'PST': 3, 'CANC': 4 };
        const orderA = statusOrder[a.status] !== undefined ? statusOrder[a.status] : 1;
        const orderB = statusOrder[b.status] !== undefined ? statusOrder[b.status] : 1;
        if (orderA !== orderB) return orderA - orderB;
        return (a.utcDate || '').localeCompare(b.utcDate || '');
    });

    const html = matches.map(match => {
        const home = match.homeTeam;
        const away = match.awayTeam;
        const time = formatLocalTime(match.utcDate);
        const isLive = ['1H', '2H', 'HT', 'LIVE'].includes(match.status);
        const isFinished = match.status === 'FT';

        let statusBadge = '';
        if (isLive) statusBadge = '<span class="status-badge live">LIVE ' + (match.minute || '') + ''</span>';
        else if (isFinished) statusBadge = '<span class="status-badge finished">FT</span>';
        else if (match.status === 'PST') statusBadge = '<span class="status-badge postponed">POS</span>';

        const scoreText = (match.homeScore !== null && match.awayScore !== null) 
            ? match.homeScore + ' - ' + match.awayScore 
            : '';

        const homeLogo = home.crest || 'https://crests.football-data.org/' + home.id + '.svg';
        const awayLogo = away.crest || 'https://crests.football-data.org/' + away.id + '.svg';

        return '<div class="match-card-main ' + (isLive ? 'live ' : '') + (isFinished ? 'finished' : '') + '" data-match-id="' + match.id + '">' +
            '<div class="match-time-row">' +
                '<span class="match-time">' + time + '</span>' +
                statusBadge +
                (scoreText ? '<span class="match-score">' + scoreText + '</span>' : '') +
            '</div>' +
            '<div class="match-teams-row">' +
                '<div class="match-team-row">' +
                    '<img src="' + homeLogo + '" alt="' + home.name + '" loading="lazy" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2224%22 height=%2224%22%3E%3Ccircle cx=%2212%22 cy=%2212%22 r=%2210%22 fill=%22%23374151%22/%3E%3C/svg%3E'">' +
                    '<span>' + (home.shortName || home.name) + '</span>' +
                    (match.homeScore !== null ? '<span class="team-score">' + match.homeScore + '</span>' : '') +
                '</div>' +
                '<div class="match-team-row">' +
                    '<img src="' + awayLogo + '" alt="' + away.name + '" loading="lazy" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2224%22 height=%2224%22%3E%3Ccircle cx=%2212%22 cy=%2212%22 r=%2210%22 fill=%22%23374151%22/%3E%3C/svg%3E'">' +
                    '<span>' + (away.shortName || away.name) + '</span>' +
                    (match.awayScore !== null ? '<span class="team-score">' + match.awayScore + '</span>' : '') +
                '</div>' +
            '</div>' +
            '<div class="match-footer">' +
                '<span class="match-league-tag">' + (match.league_name || '') + '</span>' +
                (match.venue && match.venue !== 'N/A' ? '<span class="match-venue">🏟️ ' + match.venue + '</span>' : '') +
            '</div>' +
        '</div>';
    }).join('');

    if (matchesContainer) matchesContainer.innerHTML = html;

    document.querySelectorAll('.match-card-main').forEach(card => {
        card.addEventListener('click', () => analyzeMatch(card.dataset.matchId));
    });
}

// ============ NAVIGATION ============
function showMatches() {
    if (matchesContainer && matchesContainer.parentElement) matchesContainer.parentElement.classList.remove('hidden');
    const dateSelector = document.querySelector('.date-selector');
    const leagueFilters = document.querySelector('.league-filters');
    const appHeader = document.querySelector('.app-header');

    if (dateSelector) dateSelector.classList.remove('hidden');
    if (leagueFilters) leagueFilters.classList.remove('hidden');
    if (appHeader) appHeader.classList.remove('hidden');
    if (analysisSection) analysisSection.classList.add('hidden');
    window.scrollTo(0, 0);
}

function showAnalysis() {
    if (matchesContainer && matchesContainer.parentElement) matchesContainer.parentElement.classList.add('hidden');
    const dateSelector = document.querySelector('.date-selector');
    const leagueFilters = document.querySelector('.league-filters');
    const appHeader = document.querySelector('.app-header');

    if (dateSelector) dateSelector.classList.add('hidden');
    if (leagueFilters) leagueFilters.classList.add('hidden');
    if (appHeader) appHeader.classList.add('hidden');
    if (analysisSection) analysisSection.classList.remove('hidden');
    window.scrollTo(0, 0);
}

const backBtn = document.getElementById('back-btn-matches');
if (backBtn) backBtn.addEventListener('click', showMatches);

// ============ TABS ============
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        const tabContent = document.getElementById('tab-' + btn.dataset.tab);
        if (tabContent) tabContent.classList.add('active');
    });
});

// ============ ANALYZE MATCH ============
async function analyzeMatch(matchId) {
    showAnalysis();

    // Reset tabs
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    const summaryTab = document.querySelector('[data-tab="summary"]');
    const summaryContent = document.getElementById('tab-summary');
    if (summaryTab) summaryTab.classList.add('active');
    if (summaryContent) summaryContent.classList.add('active');

    try {
        const response = await fetch('/api/analyze/' + matchId);
        if (!response.ok) throw new Error('HTTP ' + response.status);

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

    // Header
    const homeNameEl = document.getElementById('home-name');
    const awayNameEl = document.getElementById('away-name');
    const homeLogoEl = document.getElementById('home-logo');
    const awayLogoEl = document.getElementById('away-logo');
    const homeFormationEl = document.getElementById('home-formation');
    const awayFormationEl = document.getElementById('away-formation');

    if (homeNameEl) homeNameEl.textContent = info.home_team;
    if (awayNameEl) awayNameEl.textContent = info.away_team;
    if (homeLogoEl) homeLogoEl.src = info.home_logo;
    if (awayLogoEl) awayLogoEl.src = info.away_logo;
    if (homeFormationEl) homeFormationEl.textContent = info.home_formation || '';
    if (awayFormationEl) awayFormationEl.textContent = info.away_formation || '';

    const scoreDisplay = document.getElementById('score-display');
    if (scoreDisplay) {
        if (info.home_score !== null && info.away_score !== null) {
            let scoreHtml = '<div class="score-box">' + info.home_score + '</div><div class="score-sep">-</div><div class="score-box">' + info.away_score + '</div>';
            if (info.halfTimeHome !== null) {
                scoreHtml += '<div class="ht-score">Descanso: ' + info.halfTimeHome + '-' + info.halfTimeAway + '</div>';
            }
            scoreDisplay.innerHTML = scoreHtml;
        } else {
            scoreDisplay.textContent = 'VS';
        }
    }

    // Meta
    let metaText = info.date + ' | ' + info.time + ' | ' + info.league;
    if (info.matchday) metaText += ' | Jornada ' + info.matchday;
    const matchMeta = document.getElementById('match-meta');
    if (matchMeta) matchMeta.textContent = metaText;

    // Details
    let detailsHtml = '';
    if (info.venue && info.venue !== 'N/A') detailsHtml += '<span>🏟️ ' + info.venue + '</span>';
    if (info.attendance) detailsHtml += '<span>👥 ' + info.attendance.toLocaleString() + '</span>';
    if (info.home_coach) detailsHtml += '<span>👔 ' + info.home_coach + ' vs ' + info.away_coach + '</span>';
    if (info.referees && info.referees.length) detailsHtml += '<span>🎺 ' + info.referees[0] + '</span>';
    const matchDetails = document.getElementById('match-details');
    if (matchDetails) matchDetails.innerHTML = detailsHtml;

    // Standings
    renderStandings(homeStats, awayStats, info);

    // Probabilities
    setTimeout(() => {
        setProbBar('prob-over15', probs.over_1_5);
        setProbBar('prob-over25', probs.over_2_5);
        setProbBar('prob-over35', probs.over_3_5);
        setProbBar('prob-btts', probs.btts);
        setProbBar('prob-xg', Math.min(probs.total_expected_goals * 15, 100), probs.total_expected_goals);
        setProbBar('prob-corners', Math.min(probs.expected_corners * 5, 100), probs.expected_corners);
        setProbBar('prob-cards', Math.min(probs.expected_cards * 12, 100), probs.expected_cards);
    }, 100);

    // Odds
    renderOdds(data.odds);

    // H2H
    renderH2H(data.h2h);

    // Form
    const homeFormTitle = document.getElementById('home-form-title');
    const awayFormTitle = document.getElementById('away-form-title');
    if (homeFormTitle) homeFormTitle.textContent = info.home_team.substring(0, 20);
    if (awayFormTitle) awayFormTitle.textContent = info.away_team.substring(0, 20);
    renderForm(data.home_form, 'home-form', 'home-form-list');
    renderForm(data.away_form, 'away-form', 'away-form-list');

    // Stats tables
    const statsHome = document.getElementById('stats-home');
    const statsAway = document.getElementById('stats-away');
    const goalsHome = document.getElementById('goals-home');
    const goalsAway = document.getElementById('goals-away');
    const miscHome = document.getElementById('misc-home');
    const miscAway = document.getElementById('misc-away');

    if (statsHome) statsHome.textContent = info.home_short;
    if (statsAway) statsAway.textContent = info.away_short;
    if (goalsHome) goalsHome.textContent = info.home_short;
    if (goalsAway) goalsAway.textContent = info.away_short;
    if (miscHome) miscHome.textContent = info.home_short;
    if (miscAway) miscAway.textContent = info.away_short;

    renderMatchStats(homeStats, awayStats);
    renderGoalsTable(homeStats, awayStats);
    renderMiscTable(homeStats, awayStats);

    // Events
    renderEvents(data.match_events, info);
}

function renderStandings(home, away, info) {
    const container = document.getElementById('standings-row');
    if (!container) return;

    if (!home.position && !away.position) {
        container.innerHTML = '<div class="no-data">Datos de clasificacion no disponibles</div>';
        return;
    }

    const homeHtml = home.position ? 
        '<div class="pos-badge" style="background:' + getPosColor(home.position) + '">#' + home.position + '</div>' +
        '<div class="standing-info">' +
            '<div>' + home.points + ' pts | ' + home.played + ' PJ</div>' +
            '<div>' + home.won + 'V ' + home.draw + 'E ' + home.lost + 'D</div>' +
            '<div>GF:' + home.goals_for + ' GC:' + home.goals_against + '</div>' +
        '</div>' +
        '<div class="form-string">' + (home.form_string || '') + '</div>'
        : '<div class="no-data">Sin datos</div>';

    const awayHtml = away.position ? 
        '<div class="pos-badge" style="background:' + getPosColor(away.position) + '">#' + away.position + '</div>' +
        '<div class="standing-info">' +
            '<div>' + away.points + ' pts | ' + away.played + ' PJ</div>' +
            '<div>' + away.won + 'V ' + away.draw + 'E ' + away.lost + 'D</div>' +
            '<div>GF:' + away.goals_for + ' GC:' + away.goals_against + '</div>' +
        '</div>' +
        '<div class="form-string">' + (away.form_string || '') + '</div>'
        : '<div class="no-data">Sin datos</div>';

    const homeStanding = document.getElementById('home-standing');
    const awayStanding = document.getElementById('away-standing');
    if (homeStanding) homeStanding.innerHTML = homeHtml;
    if (awayStanding) awayStanding.innerHTML = awayHtml;
}

function getPosColor(pos) {
    if (pos <= 4) return 'var(--success)';
    if (pos <= 6) return 'var(--info)';
    if (pos >= 18) return 'var(--danger)';
    return 'var(--warning)';
}

function renderOdds(odds) {
    const card = document.getElementById('odds-card');
    if (!card) return;

    if (!odds || (!odds.home && !odds.draw && !odds.away)) {
        card.classList.add('hidden');
        return;
    }
    card.classList.remove('hidden');

    const oddsRow = document.getElementById('odds-row');
    if (oddsRow) {
        oddsRow.innerHTML = 
            '<div class="odd-box"><span class="odd-label">1</span><span class="odd-value">' + (odds.home || '-') + '</span></div>' +
            '<div class="odd-box"><span class="odd-label">X</span><span class="odd-value">' + (odds.draw || '-') + '</span></div>' +
            '<div class="odd-box"><span class="odd-label">2</span><span class="odd-value">' + (odds.away || '-') + '</span></div>';
    }
}

function renderH2H(h2h) {
    const statsDiv = document.getElementById('h2h-stats');
    const matchesDiv = document.getElementById('h2h-matches');
    if (!statsDiv || !matchesDiv) return;

    const stats = h2h.stats;

    if (!stats.total_matches) {
        statsDiv.innerHTML = '<div class="no-data">Sin datos H2H</div>';
        matchesDiv.innerHTML = '';
        return;
    }

    statsDiv.innerHTML = 
        '<div class="h2h-stat-item"><span class="h2h-number">' + stats.total_matches + '</span><span class="h2h-label">Partidos</span></div>' +
        '<div class="h2h-stat-item win"><span class="h2h-number">' + stats.home_wins + '</span><span class="h2h-label">Victorias Local</span></div>' +
        '<div class="h2h-stat-item draw"><span class="h2h-number">' + stats.draws + '</span><span class="h2h-label">Empates</span></div>' +
        '<div class="h2h-stat-item win"><span class="h2h-number">' + stats.away_wins + '</span><span class="h2h-label">Victorias Visitante</span></div>' +
        '<div class="h2h-stat-item"><span class="h2h-number">' + stats.home_goals + '-' + stats.away_goals + '</span><span class="h2h-label">Goles</span></div>';

    matchesDiv.innerHTML = h2h.matches.map(m => 
        '<div class="h2h-match">' +
            '<span class="h2h-date">' + m.date + '</span>' +
            '<span class="h2h-comp">' + m.competition + '</span>' +
            '<span class="h2h-result">' + m.home + ' ' + (m.homeScore !== null ? m.homeScore : '-') + ' - ' + (m.awayScore !== null ? m.awayScore : '-') + ' ' + m.away + '</span>' +
        '</div>'
    ).join('');
}

function renderForm(form, badgesId, listId) {
    const badgesContainer = document.getElementById(badgesId);
    const listContainer = document.getElementById(listId);

    if (!badgesContainer || !listContainer) return;

    if (!form || !form.length) {
        badgesContainer.innerHTML = '<span class="no-data-small">Sin datos</span>';
        listContainer.innerHTML = '';
        return;
    }

    badgesContainer.innerHTML = form.map(f => 
        '<div class="badge ' + f.result + '" title="' + f.result_text + ': ' + f.team_goals + '-' + f.opp_goals + ' vs ' + f.opponent + ' (' + (f.competition || '') + ')">' + (f.result === 'W' ? 'V' : f.result === 'D' ? 'E' : 'D') + '</div>'
    ).join('');

    listContainer.innerHTML = form.map(f => 
        '<div class="form-item">' +
            '<span class="form-result ' + f.result + '">' + (f.result === 'W' ? '✅' : f.result === 'D' ? '➖' : '❌') + '</span>' +
            '<span class="form-score">' + f.team_goals + '-' + f.opp_goals + '</span>' +
            '<span class="form-opp">' + f.opponent.substring(0, 15) + '</span>' +
            '<span class="form-venue">' + (f.venue === 'home' ? '🏠' : '✈️') + '</span>' +
            '<span class="form-date">' + f.date + '</span>' +
        '</div>'
    ).join('');
}

function renderMatchStats(home, away) {
    const tbody = document.getElementById('match-stats-body');
    if (!tbody) return;

    const stats = [
        { label: 'Posesion (%)', home: home.possession, away: away.possession, suffix: '%' },
        { label: 'Tiros', home: home.shots, away: away.shots },
        { label: 'Tiros a puerta', home: home.shots_on_goal, away: away.shots_on_goal },
        { label: 'Corners', home: home.avg_corners, away: away.avg_corners },
        { label: 'Faltas', home: home.fouls, away: away.fouls },
        { label: 'Fueras de juego', home: home.offsides, away: away.offsides },
        { label: 'Tarjetas', home: home.avg_cards, away: away.avg_cards },
    ];

    tbody.innerHTML = stats.map(s => {
        const hVal = s.home || 0;
        const aVal = s.away || 0;
        const hClass = hVal > aVal ? 'value-high' : hVal < aVal ? 'value-low' : 'value-medium';
        const aClass = aVal > hVal ? 'value-high' : aVal < hVal ? 'value-low' : 'value-medium';
        const suffix = s.suffix || '';

        return '<tr><td>' + s.label + '</td><td class="' + hClass + '">' + hVal + suffix + '</td><td class="' + aClass + '">' + aVal + suffix + '</td></tr>';
    }).join('');
}

function renderGoalsTable(home, away) {
    const tbody = document.getElementById('goals-table-body');
    if (!tbody) return;

    const rows = [
        { label: 'Goles/Partido', home: home.avg_total_goals, away: away.avg_total_goals },
        { label: 'Goles a Favor', home: home.avg_team_goals, away: away.avg_team_goals },
        { label: 'Goles en Contra', home: home.avg_conceded, away: away.avg_conceded },
        { label: 'Over 1.5', home: home.over_1_5_pct, away: away.over_1_5_pct, isPct: true },
        { label: 'Over 2.5', home: home.over_2_5_pct, away: away.over_2_5_pct, isPct: true },
        { label: 'Over 3.5', home: home.over_3_5_pct, away: away.over_3_5_pct, isPct: true },
        { label: 'BTTS', home: home.btts_pct, away: away.btts_pct, isPct: true },
    ];

    tbody.innerHTML = rows.map(r => {
        const avg = ((parseFloat(r.home) + parseFloat(r.away)) / 2).toFixed(1);
        const homeVal = r.isPct ? (r.home + '%') : r.home;
        const awayVal = r.isPct ? (r.away + '%') : r.away;
        const avgVal = r.isPct ? (avg + '%') : avg;

        const homeClass = r.home >= 60 ? 'value-high' : r.home >= 40 ? 'value-medium' : 'value-low';
        const awayClass = r.away >= 60 ? 'value-high' : r.away >= 40 ? 'value-medium' : 'value-low';

        return '<tr><td>' + r.label + '</td><td class="' + homeClass + '">' + homeVal + '</td><td class="' + awayClass + '">' + awayVal + '</td><td>' + avgVal + '</td></tr>';
    }).join('');
}

function renderMiscTable(home, away) {
    const tbody = document.getElementById('misc-table-body');
    if (!tbody) return;

    tbody.innerHTML = 
        '<tr><td>Corners/Partido</td><td class="value-high">' + (home.avg_corners || 0).toFixed(1) + '</td><td class="value-high">' + (away.avg_corners || 0).toFixed(1) + '</td></tr>' +
        '<tr><td>Tarjetas/Partido</td><td class="value-high">' + (home.avg_cards || 0).toFixed(1) + '</td><td class="value-high">' + (away.avg_cards || 0).toFixed(1) + '</td></tr>' +
        '<tr><td>Posicion Liga</td><td class="value-high">#' + (home.position || '-') + '</td><td class="value-high">#' + (away.position || '-') + '</td></tr>' +
        '<tr><td>Puntos</td><td class="value-high">' + (home.points || '-') + '</td><td class="value-high">' + (away.points || '-') + '</td></tr>' +
        '<tr><td>Partidos Jugados</td><td>' + (home.played || '-') + '</td><td>' + (away.played || '-') + '</td></tr>';
}

function renderEvents(events, info) {
    // Scorers
    const scorersCard = document.getElementById('scorers-card');
    const scorersDiv = document.getElementById('scorers-list');
    if (scorersCard && scorersDiv) {
        if (events.scorers && events.scorers.length > 0) {
            scorersCard.classList.remove('hidden');
            scorersDiv.innerHTML = events.scorers.map(s => 
                '<div class="event-item">' +
                    '<span class="event-minute">' + s.minute + ''</span>' +
                    '<span class="event-icon goal">⚽</span>' +
                    '<span class="event-player">' + s.player + '</span>' +
                    '<span class="event-team">' + (s.team === 'home' ? info.home_short : info.away_short) + '</span>' +
                    '<span class="event-type">' + (s.type === 'PENALTY' ? '(P)' : s.type === 'OWN_GOAL' ? '(OG)' : '') + '</span>' +
                '</div>'
            ).join('');
        } else {
            scorersCard.classList.add('hidden');
        }
    }

    // Cards
    const cardsCard = document.getElementById('cards-card');
    const cardsDiv = document.getElementById('cards-list');
    if (cardsCard && cardsDiv) {
        if (events.bookings && events.bookings.length > 0) {
            cardsCard.classList.remove('hidden');
            cardsDiv.innerHTML = events.bookings.map(c => 
                '<div class="event-item">' +
                    '<span class="event-minute">' + c.minute + ''</span>' +
                    '<span class="event-icon ' + c.card.toLowerCase() + '">' + (c.card === 'RED' ? '🟥' : '🟨') + '</span>' +
                    '<span class="event-player">' + c.player + '</span>' +
                    '<span class="event-team">' + (c.team === 'home' ? info.home_short : info.away_short) + '</span>' +
                '</div>'
            ).join('');
        } else {
            cardsCard.classList.add('hidden');
        }
    }

    // Substitutions
    const subsCard = document.getElementById('subs-card');
    const subsDiv = document.getElementById('subs-list');
    if (subsCard && subsDiv) {
        if (events.substitutions && events.substitutions.length > 0) {
            subsCard.classList.remove('hidden');
            subsDiv.innerHTML = events.substitutions.map(s => 
                '<div class="event-item">' +
                    '<span class="event-minute">' + s.minute + ''</span>' +
                    '<span class="event-icon sub">🔄</span>' +
                    '<span class="event-player"><span class="sub-out">' + s.out + '</span> → <span class="sub-in">' + s.in + '</span></span>' +
                    '<span class="event-team">' + (s.team === 'home' ? info.home_short : info.away_short) + '</span>' +
                '</div>'
            ).join('');
        } else {
            subsCard.classList.add('hidden');
        }
    }
}

function setProbBar(id, value, displayValue) {
    const bar = document.getElementById(id);
    const val = document.getElementById(id + '-val');
    if (!bar || !val) return;

    const pct = Math.min(value || 0, 100);

    bar.style.width = pct + '%';
    bar.className = 'prob-bar';
    if (pct < 45) bar.classList.add('low');
    else if (pct < 70) bar.classList.add('medium');

    val.textContent = displayValue !== undefined && displayValue !== null ? displayValue : (pct + '%');
}

// ============ INIT ============
updateDateDisplay();
loadMatches();
