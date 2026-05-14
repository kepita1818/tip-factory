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
  if (isNaN(date.getTime())) return '--:--';
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

function num(value, fallback) {
  var n = parseFloat(value);
  return isNaN(n) ? (fallback || 0) : n;
}

function pct(value) {
  return num(value, 0).toFixed(0) + '%';
}

function dec(value) {
  return num(value, 0).toFixed(2);
}

function valueOrDash(value) {
  if (value === null || value === undefined || value === '') return '-';
  return String(value);
}

function showMatches() {
  var matchesSection = getEl('matches-section');
  var analysisSection = getEl('analysis-section');
  var dateSelector = document.querySelector('.date-selector');
  var leagueFilters = document.querySelector('.league-filters');
  var appHeader = document.querySelector('.app-header');

  if (matchesSection) matchesSection.classList.remove('hidden');
  if (analysisSection) analysisSection.classList.add('hidden');
  if (dateSelector) dateSelector.classList.remove('hidden');
  if (leagueFilters) leagueFilters.classList.remove('hidden');
  if (appHeader) appHeader.classList.remove('hidden');

  window.scrollTo(0, 0);
}

function showAnalysis() {
  var matchesSection = getEl('matches-section');
  var analysisSection = getEl('analysis-section');
  var dateSelector = document.querySelector('.date-selector');
  var leagueFilters = document.querySelector('.league-filters');
  var appHeader = document.querySelector('.app-header');

  if (matchesSection) matchesSection.classList.add('hidden');
  if (analysisSection) analysisSection.classList.remove('hidden');
  if (dateSelector) dateSelector.classList.add('hidden');
  if (leagueFilters) leagueFilters.classList.add('hidden');
  if (appHeader) appHeader.classList.add('hidden');

  window.scrollTo(0, 0);
}

function activateTab(tabName) {
  var allTabs = document.querySelectorAll('.tab-btn');
  var allContents = document.querySelectorAll('.tab-content');

  for (var i = 0; i < allTabs.length; i++) allTabs[i].classList.remove('active');
  for (var j = 0; j < allContents.length; j++) allContents[j].classList.remove('active');

  var btn = document.querySelector('.tab-btn[data-tab="' + tabName + '"]');
  var content = getEl('tab-' + tabName);

  if (btn) btn.classList.add('active');
  if (content) content.classList.add('active');
}

function setupEventListeners() {
  var prevBtn = getEl('prev-date');
  var nextBtn = getEl('next-date');
  var dateDisplay = getEl('current-date');
  var datePicker = getEl('date-picker');
  var backBtn = getEl('back-btn');

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
      if (datePicker.showPicker) datePicker.showPicker();
      else datePicker.focus();
    });

    datePicker.addEventListener('change', function (e) {
      currentDate = new Date(e.target.value + 'T12:00:00');
      updateDateDisplay();
      loadMatches();
    });
  }

  var filterBtns = document.querySelectorAll('.filter-btn');
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

  if (backBtn) backBtn.addEventListener('click', showMatches);

  var tabBtns = document.querySelectorAll('.tab-btn');
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
      if (!response.ok) {
        return response.text().then(function (txt) {
          throw new Error('HTTP ' + response.status + ' - ' + txt);
        });
      }
      return response.json();
    })
    .then(function (data) {
      allMatches = Array.isArray(data.matches) ? data.matches : [];
      renderMatches();
    })
    .catch(function (error) {
      console.error('Error cargando partidos:', error);
      if (matchesContainer) {
        matchesContainer.innerHTML = '<div class="no-matches">Error cargando partidos: ' + error.message + '</div>';
      }
    });
}

