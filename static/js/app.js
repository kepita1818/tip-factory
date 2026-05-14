console.log('APP START - TipFactory v9.1 - Mobile/League Groups');

var currentDate = new Date();
var allMatches = [];
var groupedMatches = {};

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
  window.scrollTo(0, 0);
}

function showAnalysis() {
  var matchesSection = getEl('matches-section');
  var analysisSection = getEl('analysis-section');
  if (matchesSection) matchesSection.classList.add('hidden');
  if (analysisSection) analysisSection.classList.remove('hidden');
  window.scrollTo(0, 0);
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

function groupMatchesByLeague(matches) {
  var groups = {};
  for (var i = 0; i < matches.length; i++) {
    var m = matches[i];
    var leagueName = m.league_name || 'Otras Ligas';
    var country = m.country || '';
    var key = leagueName + '|' + country;

    if (!groups[key]) {
      groups[key] = {
        league_name: leagueName,
        country: country,
        matches: []
      };
    }
    groups[key].matches.push(m);
  }

  // Sort matches within each group by time
  for (var key in groups) {
    groups[key].matches.sort(function (a, b) {
      return (a.utcDate || '').localeCompare(b.utcDate || '');
    });
  }

  return groups;
}

function renderMatches() {
  var matchesContainer = getEl('matches-container');
  if (!matchesContainer) return;

  if (!allMatches.length) {
    matchesContainer.innerHTML = '<div class="no-matches">No hay partidos para esta fecha</div>';
    return;
  }

  var groups = groupMatchesByLeague(allMatches);
  var html = '';

  // Sort groups by priority (top leagues first)
  var priorityLeagues = [
    'Premier League', 'La Liga', 'Serie A', 'Bundesliga', 'Ligue 1',
    'Champions League', 'Europa League', 'Conference League',
    'Primeira Liga', 'Eredivisie', 'Brasileirao', 'Liga MX', 'MLS',
    'Copa Libertadores', 'Copa Sudamericana', 'Liga Argentina', 'Liga Colombia'
  ];

  var sortedKeys = Object.keys(groups).sort(function (a, b) {
    var leagueA = groups[a].league_name;
    var leagueB = groups[b].league_name;
    var idxA = priorityLeagues.indexOf(leagueA);
    var idxB = priorityLeagues.indexOf(leagueB);

    if (idxA !== -1 && idxB !== -1) return idxA - idxB;
    if (idxA !== -1) return -1;
    if (idxB !== -1) return 1;
    return leagueA.localeCompare(leagueB);
  });

  for (var g = 0; g < sortedKeys.length; g++) {
    var group = groups[sortedKeys[g]];
    var leagueDisplay = group.league_name + (group.country ? ' · ' + group.country : '');

    html += '<div class="league-group">';
    html += '<div class="league-header">' + leagueDisplay + '</div>';
    html += '<div class="league-matches">';

    for (var i = 0; i < group.matches.length; i++) {
      var m = group.matches[i];
      var home = m.homeTeam || {};
      var away = m.awayTeam || {};
      var comp = m.competition || {};
      var timeStr = formatLocalTime(m.utcDate);
      var isLive = m.status === '1H' || m.status === '2H' || m.status === 'HT' || m.status === 'ET';
      var isFinished = m.status === 'FT' || m.status === 'AET' || m.status === 'PEN';

      html += '<div class="match-card"'
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
        + ' data-time="' + encodeURIComponent(timeStr) + '"'
        + ' data-venue="' + encodeURIComponent(m.venue || '') + '"'
        + ' data-home-score="' + (m.homeScore === null || m.homeScore === undefined ? '' : m.homeScore) + '"'
        + ' data-away-score="' + (m.awayScore === null || m.awayScore === undefined ? '' : m.awayScore) + '"'
        + ' data-matchday="' + valueOrDash(m.matchday || 0) + '"'
        + ' data-status="' + encodeURIComponent(m.statusText || 'SCHEDULED') + '">';

      // Time row
      html += '<div class="match-time-row">';
      if (isLive) {
        html += '<span class="match-time live">' + timeStr + ' LIVE</span>';
      } else if (isFinished) {
        html += '<span class="match-time finished">FT</span>';
      } else {
        html += '<span class="match-time">' + timeStr + '</span>';
      }
      html += '</div>';

      // Teams row - compact mobile style
      html += '<div class="match-teams">';

      // Home team
      html += '<div class="match-team">';
      html += '<img src="' + (home.crest || '') + '" alt="" onerror="this.style.display=\'none\'">';
      html += '<span class="team-name">' + valueOrDash(home.name) + '</span>';
      if (m.homeScore !== null && m.homeScore !== undefined) {
        html += '<span class="match-score">' + m.homeScore + '</span>';
      }
      html += '</div>';

      // Away team
      html += '<div class="match-team">';
      html += '<img src="' + (away.crest || '') + '" alt="" onerror="this.style.display=\'none\'">';
      html += '<span class="team-name">' + valueOrDash(away.name) + '</span>';
      if (m.awayScore !== null && m.awayScore !== undefined) {
        html += '<span class="match-score">' + m.awayScore + '</span>';
      }
      html += '</div>';

      html += '</div>'; // end match-teams
      html += '</div>'; // end match-card
    }

    html += '</div>'; // end league-matches
    html += '</div>'; // end league-group
  }

  matchesContainer.innerHTML = html;

  // Add click listeners
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
  var pred = data.predictions || {};
  var html = '';

  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.over_1_5) + '</div><div class="prob-box-label">Más de 1.5</div><div class="prob-box-sub">Promedio de ambos</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.over_2_5) + '</div><div class="prob-box-label">Más de 2.5</div><div class="prob-box-sub">Promedio de ambos</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.over_3_5) + '</div><div class="prob-box-label">Más de 3.5</div><div class="prob-box-sub">Promedio de ambos</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + pct(p.btts) + '</div><div class="prob-box-label">AMB</div><div class="prob-box-sub">Ambos marcan</div></div>';
  html += '<div class="prob-box"><div class="prob-box-value">' + dec(p.total_expected_goals) + '</div><div class="prob-box-label">Goles esperados</div><div class="prob-box-sub">Media ofensiva</div></div>';

  if (pred && pred.advice) {
    html += '<div class="prob-box"><div class="prob-box-value">' + (pred.winner || '-') + '</div><div class="prob-box-label">Predicción</div><div class="prob-box-sub">' + pred.advice + '</div></div>';
  } else {
    html += '<div class="prob-box"><div class="prob-box-value">' + dec(data.odds.home) + ' / ' + dec(data.odds.draw) + ' / ' + dec(data.odds.away) + '</div><div class="prob-box-label">Probabilidades</div><div class="prob-box-sub">Home / Draw / Away</div></div>';
  }

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

