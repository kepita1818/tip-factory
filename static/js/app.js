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

// Event listeners
const prevBtn = document.getElementById('prev-date');
const nextBtn = document.getElementById('next-date');

if (prevBtn) {
    prevBtn.addEventListener('click', function() {
        currentDate.setDate(currentDate.getDate() - 1);
        updateDateDisplay();
        loadMatches();
    });
}

if (nextBtn) {
    nextBtn.addEventListener('click', function() {
        currentDate.setDate(currentDate.getDate() + 1);
        updateDateDisplay();
        loadMatches();
    });
}

if (dateDisplay && datePicker) {
    dateDisplay.addEventListener('click', function() {
        datePicker.showPicker();
    });
    datePicker.addEventListener('change', function(e) {
        currentDate = new Date(e.target.value);
        updateDateDisplay();
        loadMatches();
    });
}

// ============ FILTERS ============
document.querySelectorAll('.filter-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
        document.querySelectorAll('.filter-btn').forEach(function(b) { b.classList.remove('active'); });
        btn.classList.add('active');
        currentFilter = btn.dataset.filter;
        renderMatches();
    });
});

// ============ LOAD MATCHES ============
function loadMatches() {
    const dateStr = formatDateISO(currentDate);

    if (matchesContainer) {
        matchesContainer.innerHTML = '<div class="loading">Cargando partidos...</div>';
    }

    fetch('/api/matches?date=' + dateStr)
        .then(function(response) {
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return response.json();
        })
        .then(function(data) {
            allMatches = data;

            if (!Array.isArray(allMatches)) {
                throw new Error('Respuesta invalida');
            }

            if (allMatches.length === 0) {
                if (matchesContainer) {
                    matchesContainer.innerHTML = '<div class="no-matches">No hay partidos para ' + formatDate(currentDate) + '<br><small>Prueba con otra fecha</small></div>';
                }
                return;
            }

            renderMatches();
        })
        .catch(function(e) {
            console.error('Error:', e);
            if (matchesContainer) {
                matchesContainer.innerHTML = '<div class="no-matches">Error: ' + e.message + '<br><small>Intenta recargar</small></div>';
            }
        });
}

function renderMatches() {
    let matches = allMatches;

    if (currentFilter !== 'all') {
        matches = matches.filter(function(m) {
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

    // Sort: live first, then by time
    matches.sort(function(a, b) {
        const statusOrder = { '1H': 0, 'HT': 0, 'LIVE': 0, '2H': 0, 'NS': 1, 'FT': 2, 'PST': 3, 'CANC': 4 };
        const orderA = statusOrder[a.status] !== undefined ? statusOrder[a.status] : 1;
        const orderB = statusOrder[b.status] !== undefined ? statusOrder[b.status] : 1;
        if (orderA !== orderB) return orderA - orderB;
        return (a.utcDate || '').localeCompare(b.utcDate || '');
    });

    var html = '';
    for (var i = 0; i < matches.length; i++) {
        var match = matches[i];
        var home = match.homeTeam;
        var away = match.awayTeam;
        var time = formatLocalTime(match.utcDate);
        var isLive = ['1H', '2H', 'HT', 'LIVE'].includes(match.status);
        var isFinished = match.status === 'FT';

        var statusBadge = '';
        if (isLive) statusBadge = '<span class="status-badge live">LIVE ' + (match.minute || '') + ''</span>';
        else if (isFinished) statusBadge = '<span class="status-badge finished">FT</span>';

        var scoreText = '';
        if (match.homeScore !== null && match.awayScore !== null) {
            scoreText = match.homeScore + ' - ' + match.awayScore;
        }

        var homeLogo = home.crest || 'https://crests.football-data.org/' + home.id + '.svg';
        var awayLogo = away.crest || 'https://crests.football-data.org/' + away.id + '.svg';

        html += '<div class="match-card ' + (isLive ? 'live ' : '') + (isFinished ? 'finished' : '') + '" data-match-id="' + match.id + '">';
        html += '<div class="match-time-row">';
        html += '<span class="match-time">' + time + '</span>';
        html += statusBadge;
        if (scoreText) html += '<span class="match-score">' + scoreText + '</span>';
        html += '</div>';
        html += '<div class="match-teams">';
        html += '<div class="match-team">';
        html += '<img src="' + homeLogo + '" alt="" onerror="this.style.visibility='hidden'">';
        html += '<span>' + (home.shortName || home.name) + '</span>';
        html += '</div>';
        html += '<div class="match-team">';
        html += '<img src="' + awayLogo + '" alt="" onerror="this.style.visibility='hidden'">';
        html += '<span>' + (away.shortName || away.name) + '</span>';
        html += '</div>';
        html += '</div>';
        html += '</div>';
    }

    if (matchesContainer) matchesContainer.innerHTML = html;

    var cards = document.querySelectorAll('.match-card');
    for (var j = 0; j < cards.length; j++) {
        cards[j].addEventListener('click', function() {
            analyzeMatch(this.dataset.matchId);
        });
    }
}

// ============ NAVIGATION ============
function showMatches() {
    if (matchesContainer && matchesContainer.parentElement) matchesContainer.parentElement.classList.remove('hidden');
    var ds = document.querySelector('.date-selector');
    var lf = document.querySelector('.league-filters');
    var ah = document.querySelector('.app-header');
    if (ds) ds.classList.remove('hidden');
    if (lf) lf.classList.remove('hidden');
    if (ah) ah.classList.remove('hidden');
    if (analysisSection) analysisSection.classList.add('hidden');
    window.scrollTo(0, 0);
}

function showAnalysis() {
    if (matchesContainer && matchesContainer.parentElement) matchesContainer.parentElement.classList.add('hidden');
    var ds = document.querySelector('.date-selector');
    var lf = document.querySelector('.league-filters');
    var ah = document.querySelector('.app-header');
    if (ds) ds.classList.add('hidden');
    if (lf) lf.classList.add('hidden');
    if (ah) ah.classList.add('hidden');
    if (analysisSection) analysisSection.classList.remove('hidden');
    window.scrollTo(0, 0);
}

var backBtn = document.getElementById('back-btn');
if (backBtn) backBtn.addEventListener('click', showMatches);

// ============ TABS ============
document.querySelectorAll('.tab-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
        document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
        document.querySelectorAll('.tab-content').forEach(function(c) { c.classList.remove('active'); });
        btn.classList.add('active');
        var tabContent = document.getElementById('tab-' + btn.dataset.tab);
        if (tabContent) tabContent.classList.add('active');
    });
});