function renderMatches() {
  var matchesContainer = getEl('matches-container');
  if (!matchesContainer) return;

  var matches = Array.isArray(allMatches) ? allMatches.slice() : [];

  if (currentFilter !== 'all') {
    matches = matches.filter(function (m) {
      var country = (m.country || '').toLowerCase();
      var league = (m.league_name || '').toLowerCase();
      var filter = currentFilter.toLowerCase();
      return country.indexOf(filter) !== -1 || league.indexOf(filter) !== -1;
    });
  }

  matches.sort(function (a, b) {
    return (a.utcDate || '').localeCompare(b.utcDate || '');
  });

  if (!matches.length) {
    matchesContainer.innerHTML = '<div class="no-matches">No hay partidos para esta fecha</div>';
    return;
  }

  var html = '';

  for (var i = 0; i < matches.length; i++) {
    var match = matches[i];
    var home = match.homeTeam || {};
    var away = match.awayTeam || {};
    var competition = match.competition || {};

    html += ''
      + '<div class="match-card"'
      + ' data-match-id="' + valueOrDash(match.id) + '"'
      + ' data-home-id="' + valueOrDash(home.id) + '"'
      + ' data-away-id="' + valueOrDash(away.id) + '"'
      + ' data-competition-id="' + valueOrDash(competition.id) + '"'
      + ' data-home-team="' + encodeURIComponent(home.name || "Local") + '"'
      + ' data-away-team="' + encodeURIComponent(away.name || "Visitante") + '"'
      + ' data-home-short="' + encodeURIComponent(home.shortName || home.name || "Local") + '"'
      + ' data-away-short="' + encodeURIComponent(away.shortName || away.name || "Visitante") + '"'
      + ' data-home-logo="' + encodeURIComponent(home.crest || "") + '"'
      + ' data-away-logo="' + encodeURIComponent(away.crest || "") + '"'
      + ' data-league="' + encodeURIComponent(match.league_name || "") + '"'
      + ' data-country="' + encodeURIComponent(match.country || "") + '"'
      + ' data-date="' + encodeURIComponent(match.matchDate || "") + '"'
      + ' data-time="' + encodeURIComponent(formatLocalTime(match.utcDate)) + '"'
      + ' data-venue="' + encodeURIComponent(match.venue || "") + '"'
      + ' data-home-score="' + valueOrDash(match.homeScore === null ? "" : match.homeScore) + '"'
      + ' data-away-score="' + valueOrDash(match.awayScore === null ? "" : match.awayScore) + '"'
      + ' data-matchday="' + valueOrDash(match.matchday || 0) + '"'
      + ' data-status="' + encodeURIComponent(match.statusText || "SCHEDULED") + '">'

      + '<div class="match-time-row">'
      + '<span class="match-time">' + formatLocalTime(match.utcDate) + '</span>'
      + '<span>' + valueOrDash(match.league_name) + '</span>'
      + '</div>'

      + '<div class="match-teams">'
      + '<div class="match-team">'
      + '<img src="' + (home.crest || '') + '" onerror="this.style.display=\'none\'">'
      + '<span>' + valueOrDash(home.name) + '</span>'
      + (match.homeScore !== null && match.homeScore !== undefined ? '<span class="match-score">' + match.homeScore + '</span>' : '')
      + '</div>'

      + '<div class="match-team">'
      + '<img src="' + (away.crest || '') + '" onerror="this.style.display=\'none\'">'
      + '<span>' + valueOrDash(away.name) + '</span>'
      + (match.awayScore !== null && match.awayScore !== undefined ? '<span class="match-score">' + match.awayScore + '</span>' : '')
      + '</div>'
      + '</div>'
      + '</div>';
  }

  matchesContainer.innerHTML = html;

  var cards = document.querySelectorAll('.match-card');
  for (var c = 0; c < cards.length; c++) {
    cards[c].addEventListener('click', function () {
      openAnalysis(this);
    });
  }
}

function formBadgeClass(result) {
  if (result === 'W') return 'background:#22c55e;';
  if (result === 'D') return 'background:#eab308;color:#111;';
  return 'background:#ef4444;';
}

function renderFormBadges(list, elementId) {
  var el = getEl(elementId);
  if (!el) return;

  if (!list || !list.length) {
    el.innerHTML = '<span class="no-data-small">Sin datos</span>';
    return;
  }

  var html = '';
  for (var i = 0; i < list.length; i++) {
    html += '<div class="form-badge" style="' + formBadgeClass(list[i].result) + '">' + list[i].result + '</div>';
  }
  el.innerHTML = html;
}

function renderProbabilities(data) {
  var p = data.probabilities || {};
  var html = '';

  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.over_1_5) + '</div><div class="prob-box-label">Más de 1.5</div><div class="prob-box-sub">Últimos partidos</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.over_2_5) + '</div><div class="prob-box-label">Más de 2.5</div><div class="prob-box-sub">Últimos partidos</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.over_3_5) + '</div><div class="prob-box-label">Más de 3.5</div><div class="prob-box-sub">Últimos partidos</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.btts) + '</div><div class="prob-box-label">AMB</div><div class="prob-box-sub">Ambos marcan</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + dec(p.total_expected_goals) + '</div><div class="prob-box-label">Goles esperados</div><div class="prob-box-sub">Media</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + dec(p.home_xg) + ' - ' + dec(p.away_xg) + '</div><div class="prob-box-label">xG</div><div class="prob-box-sub">Local / Visitante</div></div>';

  var probGrid = getEl('prob-grid');
  if (probGrid) probGrid.innerHTML = html;
}