function renderCornersTable(data) {
  var hs = data.home_stats || {};
  var as = data.away_stats || {};
  var mi = data.match_info || {};
  var fixtureStats = data.fixture_statistics || {};
  var homeFixture = fixtureStats.home || {};
  var awayFixture = fixtureStats.away || {};

  var cornersHome = getEl('corners-home-header');
  var cornersAway = getEl('corners-away-header');
  if (cornersHome) cornersHome.textContent = mi.home_short || 'Local';
  if (cornersAway) cornersAway.textContent = mi.away_short || 'Visitante';

  var rows = [
    ['Corners totales', valueOrDash(hs.corners_total), valueOrDash(as.corners_total), valueOrDash((num(hs.corners_total) + num(as.corners_total)) / 2)],
    ['Corners por partido', dec(hs.avg_corners), dec(as.avg_corners), dec((num(hs.avg_corners) + num(as.avg_corners)) / 2)],
  ];

  if (homeFixture.corners || awayFixture.corners) {
    rows.push(['Corners en este partido', valueOrDash(homeFixture.corners), valueOrDash(awayFixture.corners), valueOrDash((num(homeFixture.corners) + num(awayFixture.corners)) / 2)]);
  }

  var html = '';
  for (var i = 0; i < rows.length; i++) {
    html += '<tr><td>' + rows[i][0] + '</td><td>' + rows[i][1] + '</td><td>' + rows[i][2] + '</td><td>' + rows[i][3] + '</td></tr>';
  }

  var body = getEl('corners-table-body');
  if (body) body.innerHTML = html;

  var totalCornersBody = getEl('total-corners-body');
  if (totalCornersBody) {
    var avgCorners = (num(hs.avg_corners) + num(as.avg_corners)) / 2;
    var totalHtml = '';
    totalHtml += '<tr><td>Over 8.5</td><td>' + pct(hs.avg_corners > 8.5 ? 50 : 30) + '</td><td>' + pct(as.avg_corners > 8.5 ? 50 : 30) + '</td><td>' + pct(avgCorners > 8.5 ? 50 : 30) + '</td></tr>';
    totalHtml += '<tr><td>Over 9.5</td><td>' + pct(hs.avg_corners > 9.5 ? 45 : 25) + '</td><td>' + pct(as.avg_corners > 9.5 ? 45 : 25) + '</td><td>' + pct(avgCorners > 9.5 ? 45 : 25) + '</td></tr>';
    totalHtml += '<tr><td>Over 10.5</td><td>' + pct(hs.avg_corners > 10.5 ? 40 : 20) + '</td><td>' + pct(as.avg_corners > 10.5 ? 40 : 20) + '</td><td>' + pct(avgCorners > 10.5 ? 40 : 20) + '</td></tr>';
    totalHtml += '<tr><td>Over 11.5</td><td>' + pct(hs.avg_corners > 11.5 ? 35 : 15) + '</td><td>' + pct(as.avg_corners > 11.5 ? 35 : 15) + '</td><td>' + pct(avgCorners > 11.5 ? 35 : 15) + '</td></tr>';
    totalCornersBody.innerHTML = totalHtml;
  }
}