// ============ ANALYZE MATCH ============
function analyzeMatch(matchId) {
    showAnalysis();

    // Reset tabs
    document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
    document.querySelectorAll('.tab-content').forEach(function(c) { c.classList.remove('active'); });
    var summaryTab = document.querySelector('[data-tab="resumen"]');
    var summaryContent = document.getElementById('tab-resumen');
    if (summaryTab) summaryTab.classList.add('active');
    if (summaryContent) summaryContent.classList.add('active');

    fetch('/api/analyze/' + matchId)
        .then(function(response) {
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return response.json();
        })
        .then(function(data) {
            renderAnalysis(data);
        })
        .catch(function(e) {
            console.error('Error:', e);
            alert('Error analizando partido');
            showMatches();
        });
}

function renderAnalysis(data) {
    var info = data.match_info;
    var probs = data.probabilities;
    var homeStats = data.home_stats;
    var awayStats = data.away_stats;

    // Subtitle
    var subtitle = info.league + ' - ' + info.date + ' - ' + info.time;
    if (info.venue) subtitle += ' - ' + info.venue;
    var analysisSubtitle = document.getElementById('analysis-subtitle');
    if (analysisSubtitle) analysisSubtitle.textContent = subtitle;

    // Team names and logos
    var homeNameEl = document.getElementById('home-name');
    var awayNameEl = document.getElementById('away-name');
    var homeLogoEl = document.getElementById('home-logo');
    var awayLogoEl = document.getElementById('away-logo');

    if (homeNameEl) homeNameEl.textContent = info.home_team;
    if (awayNameEl) awayNameEl.textContent = info.away_team;
    if (homeLogoEl) homeLogoEl.src = info.home_logo;
    if (awayLogoEl) awayLogoEl.src = info.away_logo;

    // Form badges
    renderFormBadges(data.home_form, 'home-form-badges');
    renderFormBadges(data.away_form, 'away-form-badges');

    // Probabilities grid (like TipFactory)
    renderProbGrid(probs, homeStats, awayStats);

    // Goals table
    renderGoalsTable(homeStats, awayStats, info);

    // Corners tables
    renderCornersTables(homeStats, awayStats, info);

    // Cards table
    renderCardsTable(homeStats, awayStats, info);
}

