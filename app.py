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
  var year = date.getFullYear();
  var month = String(date.getMonth() + 1).padStart(2, '0');
  var day = String(date.getDate()).padStart(2, '0');
  return year + '-' + month + '-' + day;
}

function formatLocalTime(utcDateString) {
  if (!utcDateString) return '--:--';
  var date = new Date(utcDateString);
  return date.toLocaleTimeString('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  });
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
  var backBtn = getEl('back-btn');
  var filterBtns = document.querySelectorAll('.filter-btn');
  var tabBtns = document.querySelectorAll('.tab-btn');

  if (prevBtn) {
    prevBtn.addEventListener('click', function () {
      currentDate.setDate(currentDate.getDate() - 1);
      updateDateDisplay();
      loadMatches();
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', function () {
      currentDate.setDate(currentDate.getDate() + 1);
      updateDateDisplay();
      loadMatches();
    });
  }

  if (dateDisplay && datePicker) {
    dateDisplay.addEventListener('click', function () {
      if (datePicker.showPicker) {
        datePicker.showPicker();
      } else {
        datePicker.focus();
      }
    });

    datePicker.addEventListener('change', function (e) {
      currentDate = new Date(e.target.value + 'T12:00:00');
      updateDateDisplay();
      loadMatches();
    });
  }

  for (var i = 0; i < filterBtns.length; i++) {
    filterBtns[i].addEventListener('click', function () {
      var allBtns = document.querySelectorAll('.filter-btn');
      for (var j = 0; j < allBtns.length; j++) {
        allBtns[j].classList.remove('active');
      }
      this.classList.add('active');
      currentFilter = this.dataset.filter || 'all';
      renderMatches();
    });
  }

  if (backBtn) {
    backBtn.addEventListener('click', function () {
      showMatches();
    });
  }

  for (var k = 0; k < tabBtns.length; k++) {
    tabBtns[k].addEventListener('click', function () {
      activateTab(this.dataset.tab);
    });
  }
}

function activateTab(tabName) {
  var allTabs = document.querySelectorAll('.tab-btn');
  var allContents = document.querySelectorAll('.tab-content');

  for (var i = 0; i < allTabs.length; i++) {
    allTabs[i].classList.remove('active');
  }

  for (var j = 0; j < allContents.length; j++) {
    allContents[j].classList.remove('active');
  }

  var btn = document.querySelector('.tab-btn[data-tab="' + tabName + '"]');
  var content = getEl('tab-' + tabName);

  if (btn) btn.classList.add('active');
  if (content) content.classList.add('active');
}

function loadMatches() {
  var dateStr = formatDateISO(currentDate);
  var matchesContainer = getEl('matches-container');

  if (matchesContainer) {
    matchesContainer.innerHTML = '<div class="loading">Cargando partidos...</div>';
  }

  fetch('/api/matches?date=' + encodeURIComponent(dateStr))
    .then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.json();
    })
    .then(function (data) {
      if (data && Array.isArray(data.matches)) {
        allMatches = data.matches;
        allMatches.meta = {
          requestedDate: data.requested_date,
          sourceDate: data.source_date,
          isExact: data.is_exact
        };
      } else {
        throw new Error('Respuesta inválida');
      }

      renderMatches();
    })
    .catch(function (e) {
      console.error('Error cargando partidos:', e);
      if (matchesContainer) {
        matchesContainer.innerHTML =
          '<div class="no-matches">Error: ' + e.message + '<br><small>Intenta recargar</small></div>';
      }
    });
}