function renderMiniStats(data) {
  var hs = data.home_stats || {};
  var as = data.away_stats || {};
  var html = '';

  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrDash(hs.played) + '</div><div class="mini-stat-label">Partidos local</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrDash(as.played) + '</div><div class="mini-stat-label">Partidos visitante</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrDash(hs.avg_team_goals) + '</div><div class="mini-stat-label">Goles local</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrDash(as.avg_team_goals) + '</div><div class="mini-stat-label">Goles visitante</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrDash(hs.clean_sheet_pct) + '%</div><div class="mini-stat-label">Portería a 0 local</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrDash(as.clean_sheet_pct) + '%</div><div class="mini-stat-label">Portería a 0 visitante</div></div>';

  var grid = getEl('mini-stats-grid');
  if (grid) grid.innerHTML = html;
}

function renderSeasonTable(data) {
  var hs = data.home_stats || {};
  var as = data.away_stats || {};
  var mi = data.match_info || {};

  var homeHeader = getEl('season-home-header');
  var awayHeader = getEl('season-away-header');
  if (homeHeader) homeHeader.textContent = mi.home_short || 'Local';
  if (awayHeader) awayHeader.textContent = mi.away_short || 'Visitante';

  var rows = [
    ['PJ', hs.played, as.played],
    ['PG', hs.won, as.won],
    ['PE', hs.draw, as.draw],
    ['PP', hs.lost, as.lost],
    ['GF', hs.goals_for, as.goals_for],
    ['GC', hs.goals_against, as.goals_against],
    ['Puntos', hs.points, as.points],
    ['Media gol', hs.avg_team_goals, as.avg_team_goals],
    ['BTTS', pct(hs.btts_pct), pct(as.btts_pct)],
    ['Over 2.5', pct(hs.over_2_5_pct), pct(as.over_2_5_pct)]
  ];

  var html = '';
  for (var i = 0; i < rows.length; i++) {
    html += '<tr><td>' + rows[i][0] + '</td><td>' + valueOrDash(rows[i][1]) + '</td><td>' + valueOrDash(rows[i][2]) + '</td></tr>';
  }

  var body = getEl('season-table-body');
  if (body) body.innerHTML = html;
}

function renderGoalsTable(data) {
  var hs = data.home_stats || {};
  var as = data.away_stats || {};
  var mi = data.match_info || {};

  var homeHeader = getEl('goals-home-header');
  var awayHeader = getEl('goals-away-header');
  if (homeHeader) homeHeader.textContent = mi.home_short || 'Local';
  if (awayHeader) awayHeader.textContent = mi.away_short || 'Visitante';

  var rows = [
    ['Más de 1.5', pct(hs.over_1_5_pct), pct(as.over_1_5_pct), pct((num(hs.over_1_5_pct, 0) + num(as.over_1_5_pct, 0)) / 2)],
    ['Más de 2.5', pct(hs.over_2_5_pct), pct(as.over_2_5_pct), pct((num(hs.over_2_5_pct, 0) + num(as.over_2_5_pct, 0)) / 2)],
    ['Más de 3.5', pct(hs.over_3_5_pct), pct(as.over_3_5_pct), pct((num(hs.over_3_5_pct, 0) + num(as.over_3_5_pct, 0)) / 2)],
    ['AMB', pct(hs.btts_pct), pct(as.btts_pct), pct((num(hs.btts_pct, 0) + num(as.btts_pct, 0)) / 2)]
  ];

  var html = '';
  for (var i = 0; i < rows.length; i++) {
    html += '<tr><td>' + rows[i][0] + '</td><td>' + rows[i][1] + '</td><td>' + rows[i][2] + '</td><td>' + rows[i][3] + '</td></tr>';
  }

  var body = getEl('goals-table-body');
  if (body) body.innerHTML = html;
}

function renderSimpleUnavailableTables(data) {
  var mi = data.match_info || {};

  var cornersHome = getEl('corners-home-header');
  var cornersAway = getEl('corners-away-header');
  var cardsHome = getEl('cards-home-header');
  var cardsAway = getEl('cards-away-header');

  if (cornersHome) cornersHome.textContent = mi.home_short || 'Local';
  if (cornersAway) cornersAway.textContent = mi.away_short || 'Visitante';
  if (cardsHome) cardsHome.textContent = mi.home_short || 'Local';
  if (cardsAway) cardsAway.textContent = mi.away_short || 'Visitante';

  var cornersBody = getEl('corners-table-body');
  var totalCornersBody = getEl('total-corners-body');
  var cardsBody = getEl('cards-table-body');

  if (cornersBody) cornersBody.innerHTML = '<tr><td>Corners</td><td>Sin datos</td><td>Sin datos</td><td>Sin datos</td></tr>';
  if (totalCornersBody) totalCornersBody.innerHTML = '<tr><td>Total corners</td><td>Sin datos</td><td>Sin datos</td><td>Sin datos</td></tr>';
  if (cardsBody) cardsBody.innerHTML = '<tr><td>Tarjetas</td><td>Sin datos</td><td>Sin datos</td><td>Sin datos</td></tr>';
}

