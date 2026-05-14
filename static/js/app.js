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

function valueOrDash(v) {
  if (v === null || v === undefined || v === '') return '-';
  return String(v);
}

function num(v) {
  var n = parseFloat(v);
  return isNaN(n) ? 0 : n;
}

function pct(v) {
  return num(v).toFixed(0) + '%';
}

function dec(v) {
  return num(v).toFixed(2);
}

function showMatches() {
  var matchesSection = getEl('matches-section');
  var analysisSection = getEl('analysis-section');
  if (matchesSection) matchesSection.classList.remove('hidden');
  if (analysisSection) analysisSection.classList.add('hidden');
}

function showAnalysis() {
  var matchesSection = getEl('matches-section');
  var analysisSection = getEl('analysis-section');
  if (matchesSection) matchesSection.classList.add('hidden');
  if (analysisSection) analysisSection.classList.remove('hidden');
}

function activateTab(tabName) {
  var tabs = document.querySelectorAll('.tab-btn');
  var contents = document.querySelectorAll('.tab-content');

  for (var i = 0; i < tabs.length; i++) tabs[i].classList.remove('active');
  for (var j = 0; j < contents.length; j++) contents[j].classList.remove('active');

  var tab = document.querySelector('.tab-btn[data-tab="' + tabName + '"]');
  var content = getEl('tab-' + tabName);
  if (tab) tab.classList.add('active');
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

  if (backBtn) backBtn.addEventListener('click', showMatches);

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
    .then(function (r) {
      if (!r.ok) return r.text().then(function (t) { throw new Error('HTTP ' + r.status + ' - ' + t); });
      return r.json();
    })
    .then(function (data) {
      allMatches = Array.isArray(data.matches) ? data.matches : [];
      renderMatches();
    })
    .catch(function (error) {
      if (matchesContainer) {
        matchesContainer.innerHTML = '<div class="no-matches">Error cargando partidos: ' + error.message + '</div>';
      }
    });
}

function renderMatches() {
  var matchesContainer = getEl('matches-container');
  if (!matchesContainer) return;

  var matches = allMatches.slice();

  if (currentFilter !== 'all') {
    matches = matches.filter(function (m) {
      var text = ((m.country || '') + ' ' + (m.league_name || '')).toLowerCase();
      return text.indexOf(currentFilter.toLowerCase()) !== -1;
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
    var m = matches[i];
    var home = m.homeTeam || {};
    var away = m.awayTeam || {};
    var comp = m.competition || {};

    html += ''
      + '<div class="match-card"'
      + ' data-match-id="' + valueOrDash(m.id) + '"'
      + ' data-home-id="' + valueOrDash(home.id) + '"'
      + ' data-away-id="' + valueOrDash(away.id) + '"'
      + ' data-competition-id="' + valueOrDash(comp.id) + '"'
      + ' data-home-team="' + encodeURIComponent(home.name || 'Local') + '"'
      + ' data-away-team="' + encodeURIComponent(away.name || 'Visitante') + '"'
      + ' data-home-short="' + encodeURIComponent(home.shortName || home.name || 'Local') + '"'
      + ' data-away-short="' + encodeURIComponent(away.shortName || away.name || 'Visitante') + '"'
      + ' data-home-logo="' + encodeURIComponent(home.crest || '') + '"'
      + ' data-away-logo="' + encodeURIComponent(away.crest || '') + '"'
      + ' data-league="' + encodeURIComponent(m.league_name || '') + '"'
      + ' data-country="' + encodeURIComponent(m.country || '') + '"'
      + ' data-date="' + encodeURIComponent(m.matchDate || '') + '"'
      + ' data-time="' + encodeURIComponent(formatLocalTime(m.utcDate)) + '"'
      + ' data-venue="' + encodeURIComponent(m.venue || '') + '"'
      + ' data-home-score="' + (m.homeScore === null || m.homeScore === undefined ? '' : m.homeScore) + '"'
      + ' data-away-score="' + (m.awayScore === null || m.awayScore === undefined ? '' : m.awayScore) + '"'
      + ' data-matchday="' + valueOrDash(m.matchday || 0) + '"'
      + ' data-status="' + encodeURIComponent(m.statusText || 'SCHEDULED') + '">'

      + '<div class="match-time-row">'
      + '<span class="match-time">' + formatLocalTime(m.utcDate) + '</span>'
      + '<span>' + valueOrDash(m.league_name) + '</span>'
      + '</div>'

      + '<div class="match-teams">'
      + '<div class="match-team">'
      + '<img src="' + (home.crest || '') + '" onerror="this.style.display=\'none\'">'
      + '<span>' + valueOrDash(home.name) + '</span>'
      + (m.homeScore !== null && m.homeScore !== undefined ? '<span class="match-score">' + m.homeScore + '</span>' : '')
      + '</div>'

      + '<div class="match-team">'
      + '<img src="' + (away.crest || '') + '" onerror="this.style.display=\'none\'">'
      + '<span>' + valueOrDash(away.name) + '</span>'
      + (m.awayScore !== null && m.awayScore !== undefined ? '<span class="match-score">' + m.awayScore + '</span>' : '')
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

function formBadgeStyle(result) {
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
    html += '<div class="form-badge" style="' + formBadgeStyle(list[i].result) + '">' + list[i].result + '</div>';
  }
  el.innerHTML = html;
}

function renderProbabilities(data) {
  var p = data.probabilities || {};
  var html = '';

  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.over_1_5) + '</div><div class="prob-box-label">Más de 1.5</div><div class="prob-box-sub">Promedio de ambos</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.over_2_5) + '</div><div class="prob-box-label">Más de 2.5</div><div class="prob-box-sub">Promedio de ambos</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.over_3_5) + '</div><div class="prob-box-label">Más de 3.5</div><div class="prob-box-sub">Promedio de ambos</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.btts) + '</div><div class="prob-box-label">AMB</div><div class="prob-box-sub">Ambos marcan</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + dec(p.total_expected_goals) + '</div><div class="prob-box-label">Goles esperados</div><div class="prob-box-sub">Media ofensiva</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + dec(data.odds.home) + ' / ' + dec(data.odds.draw) + ' / ' + dec(data.odds.away) + '</div><div class="prob-box-label">Cuotas</div><div class="prob-box-sub">Si la API las trae</div></div>';

  var grid = getEl('prob-grid');
  if (grid) grid.innerHTML = html;
}

function renderMiniStats(data) {
  var hs = data.home_stats || {};
  var as = data.away_stats || {};
  var d = data.debug || {};
  var html = '';

  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrDash(hs.played) + '</div><div class="mini-stat-label">PJ local (' + valueOrDash(d.home_mode_used) + ')</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrDash(as.played) + '</div><div class="mini-stat-label">PJ visitante (' + valueOrDash(d.away_mode_used) + ')</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrDash(hs.avg_team_goals) + '</div><div class="mini-stat-label">Goles local</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrDash(as.avg_team_goals) + '</div><div class="mini-stat-label">Goles visitante</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + pct(hs.clean_sheet_pct) + '</div><div class="mini-stat-label">Portería a 0 local</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + pct(as.clean_sheet_pct) + '</div><div class="mini-stat-label">Portería a 0 visitante</div></div>';

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
    ['Posición', hs.position, as.position],
    ['Puntos', hs.points, as.points],
    ['PG', hs.won, as.won],
    ['PE', hs.draw, as.draw],
    ['PP', hs.lost, as.lost],
    ['GF', hs.goals_for, as.goals_for],
    ['GC', hs.goals_against, as.goals_against]
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
    ['Over 1.5', pct(hs.over_1_5_pct), pct(as.over_1_5_pct), pct((num(hs.over_1_5_pct) + num(as.over_1_5_pct)) / 2)],
    ['Over 2.5', pct(hs.over_2_5_pct), pct(as.over_2_5_pct), pct((num(hs.over_2_5_pct) + num(as.over_2_5_pct)) / 2)],
    ['Over 3.5', pct(hs.over_3_5_pct), pct(as.over_3_5_pct), pct((num(hs.over_3_5_pct) + num(as.over_3_5_pct)) / 2)],
    ['BTTS', pct(hs.btts_pct), pct(as.btts_pct), pct((num(hs.btts_pct) + num(as.btts_pct)) / 2)]
  ];

  var html = '';
  for (var i = 0; i < rows.length; i++) {
    html += '<tr><td>' + rows[i][0] + '</td><td>' + rows[i][1] + '</td><td>' + rows[i][2] + '</td><td>' + rows[i][3] + '</td></tr>';
  }

  var body = getEl('goals-table-body');
  if (body) body.innerHTML = html;
}