function renderMatches() {
  var matchesContainer = getEl('matches-container');
  if (!matchesContainer) return;

  var matches = Array.isArray(allMatches) ? allMatches.slice() : [];
  var meta = allMatches.meta || { isExact: true, sourceDate: null };

  if (currentFilter !== 'all') {
    matches = matches.filter(function (m) {
      var country = (m.country || '').toLowerCase();
      var league = (m.league_name || '').toLowerCase();
      var filter = currentFilter.toLowerCase();

      if (filter === 'spain') return country.indexOf('spain') !== -1 || country.indexOf('espa') !== -1;
      if (filter === 'england') return country.indexOf('england') !== -1 || country.indexOf('ingla') !== -1;

      return country.indexOf(filter) !== -1 || league.indexOf(filter) !== -1;
    });
  }

  if (!matches.length) {
    matchesContainer.innerHTML =
      '<div class="no-matches">No hay partidos para ' + formatDate(currentDate) +
      '<br><small>Prueba con otra fecha</small></div>';
    return;
  }

  matches.sort(function (a, b) {
    var statusOrder = { 'LIVE': 0, '1H': 0, 'HT': 0, '2H': 0, 'NS': 1, 'FT': 2, 'PST': 3, 'CANC': 4 };
    var orderA = statusOrder[a.status] !== undefined ? statusOrder[a.status] : 1;
    var orderB = statusOrder[b.status] !== undefined ? statusOrder[b.status] : 1;

    if (orderA !== orderB) return orderA - orderB;
    return (a.utcDate || '').localeCompare(b.utcDate || '');
  });

  var html = '';

  if (!meta.isExact && meta.sourceDate) {
    var sourceParts = meta.sourceDate.split('-');
    var sourceDateFormatted = sourceParts[2] + '/' + sourceParts[1] + '/' + sourceParts[0];
    html += '<div class="date-notice">Mostrando partidos del ' + sourceDateFormatted + ' porque no hay partidos para la fecha seleccionada</div>';
  }

  for (var i = 0; i < matches.length; i++) {
    var match = matches[i];
    var home = match.homeTeam || {};
    var away = match.awayTeam || {};
    var time = formatLocalTime(match.utcDate);
    var isLive = match.status === 'LIVE' || match.status === '1H' || match.status === '2H' || match.status === 'HT';
    var isFinished = match.status === 'FT';

    var statusBadge = '';
    if (isLive) {
      statusBadge = '<span class="status-badge live">LIVE</span>';
    } else if (isFinished) {
      statusBadge = '<span class="status-badge finished">FT</span>';
    }

    var scoreText = '';
    if (match.homeScore !== null && match.homeScore !== undefined && match.awayScore !== null && match.awayScore !== undefined) {
      scoreText = '<span class="match-score">' + match.homeScore + ' - ' + match.awayScore + '</span>';
    }

    var homeLogo = home.crest || ('https://crests.football-data.org/' + (home.id || 0) + '.svg');
    var awayLogo = away.crest || ('https://crests.football-data.org/' + (away.id || 0) + '.svg');

    html += '<div class="match-card ' + (isLive ? 'live' : '') + ' ' + (isFinished ? 'finished' : '') + '" data-match-id="' + match.id + '">';
    html += '  <div class="match-time-row">';
    html += '    <span class="match-time">' + time + '</span>';
    html +=      statusBadge;
    html +=      scoreText;
    html += '  </div>';
    html += '  <div class="match-teams">';
    html += '    <div class="match-team">';
    html += '      <img src="' + homeLogo + '" alt="" onerror="this.style.visibility=\'hidden\'">';
    html += '      <span>' + (home.shortName || home.name || 'Local') + '</span>';
    html += '    </div>';
    html += '    <div class="match-team">';
    html += '      <img src="' + awayLogo + '" alt="" onerror="this.style.visibility=\'hidden\'">';
    html += '      <span>' + (away.shortName || away.name || 'Visitante') + '</span>';
    html += '    </div>';
    html += '  </div>';
    html += '</div>';
  }

  matchesContainer.innerHTML = html;

  var cards = document.querySelectorAll('.match-card');
  for (var j = 0; j < cards.length; j++) {
    cards[j].addEventListener('click', function () {
      analyzeMatch(this.dataset.matchId);
    });
  }
}

function showMatches() {
  var matchesContainer = getEl('matches-container');
  var analysisSection = getEl('analysis-section');
  var ds = document.querySelector('.date-selector');
  var lf = document.querySelector('.league-filters');
  var ah = document.querySelector('.app-header');

  if (matchesContainer && matchesContainer.parentElement) {
    matchesContainer.parentElement.classList.remove('hidden');
  }
  if (analysisSection) analysisSection.classList.add('hidden');
  if (ds) ds.classList.remove('hidden');
  if (lf) lf.classList.remove('hidden');
  if (ah) ah.classList.remove('hidden');

  window.scrollTo(0, 0);
}

function showAnalysis() {
  var matchesContainer = getEl('matches-container');
  var analysisSection = getEl('analysis-section');
  var ds = document.querySelector('.date-selector');
  var lf = document.querySelector('.league-filters');
  var ah = document.querySelector('.app-header');

  if (matchesContainer && matchesContainer.parentElement) {
    matchesContainer.parentElement.classList.add('hidden');
  }
  if (analysisSection) analysisSection.classList.remove('hidden');
  if (ds) ds.classList.add('hidden');
  if (lf) lf.classList.add('hidden');
  if (ah) ah.classList.add('hidden');

  window.scrollTo(0, 0);
}