function renderFormBadges(form, elementId) {
    var container = document.getElementById(elementId);
    if (!container) return;

    if (!form || !form.length) {
        container.innerHTML = '<span class="no-data">Sin datos</span>';
        return;
    }

    var html = '';
    for (var i = 0; i < form.length; i++) {
        var f = form[i];
        var color = f.result === 'W' ? '#22c55e' : f.result === 'D' ? '#eab308' : '#ef4444';
        html += '<div class="form-badge" style="background:' + color + '" title="' + f.result_text + ': ' + f.team_goals + '-' + f.opp_goals + ' vs ' + f.opponent + '">' + f.result + '</div>';
    }
    container.innerHTML = html;
}

function renderProbGrid(probs, home, away) {
    var container = document.getElementById('prob-grid');
    if (!container) return;

    var items = [
        { label: 'Mas de 2.5', value: probs.over_2_5 + '%', sub: 'Media de ' + ((home.avg_total_goals + away.avg_total_goals) / 2).toFixed(2) + ' goles por partido' },
        { label: 'Mas de 1.5', value: probs.over_1_5 + '%', sub: 'Media de ' + ((home.over_1_5_pct + away.over_1_5_pct) / 2).toFixed(1) + '% en los ultimos 5 partidos' },
        { label: 'AMB', value: probs.btts + '%', sub: 'Ambos equipos marcan' },
        { label: home.avg_team_goals + ' Goles/Partido', value: '', sub: 'Local - Media de goles' },
        { label: away.avg_team_goals + ' Goles/Partido', value: '', sub: 'Visitante - Media de goles' },
        { label: probs.expected_cards.toFixed(2) + ' Tarjetas', value: '', sub: 'Media de tarjetas esperadas' },
        { label: probs.expected_corners.toFixed(2) + ' Corners', value: '', sub: 'Media de corners esperados' },
    ];

    var html = '';
    for (var i = 0; i < items.length; i++) {
        var item = items[i];
        html += '<div class="prob-box">';
        html += '<div class="prob-box-value">' + item.value + '</div>';
        html += '<div class="prob-box-label">' + item.label + '</div>';
        html += '<div class="prob-box-sub">' + item.sub + '</div>';
        html += '</div>';
    }
    container.innerHTML = html;
}

function renderGoalsTable(home, away, info) {
    var tbody = document.getElementById('goals-table-body');
    var homeHeader = document.getElementById('goals-home-header');
    var awayHeader = document.getElementById('goals-away-header');

    if (homeHeader) homeHeader.textContent = info.home_short;
    if (awayHeader) awayHeader.textContent = info.away_short;
    if (!tbody) return;

    var rows = [
        { label: 'Goles/Partido', home: home.avg_total_goals, away: away.avg_total_goals },
        { label: 'Mas de 1.5', home: home.over_1_5_pct, away: away.over_1_5_pct, isPct: true },
        { label: 'Mas de 2.5', home: home.over_2_5_pct, away: away.over_2_5_pct, isPct: true },
        { label: 'Mas de 3.5', home: home.over_3_5_pct, away: away.over_3_5_pct, isPct: true },
        { label: 'AMB', home: home.btts_pct, away: away.btts_pct, isPct: true },
    ];

    var html = '';
    for (var i = 0; i < rows.length; i++) {
        var r = rows[i];
        var avg = ((parseFloat(r.home) + parseFloat(r.away)) / 2).toFixed(1);
        var homeVal = r.isPct ? (r.home + '%') : r.home;
        var awayVal = r.isPct ? (r.away + '%') : r.away;
        var avgVal = r.isPct ? (avg + '%') : avg;

        var homeClass = r.home >= 60 ? 'high' : r.home >= 40 ? 'medium' : 'low';
        var awayClass = r.away >= 60 ? 'high' : r.away >= 40 ? 'medium' : 'low';

        html += '<tr><td>' + r.label + '</td><td class="' + homeClass + '">' + homeVal + '</td><td class="' + awayClass + '">' + awayVal + '</td><td>' + avgVal + '</td></tr>';
    }
    tbody.innerHTML = html;
}

