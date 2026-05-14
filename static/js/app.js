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

function formatLocalTime(dateString) {
  if (!dateString) return '--:--';
  var date = new Date(dateString.replace(' ', 'T'));
  if (isNaN(date.getTime())) return dateString.slice(11, 16) || '--:--';
  return date.toLocaleTimeString('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  });
}

function num(value, fallback) {
  var n = parseFloat(value);
  return isNaN(n) ? (fallback || 0) : n;
}

function pct(value) {
  if (value === null || value === undefined || value === '') return '0%';
  return num(value, 0).toFixed(0) + '%';
}

function dec(value) {
  if (value === null || value === undefined || value === '') return '0.00';
  return num(value, 0).toFixed(2);
}

function valueOrNoData(value, suffix) {
  if (value === null || value === undefined || value === '') return 'Sin datos';
  return String(value) + (suffix || '');
}

function updateDateDisplay() {
  getEl('current-date').textContent = formatDate(currentDate);
  getEl('date-picker').value = formatDateISO(currentDate);
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

function showMatches() {
  getEl('matches-section').classList.remove('hidden');
  getEl('analysis-section').classList.add('hidden');
  document.querySelector('.date-selector').classList.remove('hidden');
  document.querySelector('.league-filters').classList.remove('hidden');
  document.querySelector('.app-header').classList.remove('hidden');
  window.scrollTo(0, 0);
}

function showAnalysis() {
  getEl('matches-section').classList.add('hidden');
  getEl('analysis-section').classList.remove('hidden');
  document.querySelector('.date-selector').classList.add('hidden');
  document.querySelector('.league-filters').classList.add('hidden');
  document.querySelector('.app-header').classList.add('hidden');
  window.scrollTo(0, 0);
}

function setupEventListeners() {
  getEl('prev-date').addEventListener('click', function () {
    currentDate.setDate(currentDate.getDate() - 1);
    updateDateDisplay();
    loadMatches();
  });

  getEl('next-date').addEventListener('click', function () {
    currentDate.setDate(currentDate.getDate() + 1);
    updateDateDisplay();
    loadMatches();
  });

  getEl('current-date').addEventListener('click', function () {
    var picker = getEl('date-picker');
    if (picker.showPicker) picker.showPicker();
    else picker.focus();
  });

  getEl('date-picker').addEventListener('change', function (e) {
    currentDate = new Date(e.target.value + 'T12:00:00');
    updateDateDisplay();
    loadMatches();
  });

  var filterBtns = document.querySelectorAll('.filter-btn');
  for (var i = 0; i < filterBtns.length; i++) {
    filterBtns[i].addEventListener('click', function () {
      var allBtns = document.querySelectorAll('.filter-btn');
      for (var j = 0; j < allBtns.length; j++) allBtns[j].classList.remove('active');
      this.classList.add('active');
      currentFilter = this.dataset.filter || 'all';
      renderMatches();
    });
  }

  getEl('back-btn').addEventListener('click', showMatches);

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
  matchesContainer.innerHTML = '<div class="loading">Cargando partidos...</div>';

  fetch('/api/matches?date=' + encodeURIComponent(dateStr))
    .then(function (response) { return response.json(); })
    .then(function (data) {
      allMatches = Array.isArray(data.matches) ? data.matches : [];
      renderMatches();
    })
    .catch(function (e) {
      console.error(e);
      matchesContainer.innerHTML = '<div class="no-matches">Error cargando partidos</div>';
    });
}

function renderMatches() {
  var matchesContainer = getEl('matches-container');
  var matches = Array.isArray(allMatches) ? allMatches.slice() : [];

  if (currentFilter !== 'all') {
    matches = matches.filter(function (m) {
      var country = (m.country || '').toLowerCase();
      return country.indexOf(currentFilter.toLowerCase()) !== -1;
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

    html += ''
      + '<div class="match-card"'
      + ' data-match-id="' + (match.id || 0) + '"'
      + ' data-home-team="' + encodeURIComponent(home.name || 'Local') + '"'
      + ' data-away-team="' + encodeURIComponent(away.name || 'Visitante') + '"'
      + ' data-home-logo="' + encodeURIComponent(home.crest || '') + '"'
      + ' data-away-logo="' + encodeURIComponent(away.crest || '') + '"'
      + ' data-league="' + encodeURIComponent(match.league_name || '') + '"'
      + ' data-country="' + encodeURIComponent(match.country || '') + '"'
      + ' data-date="' + encodeURIComponent(match.matchDate || '') + '"'
      + ' data-time="' + encodeURIComponent(formatLocalTime(match.utcDate)) + '"'
      + ' data-venue="' + encodeURIComponent(match.venue || '') + '"'
      + ' data-home-score="' + (match.homeScore ?? '') + '"'
      + ' data-away-score="' + (match.awayScore ?? '') + '"'
      + ' data-xg-home="' + (match.xg_home ?? '') + '"'
      + ' data-xg-away="' + (match.xg_away ?? '') + '"'
      + ' data-xg-total="' + (match.xg_total ?? '') + '"'
      + ' data-odds-home="' + (match.odds_home ?? '') + '"'
      + ' data-odds-draw="' + (match.odds_draw ?? '') + '"'
      + ' data-odds-away="' + (match.odds_away ?? '') + '"'
      + ' data-prob-home="' + (match.prob_home ?? '') + '"'
      + ' data-prob-draw="' + (match.prob_draw ?? '') + '"'
      + ' data-prob-away="' + (match.prob_away ?? '') + '">'

      + '<div class="match-time-row">'
      + '<span class="match-time">' + formatLocalTime(match.utcDate) + '</span>'
      + '<span>' + (match.league_name || '') + '</span>'
      + '</div>'

      + '<div class="match-teams">'
      + '<div class="match-team"><img src="' + (home.crest || '') + '" onerror="this.style.display=\'none\'"><span>' + (home.name || 'Local') + '</span>' + (match.homeScore !== null && match.homeScore !== undefined ? '<span class="match-score">' + match.homeScore + '</span>' : '') + '</div>'
      + '<div class="match-team"><img src="' + (away.crest || '') + '" onerror="this.style.display=\'none\'"><span>' + (away.name || 'Visitante') + '</span>' + (match.awayScore !== null && match.awayScore !== undefined ? '<span class="match-score">' + match.awayScore + '</span>' : '') + '</div>'
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

  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.home_win) + '</div><div class="prob-box-label">1</div><div class="prob-box-sub">Victoria local</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.draw) + '</div><div class="prob-box-label">X</div><div class="prob-box-sub">Empate</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.away_win) + '</div><div class="prob-box-label">2</div><div class="prob-box-sub">Victoria visitante</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.over_1_5) + '</div><div class="prob-box-label">Más de 1.5</div><div class="prob-box-sub">Últimos partidos</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.over_2_5) + '</div><div class="prob-box-label">Más de 2.5</div><div class="prob-box-sub">Últimos partidos</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.btts) + '</div><div class="prob-box-label">AMB</div><div class="prob-box-sub">Últimos partidos</div></div>';

  getEl('prob-grid').innerHTML = html;
}

function renderMiniStats(data) {
  var hs = data.home_stats || {};
  var as = data.away_stats || {};
  var html = '';

  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrNoData(hs.played) + '</div><div class="mini-stat-label">Partidos local</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrNoData(as.played) + '</div><div class="mini-stat-label">Partidos visitante</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrNoData(hs.avg_team_goals) + '</div><div class="mini-stat-label">Goles local</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrNoData(as.avg_team_goals) + '</div><div class="mini-stat-label">Goles visitante</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + dec((data.probabilities || {}).home_xg) + '</div><div class="mini-stat-label">xG local</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + dec((data.probabilities || {}).away_xg) + '</div><div class="mini-stat-label">xG visitante</div></div>';

  getEl('mini-stats-grid').innerHTML = html;
}

function renderSeasonTable(data) {
  var hs = data.home_stats || {};
  var as = data.away_stats || {};

  getEl('season-home-header').textContent = (data.match_info && data.match_info.home_short) || 'Local';
  getEl('season-away-header').textContent = (data.match_info && data.match_info.away_short) || 'Visitante';

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
    html += '<tr><td>' + rows[i][0] + '</td><td>' + valueOrNoData(rows[i][1]) + '</td><td>' + valueOrNoData(rows[i][2]) + '</td></tr>';
  }

  getEl('season-table-body').innerHTML = html;
}

function renderGoalsTable(data) {
  var hs = data.home_stats || {};
  var as = data.away_stats || {};

  getEl('goals-home-header').textContent = (data.match_info && data.match_info.home_short) || 'Local';
  getEl('goals-away-header').textContent = (data.match_info && data.match_info.away_short) || 'Visitante';

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

  getEl('goals-table-body').innerHTML = html;
}

function renderSimpleUnavailableTables(data) {
  getEl('corners-home-header').textContent = (data.match_info && data.match_info.home_short) || 'Local';
  getEl('corners-away-header').textContent = (data.match_info && data.match_info.away_short) || 'Visitante';
  getEl('cards-home-header').textContent = (data.match_info && data.match_info.home_short) || 'Local';
  getEl('cards-away-header').textContent = (data.match_info && data.match_info.away_short) || 'Visitante';

  getEl('corners-table-body').innerHTML = '<tr><td>Corners</td><td>Sin datos</td><td>Sin datos</td><td>Sin datos</td></tr>';
  getEl('total-corners-body').innerHTML = '<tr><td>Total corners</td><td>Sin datos</td><td>Sin datos</td><td>Sin datos</td></tr>';
  getEl('cards-table-body').innerHTML = '<tr><td>Tarjetas</td><td>Sin datos</td><td>Sin datos</td><td>Sin datos</td></tr>';
}

function renderAnalysisText(data) {
  var hs = data.home_stats || {};
  var as = data.away_stats || {};
  var mi = data.match_info || {};
  var p = data.probabilities || {};
  var o = data.odds || {};

  var html = '';
  html += '<p><strong>' + (mi.home_team || 'Local') + '</strong> llega con racha ' + valueOrNoData(hs.form_string) + ' y media de ' + valueOrNoData(hs.avg_team_goals) + ' goles.</p>';
  html += '<p><strong>' + (mi.away_team || 'Visitante') + '</strong> llega con racha ' + valueOrNoData(as.form_string) + ' y media de ' + valueOrNoData(as.avg_team_goals) + ' goles.</p>';
  html += '<p>Cuotas 1X2: ' + dec(o.home) + ' / ' + dec(o.draw) + ' / ' + dec(o.away) + '. xG previo: ' + dec(p.home_xg) + ' - ' + dec(p.away_xg) + '.</p>';

  getEl('analysis-text-box').innerHTML = html;
}

function fillHeader(data) {
  var mi = data.match_info || {};
  getEl('analysis-subtitle').textContent = (mi.league || '') + (mi.country ? ' · ' + mi.country : '');
  getEl('home-name').textContent = mi.home_team || 'Local';
  getEl('away-name').textContent = mi.away_team || 'Visitante';
  getEl('home-logo').src = mi.home_logo || '';
  getEl('away-logo').src = mi.away_logo || '';
}

function openAnalysis(card) {
  var matchId = card.dataset.matchId || '0';

  var params = new URLSearchParams({
    home_team: decodeURIComponent(card.dataset.homeTeam || 'Local'),
    away_team: decodeURIComponent(card.dataset.awayTeam || 'Visitante'),
    home_logo: decodeURIComponent(card.dataset.homeLogo || ''),
    away_logo: decodeURIComponent(card.dataset.awayLogo || ''),
    league: decodeURIComponent(card.dataset.league || ''),
    date: decodeURIComponent(card.dataset.date || ''),
    time: decodeURIComponent(card.dataset.time || ''),
    country: decodeURIComponent(card.dataset.country || ''),
    venue: decodeURIComponent(card.dataset.venue || ''),
    home_score: card.dataset.homeScore || '',
    away_score: card.dataset.awayScore || '',
    xg_home: card.dataset.xgHome || '',
    xg_away: card.dataset.xgAway || '',
    xg_total: card.dataset.xgTotal || '',
    odds_home: card.dataset.oddsHome || '',
    odds_draw: card.dataset.oddsDraw || '',
    odds_away: card.dataset.oddsAway || '',
    prob_home: card.dataset.probHome || '',
    prob_draw: card.dataset.probDraw || '',
    prob_away: card.dataset.probAway || ''
  });

  showAnalysis();
  activateTab('resumen');
  getEl('analysis-text-box').innerHTML = 'Cargando análisis...';

  fetch('/api/analyze/' + matchId + '?' + params.toString())
    .then(function (response) { return response.json(); })
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
    .catch(function (e) {
      console.error(e);
      getEl('analysis-text-box').innerHTML = 'Error cargando análisis.';
    });
}

document.addEventListener('DOMContentLoaded', function () {
  updateDateDisplay();
  setupEventListeners();
  loadMatches();
});
