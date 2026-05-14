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

function valueOrNoData(value, suffix) {
  if (value === null || value === undefined || value === '') return 'Sin datos';
  return String(value) + (suffix || '');
}

function updateDateDisplay() {
  var dateDisplay = getEl('current-date');
  var datePicker = getEl('date-picker');

  if (dateDisplay) dateDisplay.textContent = formatDate(currentDate);
  if (datePicker) datePicker.value = formatDateISO(currentDate);
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

function showMatches() {
  var matchesSection = getEl('matches-section');
  var analysisSection = getEl('analysis-section');
  var dateSelector = document.querySelector('.date-selector');
  var filters = document.querySelector('.league-filters');
  var header = document.querySelector('.app-header');

  if (matchesSection) matchesSection.classList.remove('hidden');
  if (analysisSection) analysisSection.classList.add('hidden');
  if (dateSelector) dateSelector.classList.remove('hidden');
  if (filters) filters.classList.remove('hidden');
  if (header) header.classList.remove('hidden');

  window.scrollTo(0, 0);
}

function showAnalysis() {
  var matchesSection = getEl('matches-section');
  var analysisSection = getEl('analysis-section');
  var dateSelector = document.querySelector('.date-selector');
  var filters = document.querySelector('.league-filters');
  var header = document.querySelector('.app-header');

  if (matchesSection) matchesSection.classList.add('hidden');
  if (analysisSection) analysisSection.classList.remove('hidden');
  if (dateSelector) dateSelector.classList.add('hidden');
  if (filters) filters.classList.add('hidden');
  if (header) header.classList.add('hidden');

  window.scrollTo(0, 0);
}

function setupEventListeners() {
  var prevBtn = getEl('prev-date');
  var nextBtn = getEl('next-date');
  var dateDisplay = getEl('current-date');
  var datePicker = getEl('date-picker');
  var filterBtns = document.querySelectorAll('.filter-btn');
  var backBtn = getEl('back-btn');
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
    backBtn.addEventListener('click', showMatches);
  }

  for (var k = 0; k < tabBtns.length; k++) {
    tabBtns[k].addEventListener('click', function () {
      activateTab(this.dataset.tab);
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
    .then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.json();
    })
    .then(function (data) {
      if (!data || !Array.isArray(data.matches)) {
        throw new Error('Respuesta inválida');
      }

      allMatches = data.matches;
      allMatches.meta = {
        requestedDate: data.requested_date,
        sourceDate: data.source_date,
        isExact: data.is_exact
      };

      renderMatches();
    })
    .catch(function (e) {
      console.error('Error cargando partidos:', e);
      if (matchesContainer) {
        matchesContainer.innerHTML =
          '<div class="no-matches">Error cargando partidos<br><small>' + e.message + '</small></div>';
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
      if (filter === 'italy') return country.indexOf('italy') !== -1 || country.indexOf('italia') !== -1;
      if (filter === 'germany') return country.indexOf('germany') !== -1 || country.indexOf('alemania') !== -1;
      if (filter === 'france') return country.indexOf('france') !== -1;
      if (filter === 'portugal') return country.indexOf('portugal') !== -1;
      if (filter === 'netherlands') return country.indexOf('netherlands') !== -1 || country.indexOf('holanda') !== -1;
      if (filter === 'brazil') return country.indexOf('brazil') !== -1 || country.indexOf('brasil') !== -1;

      return country.indexOf(filter) !== -1 || league.indexOf(filter) !== -1;
    });
  }

  matches.sort(function (a, b) {
    var statusOrder = { 'LIVE': 0, '1H': 0, 'HT': 0, '2H': 0, 'NS': 1, 'FT': 2, 'PST': 3, 'CANC': 4 };
    var orderA = statusOrder[a.status] !== undefined ? statusOrder[a.status] : 1;
    var orderB = statusOrder[b.status] !== undefined ? statusOrder[b.status] : 1;

    if (orderA !== orderB) return orderA - orderB;
    return (a.utcDate || '').localeCompare(b.utcDate || '');
  });

  if (!matches.length) {
    matchesContainer.innerHTML =
      '<div class="no-matches">No hay partidos para este filtro<br><small>Prueba otra fecha o otra liga</small></div>';
    return;
  }

  var html = '';

  if (!meta.isExact && meta.sourceDate) {
    var p = meta.sourceDate.split('-');
    var sourceFormatted = p[2] + '/' + p[1] + '/' + p[0];
    html += '<div class="date-notice">Mostrando partidos del ' + sourceFormatted + ' porque no hay partidos en la fecha elegida</div>';
  }

  for (var i = 0; i < matches.length; i++) {
    var match = matches[i];
    var home = match.homeTeam || {};
    var away = match.awayTeam || {};
    var time = formatLocalTime(match.utcDate);
    var isLive = match.status === 'LIVE' || match.status === '1H' || match.status === 'HT' || match.status === '2H';
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
    html += '<div class="match-time-row">';
    html += '<span class="match-time">' + time + '</span>';
    html += statusBadge;
    html += scoreText;
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

  matchesContainer.innerHTML = html;

  var cards = document.querySelectorAll('.match-card');
  for (var j = 0; j < cards.length; j++) {
    cards[j].addEventListener('click', function () {
      analyzeMatch(this.dataset.matchId);
    });
  }
}

function analyzeMatch(matchId) {
  showAnalysis();
  activateTab('resumen');

  var selected = null;
  for (var i = 0; i < allMatches.length; i++) {
    if (String(allMatches[i].id) === String(matchId)) {
      selected = allMatches[i];
      break;
    }
  }

  var params = new URLSearchParams();

  if (selected) {
    params.set('home_team', selected.homeTeam && selected.homeTeam.name ? selected.homeTeam.name : 'Local');
    params.set('away_team', selected.awayTeam && selected.awayTeam.name ? selected.awayTeam.name : 'Visitante');
    params.set('home_logo', selected.homeTeam && selected.homeTeam.crest ? selected.homeTeam.crest : '');
    params.set('away_logo', selected.awayTeam && selected.awayTeam.crest ? selected.awayTeam.crest : '');
    params.set('league', selected.league_name || '');
    params.set('date', selected.matchDate || '');
    params.set('time', formatLocalTime(selected.utcDate));
    params.set('country', selected.country || '');
  }

  fetch('/api/analyze/' + matchId + '?' + params.toString())
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

function renderFormBadges(form, elementId) {
  var container = getEl(elementId);
  if (!container) return;

  if (!form || !form.length) {
    container.innerHTML = '<div class="no-data-small">Sin datos</div>';
    return;
  }

  var html = '';
  for (var i = 0; i < form.length; i++) {
    var item = form[i];
    var bg = '#eab308';

    if (item.result === 'W') bg = '#22c55e';
    if (item.result === 'L') bg = '#ef4444';

    html += '<div class="form-badge" style="background:' + bg + '">' + item.result + '</div>';
  }

  container.innerHTML = html;
}

function getLevelClass(value) {
  var n = parseFloat(value);
  if (isNaN(n)) return '';
  if (n >= 60) return 'high';
  if (n >= 40) return 'medium';
  return 'low';
}

function renderProbGrid(probs, homeStats, awayStats) {
  var container = getEl('prob-grid');
  if (!container) return;

  var items = [
    { label: 'Más de 1.5', value: valueOrNoData(probs.over_1_5, '%'), sub: 'Temporada completa' },
    { label: 'Más de 2.5', value: valueOrNoData(probs.over_2_5, '%'), sub: 'Temporada completa' },
    { label: 'Más de 3.5', value: valueOrNoData(probs.over_3_5, '%'), sub: 'Temporada completa' },
    { label: 'AMB', value: valueOrNoData(probs.btts, '%'), sub: 'Ambos marcan' },
    { label: 'Goles esperados', value: valueOrNoData(probs.total_expected_goals, ''), sub: 'Cálculo local+visitante' },
    { label: 'Corners esperados', value: valueOrNoData(probs.expected_corners, ''), sub: 'Solo si la API lo da' },
    { label: 'Tarjetas esperadas', value: valueOrNoData(probs.expected_cards, ''), sub: 'Solo si la API lo da' },
    { label: 'Goles local', value: valueOrNoData(homeStats.avg_team_goals, ''), sub: 'Media temporada' },
    { label: 'Goles visitante', value: valueOrNoData(awayStats.avg_team_goals, ''), sub: 'Media temporada' }
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
  var tbody = getEl('goals-table-body');
  if (!tbody) return;

  var homeHeader = getEl('goals-home-header');
  var awayHeader = getEl('goals-away-header');
  if (homeHeader) homeHeader.textContent = info.home_short || 'Local';
  if (awayHeader) awayHeader.textContent = info.away_short || 'Visitante';

  var rows = [
    { label: 'Goles/Partido', home: home.avg_total_goals, away: away.avg_total_goals, pct: false },
    { label: 'Más de 1.5', home: home.over_1_5_pct, away: away.over_1_5_pct, pct: true },
    { label: 'Más de 2.5', home: home.over_2_5_pct, away: away.over_2_5_pct, pct: true },
    { label: 'Más de 3.5', home: home.over_3_5_pct, away: away.over_3_5_pct, pct: true },
    { label: 'AMB', home: home.btts_pct, away: away.btts_pct, pct: true },
    { label: 'Portería a cero', home: home.clean_sheet_pct, away: away.clean_sheet_pct, pct: true },
    { label: 'Sin marcar', home: home.failed_to_score_pct, away: away.failed_to_score_pct, pct: true }
  ];

  var html = '';
  for (var i = 0; i < rows.length; i++) {
    var r = rows[i];
    var homeVal = r.home ?? 0;
    var awayVal = r.away ?? 0;
    var avg = ((parseFloat(homeVal) + parseFloat(awayVal)) / 2).toFixed(r.pct ? 1 : 2);

    html += '<tr>';
    html += '<td>' + r.label + '</td>';
    html += '<td class="' + getLevelClass(homeVal) + '">' + homeVal + (r.pct ? '%' : '') + '</td>';
    html += '<td class="' + getLevelClass(awayVal) + '">' + awayVal + (r.pct ? '%' : '') + '</td>';
    html += '<td>' + avg + (r.pct ? '%' : '') + '</td>';
    html += '</tr>';
  }

  tbody.innerHTML = html;
}

function renderCornersTables(home, away, info) {
  var body1 = getEl('corners-table-body');
  var body2 = getEl('total-corners-body');

  var homeHeader = getEl('corners-home-header');
  var awayHeader = getEl('corners-away-header');
  if (homeHeader) homeHeader.textContent = info.home_short || 'Local';
  if (awayHeader) awayHeader.textContent = info.away_short || 'Visitante';

  if (body1) {
    body1.innerHTML =
      '<tr><td>Corners</td><td>Sin datos</td><td>Sin datos</td><td>API no disponible</td></tr>';
  }

  if (body2) {
    body2.innerHTML =
      '<tr><td>Total corners</td><td>Sin datos</td><td>Sin datos</td><td>API no disponible</td></tr>';
  }
}

function renderCardsTable(home, away, info) {
  var tbody = getEl('cards-table-body');
  if (!tbody) return;

  var homeHeader = getEl('cards-home-header');
  var awayHeader = getEl('cards-away-header');
  if (homeHeader) homeHeader.textContent = info.home_short || 'Local';
  if (awayHeader) awayHeader.textContent = info.away_short || 'Visitante';

  tbody.innerHTML =
    '<tr><td>Tarjetas</td><td>Sin datos</td><td>Sin datos</td><td>API no disponible</td></tr>';
}

function renderAnalysis(data) {
  var info = data.match_info || {};
  var probs = data.probabilities || {};
  var homeStats = data.home_stats || {};
  var awayStats = data.away_stats || {};

  var subtitleParts = [];
  if (info.league) subtitleParts.push(info.league);
  if (info.date) subtitleParts.push(info.date);
  if (info.time) subtitleParts.push(info.time);
  if (info.country) subtitleParts.push(info.country);

  var subtitle = subtitleParts.join(' - ');
  var subtitleEl = getEl('analysis-subtitle');
  if (subtitleEl) subtitleEl.textContent = subtitle;

  var homeName = getEl('home-name');
  var awayName = getEl('away-name');
  var homeLogo = getEl('home-logo');
  var awayLogo = getEl('away-logo');

  if (homeName) homeName.textContent = info.home_team || 'Local';
  if (awayName) awayName.textContent = info.away_team || 'Visitante';
  if (homeLogo) homeLogo.src = info.home_logo || '';
  if (awayLogo) awayLogo.src = info.away_logo || '';

  renderFormBadges(data.home_form || [], 'home-form-badges');
  renderFormBadges(data.away_form || [], 'away-form-badges');
  renderProbGrid(probs, homeStats, awayStats);
  renderGoalsTable(homeStats, awayStats, info);
  renderCornersTables(homeStats, awayStats, info);
  renderCardsTable(homeStats, awayStats, info);
}

try {
  setupEventListeners();
  updateDateDisplay();
  loadMatches();
  console.log('INIT COMPLETE');
} catch (e) {
  console.error('INIT ERROR:', e);
  var mc = getEl('matches-container');
  if (mc) {
    mc.innerHTML = '<div class="no-matches">Error: ' + e.message + '</div>';
  }
}