function renderAnalysisText(data) {
  var hs = data.home_stats || {};
  var as = data.away_stats || {};
  var mi = data.match_info || {};
  var debug = data.debug || {};

  var html = '';
  html += '<p><strong>' + valueOrDash(mi.home_team) + '</strong> llega con racha ' + valueOrDash(hs.form_string || 'Sin datos') + ' y media de ' + valueOrDash(hs.avg_team_goals) + ' goles.</p>';
  html += '<p><strong>' + valueOrDash(mi.away_team) + '</strong> llega con racha ' + valueOrDash(as.form_string || 'Sin datos') + ' y media de ' + valueOrDash(as.avg_team_goals) + ' goles.</p>';
  html += '<p>Competicion: ' + valueOrDash(mi.league) + ' · IDs ' + valueOrDash(debug.home_id) + ' vs ' + valueOrDash(debug.away_id) + '.</p>';

  var analysisBox = getEl('analysis-text-box');
  if (analysisBox) analysisBox.innerHTML = html;
}

function fillHeader(data) {
  var mi = data.match_info || {};

  var subtitle = getEl('analysis-subtitle');
  var homeName = getEl('home-name');
  var awayName = getEl('away-name');
  var homeLogo = getEl('home-logo');
  var awayLogo = getEl('away-logo');

  if (subtitle) subtitle.textContent = (mi.league || '') + (mi.country ? ' · ' + mi.country : '');
  if (homeName) homeName.textContent = mi.home_team || 'Local';
  if (awayName) awayName.textContent = mi.away_team || 'Visitante';
  if (homeLogo) homeLogo.src = mi.home_logo || '';
  if (awayLogo) awayLogo.src = mi.away_logo || '';
}

function openAnalysis(card) {
  if (!card) return;

  var matchId = card.dataset.matchId;
  var homeId = card.dataset.homeId;
  var awayId = card.dataset.awayId;
  var competitionId = card.dataset.competitionId;

  if (!matchId || !homeId || !awayId || !competitionId) {
    console.error('Faltan ids para analizar', { matchId: matchId, homeId: homeId, awayId: awayId, competitionId: competitionId });
    return;
  }

  showAnalysis();
  activateTab('resumen');

  var analysisBox = getEl('analysis-text-box');
  if (analysisBox) analysisBox.innerHTML = 'Cargando análisis...';

  var params = new URLSearchParams({
    home_id: homeId,
    away_id: awayId,
    competition_id: competitionId,
    home_team: decodeURIComponent(card.dataset.homeTeam || 'Local'),
    away_team: decodeURIComponent(card.dataset.awayTeam || 'Visitante'),
    home_short: decodeURIComponent(card.dataset.homeShort || 'Local'),
    away_short: decodeURIComponent(card.dataset.awayShort || 'Visitante'),
    home_logo: decodeURIComponent(card.dataset.homeLogo || ''),
    away_logo: decodeURIComponent(card.dataset.awayLogo || ''),
    league: decodeURIComponent(card.dataset.league || ''),
    country: decodeURIComponent(card.dataset.country || ''),
    date: decodeURIComponent(card.dataset.date || ''),
    time: decodeURIComponent(card.dataset.time || '--:--'),
    venue: decodeURIComponent(card.dataset.venue || ''),
    home_score: card.dataset.homeScore || '',
    away_score: card.dataset.awayScore || '',
    matchday: card.dataset.matchday || '0',
    status: decodeURIComponent(card.dataset.status || 'SCHEDULED')
  });

  fetch('/api/analyze/' + encodeURIComponent(matchId) + '?' + params.toString())
    .then(function (response) {
      if (!response.ok) {
        return response.text().then(function (txt) {
          throw new Error('HTTP ' + response.status + ' - ' + txt);
        });
      }
      return response.json();
    })
    .then(function (data) {
      console.log('ANALYSIS DATA', data);
      fillHeader(data);
      renderFormBadges(data.home_form || [], 'home-form-badges');
      renderFormBadges(data.away_form || [], 'away-form-badges');
      renderProbabilities(data);
      renderMiniStats(data);
      renderSeasonTable(data);
      renderGoalsTable(data);
      renderSimpleUnavailableTables(data);
      renderAnalysisText(data);
    })
    .catch(function (error) {
      console.error('Error cargando analisis:', error);
      if (analysisBox) analysisBox.innerHTML = 'Error cargando análisis: ' + error.message;
    });
}

document.addEventListener('DOMContentLoaded', function () {
  updateDateDisplay();
  setupEventListeners();
  loadMatches();
});