function renderCardsTable(data) {
  var hs = data.home_stats || {};
  var as = data.away_stats || {};
  var mi = data.match_info || {};
  var fixtureStats = data.fixture_statistics || {};
  var homeFixture = fixtureStats.home || {};
  var awayFixture = fixtureStats.away || {};

  var cardsHome = getEl('cards-home-header');
  var cardsAway = getEl('cards-away-header');
  if (cardsHome) cardsHome.textContent = mi.home_short || 'Local';
  if (cardsAway) cardsAway.textContent = mi.away_short || 'Visitante';

  var rows = [
    ['Tarjetas amarillas', valueOrDash(hs.yellow_cards), valueOrDash(as.yellow_cards), valueOrDash((num(hs.yellow_cards) + num(as.yellow_cards)) / 2)],
    ['Tarjetas rojas', valueOrDash(hs.red_cards), valueOrDash(as.red_cards), valueOrDash((num(hs.red_cards) + num(as.red_cards)) / 2)],
    ['Amarillas por partido', dec(hs.avg_yellow_cards), dec(as.avg_yellow_cards), dec((num(hs.avg_yellow_cards) + num(as.avg_yellow_cards)) / 2)],
    ['Rojas por partido', dec(hs.avg_red_cards), dec(as.avg_red_cards), dec((num(hs.avg_red_cards) + num(as.avg_red_cards)) / 2)],
  ];

  if (homeFixture.yellow_cards || awayFixture.yellow_cards) {
    rows.push(['Amarillas en este partido', valueOrDash(homeFixture.yellow_cards), valueOrDash(awayFixture.yellow_cards), valueOrDash((num(homeFixture.yellow_cards) + num(awayFixture.yellow_cards)) / 2)]);
  }
  if (homeFixture.red_cards || awayFixture.red_cards) {
    rows.push(['Rojas en este partido', valueOrDash(homeFixture.red_cards), valueOrDash(awayFixture.red_cards), valueOrDash((num(homeFixture.red_cards) + num(awayFixture.red_cards)) / 2)]);
  }

  var html = '';
  for (var i = 0; i < rows.length; i++) {
    html += '<tr><td>' + rows[i][0] + '</td><td>' + rows[i][1] + '</td><td>' + rows[i][2] + '</td><td>' + rows[i][3] + '</td></tr>';
  }

  var body = getEl('cards-table-body');
  if (body) body.innerHTML = html;
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
  var pred = data.predictions || {};
  var fixtureStats = data.fixture_statistics || {};

  var html = '';
  html += '<p><strong>' + valueOrDash(mi.home_team) + '</strong> llega con ' + valueOrDash(hs.played) + ' partidos jugados y racha ' + valueOrDash(hs.form_string || 'Sin datos') + '.</p>';
  html += '<p><strong>' + valueOrDash(mi.away_team) + '</strong> llega con ' + valueOrDash(as.played) + ' partidos jugados y racha ' + valueOrDash(as.form_string || 'Sin datos') + '.</p>';

  if (hs.avg_corners > 0 || as.avg_corners > 0) {
    html += '<p><strong>Corners:</strong> Local promedia ' + dec(hs.avg_corners) + ' corners por partido, visitante ' + dec(as.avg_corners) + '.</p>';
  }

  if (hs.avg_yellow_cards > 0 || as.avg_yellow_cards > 0) {
    html += '<p><strong>Tarjetas:</strong> Local promedia ' + dec(hs.avg_yellow_cards) + ' amarillas, visitante ' + dec(as.avg_yellow_cards) + ' por partido.</p>';
  }

  if (fixtureStats && fixtureStats.home) {
    var homeStats = fixtureStats.home;
    var awayStats = fixtureStats.away;
    html += '<p><strong>Estadísticas del partido:</strong></p>';
    if (homeStats.ball_possession || awayStats.ball_possession) {
      html += '<p>Posesión: Local ' + valueOrDash(homeStats.ball_possession) + ' - Visitante ' + valueOrDash(awayStats.ball_possession) + '</p>';
    }
    if (homeStats.shots_on_goal || awayStats.shots_on_goal) {
      html += '<p>Tiros a puerta: Local ' + valueOrDash(homeStats.shots_on_goal) + ' - Visitante ' + valueOrDash(awayStats.shots_on_goal) + '</p>';
    }
    if (homeStats.corners || awayStats.corners) {
      html += '<p>Corners: Local ' + valueOrDash(homeStats.corners) + ' - Visitante ' + valueOrDash(awayStats.corners) + '</p>';
    }
    if (homeStats.yellow_cards || awayStats.yellow_cards) {
      html += '<p>Amarillas: Local ' + valueOrDash(homeStats.yellow_cards) + ' - Visitante ' + valueOrDash(awayStats.yellow_cards) + '</p>';
    }
  }

  if (pred && pred.advice) {
    html += '<p><strong>Predicción API-Football:</strong> ' + pred.advice + '</p>';
  }

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
      renderCornersTable(data);
      renderCardsTable(data);
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