function renderEmptyOtherTables(data) {
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
  if (totalCornersBody) totalCornersBody.innerHTML = '<tr><td>Total</td><td>Sin datos</td><td>Sin datos</td><td>Sin datos</td></tr>';
  if (cardsBody) cardsBody.innerHTML = '<tr><td>Tarjetas</td><td>Sin datos</td><td>Sin datos</td><td>Sin datos</td></tr>';
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

function renderAnalysisText(data) {
  var hs = data.home_stats || {};
  var as = data.away_stats || {};
  var mi = data.match_info || {};
  var d = data.debug || {};

  var html = '';
  html += '<p><strong>' + valueOrDash(mi.home_team) + '</strong> llega con ' + valueOrDash(hs.played) + ' partidos usados y racha ' + valueOrDash(hs.form_string || 'Sin datos') + '.</p>';
  html += '<p><strong>' + valueOrDash(mi.away_team) + '</strong> llega con ' + valueOrDash(as.played) + ' partidos usados y racha ' + valueOrDash(as.form_string || 'Sin datos') + '.</p>';
  html += '<p>Modo local: ' + valueOrDash(d.home_mode_used) + '. Modo visitante: ' + valueOrDash(d.away_mode_used) + '.</p>';

  var box = getEl('analysis-text-box');
  if (box) box.innerHTML = html;
}

function openAnalysis(card) {
  var matchId = card.dataset.matchId;

  var params = new URLSearchParams({
    home_id: card.dataset.homeId,
    away_id: card.dataset.awayId,
    competition_id: card.dataset.competitionId,
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

  showAnalysis();
  activateTab('resumen');

  var box = getEl('analysis-text-box');
  if (box) box.innerHTML = 'Cargando análisis...';

  fetch('/api/analyze/' + encodeURIComponent(matchId) + '?' + params.toString())
    .then(function (r) {
      if (!r.ok) return r.text().then(function (t) { throw new Error('HTTP ' + r.status + ' - ' + t); });
      return r.json();
    })
    .then(function (data) {
      fillHeader(data);
      renderFormBadges(data.home_form || [], 'home-form-badges');
      renderFormBadges(data.away_form || [], 'away-form-badges');
      renderProbabilities(data);
      renderMiniStats(data);
      renderSeasonTable(data);
      renderGoalsTable(data);
      renderEmptyOtherTables(data);
      renderAnalysisText(data);
    })
    .catch(function (error) {
      if (box) box.innerHTML = 'Error cargando análisis: ' + error.message;
    });
}

document.addEventListener('DOMContentLoaded', function () {
  updateDateDisplay();
  setupEventListeners();
  loadMatches();
});