function analyzeMatch(matchId) {
  showAnalysis();
  activateTab('resumen');

  fetch('/api/analyze/' + matchId)
    .then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.json();
    })
    .then(function (data) {
      renderAnalysis(data);
    })
    .catch(function (e) {
      console.error('Error analizando partido:', e);
      alert('Error analizando partido: ' + e.message);
      showMatches();
    });
}

function renderAnalysis(data) {
  var info = data.match_info || {};
  var probs = data.probabilities || {};
  var homeStats = data.home_stats || {};
  var awayStats = data.away_stats || {};

  var subtitle = (info.league || '') + ' - ' + (info.date || '') + ' - ' + (info.time || '');
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

  renderFormBadges(data.home_form || [], 'home-form-badges');
  renderFormBadges(data.away_form || [], 'away-form-badges');
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
    var color = f.result === 'W' ? '#22c55e' : (f.result === 'D' ? '#eab308' : '#ef4444');
    html += '<div class="form-badge" style="background:' + color + '">' + f.result + '</div>';
  }
  container.innerHTML = html;
}

function renderProbGrid(probs, home, away) {
  var container = getEl('prob-grid');
  if (!container) return;

  var totalGoals = (((home.avg_total_goals || 0) + (away.avg_total_goals || 0)) / 2).toFixed(2);

  var items = [
    { label: 'Más de 2.5', value: probs.over_2_5 || 0, sub: 'Media de ' + totalGoals + ' goles' },
    { label: 'Más de 1.5', value: probs.over_1_5 || 0, sub: 'Over 1.5 goles' },
    { label: 'AMB', value: probs.btts || 0, sub: 'Ambos marcan' },
    { label: (home.avg_team_goals || 0).toFixed(2) + ' GF', value: '', sub: 'Local - Media goles' },
    { label: (away.avg_team_goals || 0).toFixed(2) + ' GF', value: '', sub: 'Visitante - Media goles' },
    { label: (probs.expected_cards || 0).toFixed(1) + ' Tarjetas', value: '', sub: 'Media tarjetas' },
    { label: (probs.expected_corners || 0).toFixed(1) + ' Corners', value: '', sub: 'Media corners' }
  ];

  var html = '';
  for (var i = 0; i < items.length; i++) {
    var item = items[i];
    html += '<div class="prob-box">';
    if (item.value !== '') {
      html += '<div class="prob-box-value">' + item.value + '%</div>';
    }
    html += '<div class="prob-box-label">' + item.label + '</div>';
    html += '<div class="prob-box-sub">' + item.sub + '</div>';
    html += '</div>';
  }

  container.innerHTML = html;
}

function getLevelClass(value) {
  if (value >= 60) return 'high';
  if (value >= 40) return 'medium';
  return 'low';
}

function renderGoalsTable(home, away, info) {
  var tbody = getEl('goals-table-body');
  var homeHeader = getEl('goals-home-header');
  var awayHeader = getEl('goals-away-header');

  if (homeHeader) homeHeader.textContent = info.home_short || 'Local';
  if (awayHeader) awayHeader.textContent = info.away_short || 'Visitante';
  if (!tbody) return;

  var rows = [
    { label: 'Goles/Partido', home: home.avg_total_goals || 0, away: away.avg_total_goals || 0, isPct: false },
    { label: 'Más de 1.5', home: home.over_1_5_pct || 0, away: away.over_1_5_pct || 0, isPct: true },
    { label: 'Más de 2.5', home: home.over_2_5_pct || 0, away: away.over_2_5_pct || 0, isPct: true },
    { label: 'Más de 3.5', home: home.over_3_5_pct || 0, away: away.over_3_5_pct || 0, isPct: true },
    { label: 'AMB', home: home.btts_pct || 0, away: away.btts_pct || 0, isPct: true }
  ];

  var html = '';
  for (var i = 0; i < rows.length; i++) {
    var r = rows[i];
    var avg = ((parseFloat(r.home) + parseFloat(r.away)) / 2).toFixed(r.isPct ? 0 : 1);
    var homeVal = r.isPct ? (r.home + '%') : r.home;
    var awayVal = r.isPct ? (r.away + '%') : r.away;

    html += '<tr>';
    html += '<td>' + r.label + '</td>';
    html += '<td class="' + getLevelClass(r.home) + '">' + homeVal + '</td>';
    html += '<td class="' + getLevelClass(r.away) + '">' + awayVal + '</td>';
    html += '<td>' + avg + (r.isPct ? '%' : '') + '</td>';
    html += '</tr>';
  }

  tbody.innerHTML = html;
}

