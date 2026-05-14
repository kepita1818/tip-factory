// APP.JS LIMPIO - Sin caracteres especiales
console.log('APP START');

var currentDate = new Date();
var currentFilter = 'all';
var allMatches = [];

function getEl(id) {
    return document.getElementById(id);
}

function formatDate(date) {
    var d = date.getDate().toString().padStart(2, '0');
    var m = (date.getMonth() + 1).toString().padStart(2, '0');
    var y = date.getFullYear();
    return d + '/' + m + '/' + y;
}

function formatDateISO(date) {
    return date.toISOString().split('T')[0];
}

function formatLocalTime(utcDateString) {
    if (!utcDateString) return '--:--';
    var date = new Date(utcDateString);
    return date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function updateDateDisplay() {
    var dateDisplay = getEl('current-date');
    var datePicker = getEl('date-picker');
    if (dateDisplay) dateDisplay.textContent = formatDate(currentDate);
    if (datePicker) datePicker.value = formatDateISO(currentDate);
}

function setupEventListeners() {
    var prevBtn = getEl('prev-date');
    var nextBtn = getEl('next-date');
    var dateDisplay = getEl('current-date');
    var datePicker = getEl('date-picker');

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

    var filterBtns = document.querySelectorAll('.filter-btn');
    for (var i = 0; i < filterBtns.length; i++) {
        filterBtns[i].addEventListener('click', function() {
            var allBtns = document.querySelectorAll('.filter-btn');
            for (var j = 0; j < allBtns.length; j++) {
                allBtns[j].classList.remove('active');
            }
            this.classList.add('active');
            currentFilter = this.dataset.filter;
            renderMatches();
        });
    }

    var backBtn = getEl('back-btn');
    if (backBtn) {
        backBtn.addEventListener('click', showMatches);
    }

    var tabBtns = document.querySelectorAll('.tab-btn');
    for (var k = 0; k < tabBtns.length; k++) {
        tabBtns[k].addEventListener('click', function() {
            var allTabs = document.querySelectorAll('.tab-btn');
            var allContents = document.querySelectorAll('.tab-content');
            for (var t = 0; t < allTabs.length; t++) allTabs[t].classList.remove('active');
            for (var c = 0; c < allContents.length; c++) allContents[c].classList.remove('active');
            this.classList.add('active');
            var tabContent = getEl('tab-' + this.dataset.tab);
            if (tabContent) tabContent.classList.add('active');
        });
    }
}

function loadMatches() {
    var dateStr = formatDateISO(currentDate);
    var matchesContainer = getEl('matches-container');
    if (matchesContainer) {
        matchesContainer.innerHTML = '<div class="loading">Cargando partidos...</div>';
    }

    fetch('/api/matches?date=' + encodeURIComponent(dateStr))
        .then(function(response) {
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return response.json();
        })
        .then(function(data) {
            // Handle structured response {matches, requested_date, source_date, is_exact}
            if (data && data.matches && Array.isArray(data.matches)) {
                allMatches = data.matches;
                allMatches._meta = {
                    requestedDate: data.requested_date,
                    sourceDate: data.source_date,
                    isExact: data.is_exact
                };
            } else if (Array.isArray(data)) {
                allMatches = data;
                allMatches._meta = { isExact: true };
            } else {
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
    var matches = allMatches;
    var matchesContainer = getEl('matches-container');
    var meta = matches._meta || { isExact: true };

    // Show notice if showing matches from different date
    var dateNotice = '';
    if (!meta.isExact && meta.sourceDate) {
        var sourceDateParts = meta.sourceDate.split('-');
        var sourceDateFormatted = sourceDateParts[2] + '/' + sourceDateParts[1] + '/' + sourceDateParts[0];
        dateNotice = '<div class="date-notice">📅 Mostrando partidos del ' + sourceDateFormatted + ' (no hay partidos para la fecha seleccionada)</div>';
    }

    if (currentFilter !== 'all') {
        matches = matches.filter(function(m) {
            var country = (m.country || '').toLowerCase();
            var league = (m.league_name || '').toLowerCase();
            var filter = currentFilter.toLowerCase();
            return country.indexOf(filter) !== -1 || league.indexOf(filter) !== -1;
        });
    }

    if (!matches.length) {
        if (matchesContainer) matchesContainer.innerHTML = '<div class="no-matches">No hay partidos para este filtro</div>';
        return;
    }

    matches.sort(function(a, b) {
        var statusOrder = { '1H': 0, 'HT': 0, 'LIVE': 0, '2H': 0, 'NS': 1, 'FT': 2, 'PST': 3, 'CANC': 4 };
        var orderA = statusOrder[a.status] !== undefined ? statusOrder[a.status] : 1;
        var orderB = statusOrder[b.status] !== undefined ? statusOrder[b.status] : 1;
        if (orderA !== orderB) return orderA - orderB;
        return (a.utcDate || '').localeCompare(b.utcDate || '');
    });

    var html = dateNotice;
    for (var i = 0; i < matches.length; i++) {
        var match = matches[i];
        var home = match.homeTeam || {};
        var away = match.awayTeam || {};
        var time = formatLocalTime(match.utcDate);
        var isLive = match.status === '1H' || match.status === '2H' || match.status === 'HT' || match.status === 'LIVE';
        var isFinished = match.status === 'FT';

        var statusBadge = '';
        if (isLive) statusBadge = '<span class="status-badge live">LIVE ' + (match.minute || '') + '</span>';
        else if (isFinished) statusBadge = '<span class="status-badge finished">FT</span>';

        var scoreText = '';
        if (match.homeScore !== null && match.awayScore !== null) {
            scoreText = match.homeScore + ' - ' + match.awayScore;
        }

        var homeLogo = home.crest || 'https://crests.football-data.org/' + (home.id || 0) + '.svg';
        var awayLogo = away.crest || 'https://crests.football-data.org/' + (away.id || 0) + '.svg';

        html += '<div class="match-card ' + (isLive ? 'live ' : '') + (isFinished ? 'finished' : '') + '" data-match-id="' + match.id + '">';
        html += '<div class="match-time-row">';
        var matchDateStr = match.matchDate || '';
        var currentDateStr = formatDateISO(currentDate);
        if (matchDateStr && matchDateStr !== currentDateStr) {
            var mdParts = matchDateStr.split('-');
            html += '<span class="match-time">' + mdParts[2] + '/' + mdParts[1] + '</span>';
        } else {
            html += '<span class="match-time">' + time + '</span>';
        }
        html += statusBadge;
        if (scoreText) html += '<span class="match-score">' + scoreText + '</span>';
        html += '</div>';
        html += '<div class="match-teams">';
        html += '<div class="match-team">';
        html += '<img src="' + homeLogo + '" alt="" onerror="this.style.visibility=\'hidden\'">';
        html += '<span>' + (home.shortName || home.name || 'Local') + '</span>';
        html += '</div>';
        html += '<div class="match-team">';
        html += '<img src="' + awayLogo + '" alt="" onerror="this.style.visibility=\'hidden\'">';
        html += '<span>' + (away.shortName || away.name || 'Visitante') + '</span>';
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

function showMatches() {
    var matchesContainer = getEl('matches-container');
    if (matchesContainer && matchesContainer.parentElement) matchesContainer.parentElement.classList.remove('hidden');

    var ds = document.querySelector('.date-selector');
    var lf = document.querySelector('.league-filters');
    var ah = document.querySelector('.app-header');
    var analysisSection = getEl('analysis-section');

    if (ds) ds.classList.remove('hidden');
    if (lf) lf.classList.remove('hidden');
    if (ah) ah.classList.remove('hidden');
    if (analysisSection) analysisSection.classList.add('hidden');
    window.scrollTo(0, 0);
}

function showAnalysis() {
    var matchesContainer = getEl('matches-container');
    if (matchesContainer && matchesContainer.parentElement) matchesContainer.parentElement.classList.add('hidden');

    var ds = document.querySelector('.date-selector');
    var lf = document.querySelector('.league-filters');
    var ah = document.querySelector('.app-header');
    var analysisSection = getEl('analysis-section');

    if (ds) ds.classList.add('hidden');
    if (lf) lf.classList.add('hidden');
    if (ah) ah.classList.add('hidden');
    if (analysisSection) analysisSection.classList.remove('hidden');
    window.scrollTo(0, 0);
}

function analyzeMatch(matchId) {
    showAnalysis();

    var allTabs = document.querySelectorAll('.tab-btn');
    var allContents = document.querySelectorAll('.tab-content');
    for (var t = 0; t < allTabs.length; t++) allTabs[t].classList.remove('active');
    for (var c = 0; c < allContents.length; c++) allContents[c].classList.remove('active');

    var summaryTab = document.querySelector('[data-tab="resumen"]');
    var summaryContent = getEl('tab-resumen');
    if (summaryTab) summaryTab.classList.add('active');
    if (summaryContent) summaryContent.classList.add('active');

    fetch('/api/analyze/' + matchId)
        .then(function(response) {
            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('Partido no disponible. Los datos detallados pueden no estar incluidos en tu plan API.');
                }
                throw new Error('HTTP ' + response.status);
            }
            return response.json();
        })
        .then(function(data) {
            renderAnalysis(data);
        })
        .catch(function(e) {
            console.error('Error:', e);
            alert('Error analizando partido: ' + e.message);
            showMatches();
        });
}

function renderAnalysis(data) {
    var info = data.match_info || {};
    var probs = data.probabilities || {};
    var homeStats = data.home_stats || {};
    var awayStats = data.away_stats || {};

    var subtitle = info.league + ' - ' + info.date + ' - ' + info.time;
    if (info.venue) subtitle += ' - ' + info.venue;
    var analysisSubtitle = getEl('analysis-subtitle');
    if (analysisSubtitle) analysisSubtitle.textContent = subtitle;

    var homeNameEl = getEl('home-name');
    var awayNameEl = getEl('away-name');
    var homeLogoEl = getEl('home-logo');
    var awayLogoEl = getEl('away-logo');

    if (homeNameEl) homeNameEl.textContent = info.home_team || 'Local';
    if (awayNameEl) awayNameEl.textContent = info.away_team || 'Visitante';
    if (homeLogoEl) homeLogoEl.src = info.home_logo || '';
    if (awayLogoEl) awayLogoEl.src = info.away_logo || '';

    renderFormBadges(data.home_form, 'home-form-badges');
    renderFormBadges(data.away_form, 'away-form-badges');
    renderProbGrid(probs, homeStats, awayStats);
    renderGoalsTable(homeStats, awayStats, info);
    renderCornersTables(homeStats, awayStats, info);
    renderCardsTable(homeStats, awayStats, info);
}

function renderFormBadges(form, elementId) {
    var container = getEl(elementId);
    if (!container) return;

    if (!form || !form.length) {
        container.innerHTML = '<span class="no-data">Sin datos</span>';
        return;
    }

    var html = '';
    for (var i = 0; i < form.length; i++) {
        var f = form[i];
        var color = f.result === 'W' ? '#22c55e' : f.result === 'D' ? '#eab308' : '#ef4444';
        html += '<div class="form-badge" style="background:' + color + '">' + f.result + '</div>';
    }
    container.innerHTML = html;
}

function renderProbGrid(probs, home, away) {
    var container = getEl('prob-grid');
    if (!container) return;

    var totalGoals = ((home.avg_total_goals || 0) + (away.avg_total_goals || 0)) / 2;

    var items = [
        { label: 'Mas de 2.5', value: (probs.over_2_5 || 0) + '%', sub: 'Media de ' + totalGoals.toFixed(2) + ' goles' },
        { label: 'Mas de 1.5', value: (probs.over_1_5 || 0) + '%', sub: 'Over 1.5 goles' },
        { label: 'AMB', value: (probs.btts || 0) + '%', sub: 'Ambos marcan' },
        { label: (home.avg_team_goals || 0).toFixed(2) + ' GF', value: '', sub: 'Local - Media goles' },
        { label: (away.avg_team_goals || 0).toFixed(2) + ' GF', value: '', sub: 'Visitante - Media goles' },
        { label: (probs.expected_cards || 0).toFixed(2) + ' Tarjetas', value: '', sub: 'Media tarjetas' },
        { label: (probs.expected_corners || 0).toFixed(2) + ' Corners', value: '', sub: 'Media corners' },
    ];

    var html = '';
    for (var i = 0; i < items.length; i++) {
        var item = items[i];
        html += '<div class="prob-box">';
        if (item.value) html += '<div class="prob-box-value">' + item.value + '</div>';
        html += '<div class="prob-box-label">' + item.label + '</div>';
        html += '<div class="prob-box-sub">' + item.sub + '</div>';
        html += '</div>';
    }
    container.innerHTML = html;
}

function renderGoalsTable(home, away, info) {
    var tbody = getEl('goals-table-body');
    var homeHeader = getEl('goals-home-header');
    var awayHeader = getEl('goals-away-header');

    if (homeHeader) homeHeader.textContent = info.home_short || 'Local';
    if (awayHeader) awayHeader.textContent = info.away_short || 'Visitante';
    if (!tbody) return;

    var rows = [
        { label: 'Goles/Partido', home: home.avg_total_goals || 0, away: away.avg_total_goals || 0 },
        { label: 'Mas de 1.5', home: home.over_1_5_pct || 0, away: away.over_1_5_pct || 0, isPct: true },
        { label: 'Mas de 2.5', home: home.over_2_5_pct || 0, away: away.over_2_5_pct || 0, isPct: true },
        { label: 'Mas de 3.5', home: home.over_3_5_pct || 0, away: away.over_3_5_pct || 0, isPct: true },
        { label: 'AMB', home: home.btts_pct || 0, away: away.btts_pct || 0, isPct: true },
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
    var cornersBody = getEl('corners-table-body');
    var cornersHomeHeader = getEl('corners-home-header');
    var cornersAwayHeader = getEl('corners-away-header');

    if (cornersHomeHeader) cornersHomeHeader.textContent = info.home_short || 'Local';
    if (cornersAwayHeader) cornersAwayHeader.textContent = info.away_short || 'Visitante';

    if (cornersBody) {
        var rows = [
            { label: 'Corners/Partido', home: home.avg_corners || 5, away: away.avg_corners || 4.5 },
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

    var totalCornersBody = getEl('total-corners-body');
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
    var tbody = getEl('cards-table-body');
    var homeHeader = getEl('cards-home-header');
    var awayHeader = getEl('cards-away-header');

    if (homeHeader) homeHeader.textContent = info.home_short || 'Local';
    if (awayHeader) awayHeader.textContent = info.away_short || 'Visitante';
    if (!tbody) return;

    var rows = [
        { label: 'Tarjetas/Partido', home: home.avg_cards || 2.5, away: away.avg_cards || 2.3 },
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

// INIT
console.log('INIT START');
try {
    setupEventListeners();
    updateDateDisplay();
    loadMatches();
    console.log('INIT COMPLETE');
} catch(e) {
    console.error('INIT ERROR:', e);
    var mc = getEl('matches-container');
    if (mc) mc.innerHTML = '<div class="no-matches">Error: ' + e.message + '</div>';
}