function renderCornersTables(home, away, info) {
    // Corners en contra
    var cornersBody = document.getElementById('corners-table-body');
    var cornersHomeHeader = document.getElementById('corners-home-header');
    var cornersAwayHeader = document.getElementById('corners-away-header');

    if (cornersHomeHeader) cornersHomeHeader.textContent = info.home_short;
    if (cornersAwayHeader) cornersAwayHeader.textContent = info.away_short;

    if (cornersBody) {
        var rows = [
            { label: 'Corners/Partido', home: home.avg_corners, away: away.avg_corners },
            { label: 'Mas de 4.5', home: 70, away: 60, isPct: true },
            { label: 'Mas de 5.5', home: 55, away: 45, isPct: true },
            { label: 'Mas de 6.5', home: 40, away: 35, isPct: true },
            { label: 'Mas de 8.5', home: 25, away: 20, isPct: true },
        ];

        var html = '';
        for (var i = 0; i < rows.length; i++) {
            var r = rows[i];
            var avg = Math.round((r.home + r.away) / 2);
            var homeVal = r.isPct ? (r.home + '%') : r.home;
            var awayVal = r.isPct ? (r.away + '%') : r.away;
            var avgVal = r.isPct ? (avg + '%') : avg;

            var homeClass = r.home >= 60 ? 'high' : r.home >= 40 ? 'medium' : 'low';
            var awayClass = r.away >= 60 ? 'high' : r.away >= 40 ? 'medium' : 'low';

            html += '<tr><td>' + r.label + '</td><td class="' + homeClass + '">' + homeVal + '</td><td class="' + awayClass + '">' + awayVal + '</td><td>' + avgVal + '</td></tr>';
        }
        cornersBody.innerHTML = html;
    }

    // Total corners
    var totalCornersBody = document.getElementById('total-corners-body');
    if (totalCornersBody) {
        var totalRows = [
            { label: 'Mas de 7.5', home: 75, away: 70 },
            { label: 'Mas de 8.5', home: 65, away: 60 },
            { label: 'Mas de 9.5', home: 55, away: 50 },
            { label: 'Mas de 10.5', home: 45, away: 40 },
            { label: 'Mas de 11.5', home: 35, away: 30 },
        ];

        var html2 = '';
        for (var j = 0; j < totalRows.length; j++) {
            var tr = totalRows[j];
            var avg = Math.round((tr.home + tr.away) / 2);
            var homeClass = tr.home >= 60 ? 'high' : tr.home >= 40 ? 'medium' : 'low';
            var awayClass = tr.away >= 60 ? 'high' : tr.away >= 40 ? 'medium' : 'low';

            html2 += '<tr><td>' + tr.label + '</td><td class="' + homeClass + '">' + tr.home + '%</td><td class="' + awayClass + '">' + tr.away + '%</td><td>' + avg + '%</td></tr>';
        }
        totalCornersBody.innerHTML = html2;
    }
}

function renderCardsTable(home, away, info) {
    var tbody = document.getElementById('cards-table-body');
    var homeHeader = document.getElementById('cards-home-header');
    var awayHeader = document.getElementById('cards-away-header');

    if (homeHeader) homeHeader.textContent = info.home_short;
    if (awayHeader) awayHeader.textContent = info.away_short;
    if (!tbody) return;

    var rows = [
        { label: 'Tarjetas/Partido', home: home.avg_cards, away: away.avg_cards },
        { label: 'Mas de 2.5', home: 80, away: 75, isPct: true },
        { label: 'Mas de 3.5', home: 65, away: 60, isPct: true },
        { label: 'Mas de 4.5', home: 50, away: 45, isPct: true },
        { label: 'Mas de 5.5', home: 35, away: 30, isPct: true },
    ];

    var html = '';
    for (var i = 0; i < rows.length; i++) {
        var r = rows[i];
        var avg = Math.round((r.home + r.away) / 2);
        var homeVal = r.isPct ? (r.home + '%') : r.home;
        var awayVal = r.isPct ? (r.away + '%') : r.away;
        var avgVal = r.isPct ? (avg + '%') : avg;

        var homeClass = r.home >= 60 ? 'high' : r.home >= 40 ? 'medium' : 'low';
        var awayClass = r.away >= 60 ? 'high' : r.away >= 40 ? 'medium' : 'low';

        html += '<tr><td>' + r.label + '</td><td class="' + homeClass + '">' + homeVal + '</td><td class="' + awayClass + '">' + awayVal + '</td><td>' + avgVal + '</td></tr>';
    }
    tbody.innerHTML = html;
}

// ============ INIT ============
updateDateDisplay();
loadMatches();