function renderCornersTables(home, away, info) {
  var cornersBody = getEl('corners-table-body');
  var totalCornersBody = getEl('total-corners-body');
  var cornersHomeHeader = getEl('corners-home-header');
  var cornersAwayHeader = getEl('corners-away-header');

  if (cornersHomeHeader) cornersHomeHeader.textContent = info.home_short || 'Local';
  if (cornersAwayHeader) cornersAwayHeader.textContent = info.away_short || 'Visitante';

  if (cornersBody) {
    var rows = [
      { label: 'Corners/Partido', home: home.avg_corners || 5, away: away.avg_corners || 4.5, isPct: false },
      { label: 'Más de 4.5', home: 70, away: 60, isPct: true },
      { label: 'Más de 5.5', home: 55, away: 45, isPct: true },
      { label: 'Más de 6.5', home: 40, away: 35, isPct: true },
      { label: 'Más de 8.5', home: 25, away: 20, isPct: true }
    ];

    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      var avg = ((parseFloat(r.home) + parseFloat(r.away)) / 2).toFixed(r.isPct ? 0 : 1);
      var homeVal = r.isPct ? (r.home + '%') : r.home;
      var awayVal = r.isPct ? (r.away + '%') : r.away;

      html += '<tr>';
      html += '<td>' + r.label + '</td>';
      html += '<td class="' + getLevelClass(r.home) + '">' + homeVal + '</td>';
      html += '<td class="' + getLevelClass(r.away) + '">' + awayVal + '</td>';
      html += '<td>' + avg + (r.isPct ? '%' : '') + '</td>';
      html += '</tr>';
    }
    cornersBody.innerHTML = html;
  }

  if (totalCornersBody) {
    var totalRows = [
      { label: 'Más de 7.5', home: 75, away: 70 },
      { label: 'Más de 8.5', home: 65, away: 60 },
      { label: 'Más de 9.5', home: 55, away: 50 },
      { label: 'Más de 10.5', home: 45, away: 40 },
      { label: 'Más de 11.5', home: 35, away: 30 }
    ];

    var html2 = '';
    for (var j = 0; j < totalRows.length; j++) {
      var tr = totalRows[j];
      var avg2 = Math.round((tr.home + tr.away) / 2);

      html2 += '<tr>';
      html2 += '<td>' + tr.label + '</td>';
      html2 += '<td class="' + getLevelClass(tr.home) + '">' + tr.home + '%</td>';
      html2 += '<td class="' + getLevelClass(tr.away) + '">' + tr.away + '%</td>';
      html2 += '<td>' + avg2 + '%</td>';
      html2 += '</tr>';
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
    { label: 'Tarjetas/Partido', home: home.avg_cards || 2.5, away: away.avg_cards || 2.3, isPct: false },
    { label: 'Más de 2.5', home: 80, away: 75, isPct: true },
    { label: 'Más de 3.5', home: 65, away: 60, isPct: true },
    { label: 'Más de 4.5', home: 50, away: 45, isPct: true },
    { label: 'Más de 5.5', home: 35, away: 30, isPct: true }
  ];

  var html = '';
  for (var i = 0; i < rows.length; i++) {
    var r = rows[i];
    var avg = ((parseFloat(r.home) + parseFloat(r.away)) / 2).toFixed(r.isPct ? 0 : 1);
    var homeVal = r.isPct ? (r.home + '%') : r.home;
    var awayVal = r.isPct ? (r.away + '%') : r.away;

    html += '<tr>';
    html += '<td>' + r.label + '</td>';
    html += '<td class="' + getLevelClass(r.home) + '">' + homeVal + '</td>';
    html += '<td class="' + getLevelClass(r.away) + '">' + awayVal + '</td>';
    html += '<td>' + avg + (r.isPct ? '%' : '') + '</td>';
    html += '</tr>';
  }

  tbody.innerHTML = html;
}

try {
  setupEventListeners();
  updateDateDisplay();
  loadMatches();
  console.log('INIT COMPLETE');
} catch (e) {
  console.error('INIT ERROR:', e);
  var mc = getEl('matches-container');
  if (mc) mc.innerHTML = '<div class="no-matches">Error: ' + e.message + '</div>';
}
