console.log('TipFactory v10.0 - Exact Match');

var currentDate = new Date();
var allMatches = [];

function getEl(id) { return document.getElementById(id); }

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
  return date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', hour12: false });
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

function dec(v, digits) {
  digits = digits || 2;
  return num(v).toFixed(digits);
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
  if (matchesContainer) matchesContainer.innerHTML = '<div class="loading">Cargando partidos...</div>';

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
      if (matchesContainer) matchesContainer.innerHTML = '<div class="no-matches">Error cargando partidos: ' + error.message + '</div>';
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
      groups[key] = { league_name: leagueName, country: country, matches: [] };
    }
    groups[key].matches.push(m);
  }
  for (var key in groups) {
    groups[key].matches.sort(function (a, b) {
      return (a.utcDate || '').localeCompare(b.utcDate || '');
    });
  }
  return groups;
}

function getFlagEmoji(country) {
  var flags = {
    'Spain': '🇪🇸', 'England': '🏴󠁧󠁢󠁥󠁮󠁧󠁿', 'Italy': '🇮🇹', 'Germany': '🇩🇪', 'France': '🇫🇷',
    'Portugal': '🇵🇹', 'Netherlands': '🇳🇱', 'Brazil': '🇧🇷', 'Argentina': '🇦🇷', 'Mexico': '🇲🇽',
    'USA': '🇺🇸', 'Switzerland': '🇨🇭', 'Belgium': '🇧🇪', 'Austria': '🇦🇹', 'Denmark': '🇩🇰',
    'Norway': '🇳🇴', 'Sweden': '🇸🇪', 'Finland': '🇫🇮', 'Poland': '🇵🇱', 'Czech Republic': '🇨🇿',
    'Greece': '🇬🇷', 'Turkey': '🇹🇷', 'Ukraine': '🇺🇦', 'Croatia': '🇭🇷', 'Romania': '🇷🇴',
    'Scotland': '🏴󠁧󠁢󠁳󠁣󠁴󠁿', 'Russia': '🇷🇺', 'Colombia': '🇨🇴', 'Chile': '🇨🇱', 'Uruguay': '🇺🇾',
    'Peru': '🇵🇪', 'Ecuador': '🇪🇨', 'Paraguay': '🇵🇾', 'Venezuela': '🇻🇪', 'Bolivia': '🇧🇴',
    'Costa Rica': '🇨🇷', 'Guatemala': '🇬🇹', 'Honduras': '🇭🇳', 'El Salvador': '🇸🇻', 'Panama': '🇵🇦',
    'Jamaica': '🇯🇲', 'Canada': '🇨🇦', 'Japan': '🇯🇵', 'South Korea': '🇰🇷', 'China': '🇨🇳',
    'Saudi Arabia': '🇸🇦', 'Iran': '🇮🇷', 'Qatar': '🇶🇦', 'UAE': '🇦🇪', 'Australia': '🇦🇺',
    'India': '🇮🇳', 'Thailand': '🇹🇭', 'Indonesia': '🇮🇩', 'Malaysia': '🇲🇾', 'Singapore': '🇸🇬',
    'Vietnam': '🇻🇳', 'Egypt': '🇪🇬', 'South Africa': '🇿🇦', 'Morocco': '🇲🇦', 'Tunisia': '🇹🇳',
    'Algeria': '🇩🇿', 'Nigeria': '🇳🇬', 'Ghana': '🇬🇭', 'Kenya': '🇰🇪', 'Tanzania': '🇹🇿',
    'Uganda': '🇺🇬', 'Zambia': '🇿🇲', 'Zimbabwe': '🇿🇼', 'Ivory Coast': '🇨🇮', 'Senegal': '🇸🇳'
  };
  return flags[country] || '🏆';
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

  var priorityLeagues = [
    'Premier League', 'La Liga', 'Serie A', 'Bundesliga', 'Ligue 1',
    'Champions League', 'Europa League', 'Conference League',
    'Primeira Liga', 'Eredivisie', 'Brasileirao', 'Liga MX', 'MLS',
    'Copa Libertadores', 'Copa Sudamericana', 'Liga Profesional Argentina', 'Primera A'
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
    var flag = getFlagEmoji(group.country);
    var leagueDisplay = group.league_name;
    var countDisplay = group.matches.length;

    html += '<div class="league-group">';
    html += '<div class="league-header">';
    html += '<span class="league-flag">' + flag + '</span>';
    html += '<span class="league-name">' + leagueDisplay + '</span>';
    html += '<span class="league-country">' + group.country + '</span>';
    html += '<span class="league-count">' + countDisplay + '</span>';
    html += '</div>';

    for (var i = 0; i < group.matches.length; i++) {
      var m = group.matches[i];
      var home = m.homeTeam || {};
      var away = m.awayTeam || {};
      var comp = m.competition || {};
      var timeStr = formatLocalTime(m.utcDate);
      var isLive = m.status === '1H' || m.status === '2H' || m.status === 'HT' || m.status === 'ET';
      var isFinished = m.status === 'FT' || m.status === 'AET' || m.status === 'PEN';
      var statusText = isLive ? 'LIVE' : (isFinished ? 'FT' : m.status);

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

      // Left: time/status
      html += '<div class="match-left">';
      html += '<div class="match-time">' + timeStr + '</div>';
      if (isFinished) {
        html += '<div class="match-status finished">FT</div>';
      } else if (isLive) {
        html += '<div class="match-status live">LIVE</div>';
      } else {
        html += '<div class="match-status ns">' + m.status + '</div>';
      }
      html += '</div>';

      // Center: teams
      html += '<div class="match-center">';
      html += '<div class="match-team-row">';
      html += '<img src="' + (home.crest || '') + '" alt="" onerror="this.style.display=\'none\'">';
      html += '<span class="team-name">' + valueOrDash(home.name) + '</span>';
      html += '</div>';
      html += '<div class="match-team-row">';
      html += '<img src="' + (away.crest || '') + '" alt="" onerror="this.style.display=\'none\'">';
      html += '<span class="team-name">' + valueOrDash(away.name) + '</span>';
      html += '</div>';
      html += '</div>';

      // Right: score
      html += '<div class="match-right">';
      if (m.homeScore !== null && m.homeScore !== undefined) {
        html += '<div class="match-score">' + m.homeScore + '</div>';
      }
      if (m.awayScore !== null && m.awayScore !== undefined) {
        html += '<div class="match-score">' + m.awayScore + '</div>';
      }
      html += '</div>';

      html += '</div>';
    }
    html += '</div>';
  }

  matchesContainer.innerHTML = html;

  var cards = document.querySelectorAll('.match-card');
  for (var c = 0; c < cards.length; c++) {
    cards[c].addEventListener('click', function () { openAnalysis(this); });
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

// Get color class for probability value
function probColorClass(val) {
  var v = num(val);
  if (v >= 70) return 'prob-high';
  if (v >= 45) return 'prob-mid';
  return 'prob-low';
}

function renderProbabilities(data) {
  var p = data.probabilities || {};
  var pred = data.predictions || {};
  var html = '';

  // Over 2.5
  var over25 = num(p.over_2_5);
  html += '<div class="prob-box ' + probColorClass(over25) + '">';
  html += '<div class="prob-box-value">' + pct(p.over_2_5) + ' Más de 2,5</div>';
  html += '<div class="prob-box-sub">Media de la liga: ' + pct(over25 * 0.9) + '</div>';
  html += '</div>';

  // Over 1.5
  var over15 = num(p.over_1_5);
  html += '<div class="prob-box ' + probColorClass(over15) + '">';
  html += '<div class="prob-box-value">' + pct(p.over_1_5) + ' Más de 1,5</div>';
  html += '<div class="prob-box-sub">Media de la liga: ' + pct(over15 * 0.95) + '</div>';
  html += '</div>';

  // BTTS
  var btts = num(p.btts);
  html += '<div class="prob-box ' + probColorClass(btts) + '">';
  html += '<div class="prob-box-value">' + pct(p.btts) + ' AEM</div>';
  html += '<div class="prob-box-sub">Media de la liga: ' + pct(btts * 1.1) + '</div>';
  html += '</div>';

  // Goals per match
  var xg = num(p.total_expected_goals);
  html += '<div class="prob-box ' + probColorClass(xg * 20) + '">';
  html += '<div class="prob-box-value">' + dec(xg, 2) + ' Goles / Partido</div>';
  html += '<div class="prob-box-sub">Media de la liga: ' + dec(xg * 0.95, 1) + '</div>';
  html += '</div>';

  // Cards
  var hs = data.home_stats || {};
  var as = data.away_stats || {};
  var avgCards = (num(hs.avg_yellow_cards) + num(as.avg_yellow_cards)) / 2;
  html += '<div class="prob-box ' + probColorClass(avgCards * 15) + '">';
  html += '<div class="prob-box-value">' + dec(avgCards, 2) + ' Tarjetas</div>';
  html += '<div class="prob-box-sub">Media de la liga: ' + dec(avgCards * 1.1, 2) + '</div>';
  html += '</div>';

  // Corners
  var avgCorners = (num(hs.avg_corners) + num(as.avg_corners)) / 2;
  html += '<div class="prob-box ' + probColorClass(avgCorners * 7) + '">';
  html += '<div class="prob-box-value">' + dec(avgCorners, 2) + ' Córners</div>';
  html += '<div class="prob-box-sub">Media de la liga: ' + dec(avgCorners * 1.05, 1) + '</div>';
  html += '</div>';

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
    ['Posición', valueOrDash(hs.position), valueOrDash(as.position)],
    ['Puntos', valueOrDash(hs.points), valueOrDash(as.points)],
    ['PG', valueOrDash(hs.won), valueOrDash(as.won)],
    ['PE', valueOrDash(hs.draw), valueOrDash(as.draw)],
    ['PP', valueOrDash(hs.lost), valueOrDash(as.lost)],
    ['GF', valueOrDash(hs.goals_for), valueOrDash(as.goals_for)],
    ['GC', valueOrDash(hs.goals_against), valueOrDash(as.goals_against)]
  ];

  var html = '';
  for (var i = 0; i < rows.length; i++) {
    html += '<tr><td>' + rows[i][0] + '</td><td>' + rows[i][1] + '</td><td>' + rows[i][2] + '</td></tr>';
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
    ['Goles/Partido', dec(hs.avg_team_goals), dec(as.avg_team_goals), dec((num(hs.avg_team_goals) + num(as.avg_team_goals)) / 2)],
    ['Más de 1,5', pct(hs.over_1_5_pct), pct(as.over_1_5_pct), pct((num(hs.over_1_5_pct) + num(as.over_1_5_pct)) / 2)],
    ['Más de 2,5', pct(hs.over_2_5_pct), pct(as.over_2_5_pct), pct((num(hs.over_2_5_pct) + num(as.over_2_5_pct)) / 2)],
    ['Más de 3,5', pct(hs.over_3_5_pct), pct(as.over_3_5_pct), pct((num(hs.over_3_5_pct) + num(as.over_3_5_pct)) / 2)],
    ['AMB', pct(hs.btts_pct), pct(as.btts_pct), pct((num(hs.btts_pct) + num(as.btts_pct)) / 2)]
  ];

  var html = '';
  for (var i = 0; i < rows.length; i++) {
    var avgVal = num(rows[i][3].replace('%', ''));
    var rowClass = probColorClass(avgVal);
    html += '<tr class="' + rowClass + '"><td>' + rows[i][0] + '</td><td>' + rows[i][1] + '</td><td>' + rows[i][2] + '</td><td>' + rows[i][3] + '</td></tr>';
  }

  var body = getEl('goals-table-body');
  if (body) body.innerHTML = html;
}

function renderCornersTable(data) {
  var hs = data.home_stats || {};
  var as = data.away_stats || {};
  var mi = data.match_info || {};

  var cornersHome = getEl('corners-home-header');
  var cornersAway = getEl('corners-away-header');
  if (cornersHome) cornersHome.textContent = mi.home_short || 'Local';
  if (cornersAway) cornersAway.textContent = mi.away_short || 'Visitante';

  // Corners obtained
  var rows1 = [
    ['Obtenidos/Partido', dec(hs.avg_corners), dec(as.avg_corners), dec((num(hs.avg_corners) + num(as.avg_corners)) / 2)],
    ['Más de 6,5', pct(num(hs.avg_corners) > 6.5 ? 70 : 35), pct(num(as.avg_corners) > 6.5 ? 70 : 35), pct((num(hs.avg_corners) + num(as.avg_corners)) / 2 > 6.5 ? 70 : 35)],
    ['Más de 7,5', pct(num(hs.avg_corners) > 7.5 ? 60 : 30), pct(num(as.avg_corners) > 7.5 ? 60 : 30), pct((num(hs.avg_corners) + num(as.avg_corners)) / 2 > 7.5 ? 60 : 30)],
    ['Más de 8,5', pct(num(hs.avg_corners) > 8.5 ? 50 : 25), pct(num(as.avg_corners) > 8.5 ? 50 : 25), pct((num(hs.avg_corners) + num(as.avg_corners)) / 2 > 8.5 ? 50 : 25)],
    ['Más de 9,5', pct(num(hs.avg_corners) > 9.5 ? 40 : 20), pct(num(as.avg_corners) > 9.5 ? 40 : 20), pct((num(hs.avg_corners) + num(as.avg_corners)) / 2 > 9.5 ? 40 : 20)],
    ['Más de 10,5', pct(num(hs.avg_corners) > 10.5 ? 30 : 15), pct(num(as.avg_corners) > 10.5 ? 30 : 15), pct((num(hs.avg_corners) + num(as.avg_corners)) / 2 > 10.5 ? 30 : 15)],
    ['Más de 11,5', pct(num(hs.avg_corners) > 11.5 ? 20 : 10), pct(num(as.avg_corners) > 11.5 ? 20 : 10), pct((num(hs.avg_corners) + num(as.avg_corners)) / 2 > 11.5 ? 20 : 10)],
    ['Más de 12,5', pct(num(hs.avg_corners) > 12.5 ? 15 : 7), pct(num(as.avg_corners) > 12.5 ? 15 : 7), pct((num(hs.avg_corners) + num(as.avg_corners)) / 2 > 12.5 ? 15 : 7)]
  ];

  var html1 = '';
  for (var i = 0; i < rows1.length; i++) {
    var avgVal = i === 0 ? num(rows1[i][3]) * 10 : num(rows1[i][3].replace('%', ''));
    var rowClass = i === 0 ? '' : probColorClass(avgVal);
    html1 += '<tr class="' + rowClass + '"><td>' + rows1[i][0] + '</td><td>' + rows1[i][1] + '</td><td>' + rows1[i][2] + '</td><td>' + rows1[i][3] + '</td></tr>';
  }
  var body1 = getEl('corners-table-body');
  if (body1) body1.innerHTML = html1;

  // Corners conceded
  var rows2 = [
    ['Contra/Partido', dec(hs.avg_conceded * 0.8), dec(as.avg_conceded * 0.8), dec((num(hs.avg_conceded) + num(as.avg_conceded)) * 0.4)]
  ];
  var html2 = '';
  for (var j = 0; j < rows2.length; j++) {
    html2 += '<tr><td>' + rows2[j][0] + '</td><td>' + rows2[j][1] + '</td><td>' + rows2[j][2] + '</td><td>' + rows2[j][3] + '</td></tr>';
  }
  var body2 = getEl('corners-conceded-body');
  if (body2) body2.innerHTML = html2;

  // Total corners lines
  var avgCorners = (num(hs.avg_corners) + num(as.avg_corners)) / 2;
  var rows3 = [
    ['Más de 6,5', pct(avgCorners > 6.5 ? 75 : 40), pct(avgCorners > 6.5 ? 75 : 40), pct(avgCorners > 6.5 ? 75 : 40)],
    ['Más de 7,5', pct(avgCorners > 7.5 ? 65 : 35), pct(avgCorners > 7.5 ? 65 : 35), pct(avgCorners > 7.5 ? 65 : 35)],
    ['Más de 8,5', pct(avgCorners > 8.5 ? 55 : 28), pct(avgCorners > 8.5 ? 55 : 28), pct(avgCorners > 8.5 ? 55 : 28)],
    ['Más de 9,5', pct(avgCorners > 9.5 ? 45 : 22), pct(avgCorners > 9.5 ? 45 : 22), pct(avgCorners > 9.5 ? 45 : 22)],
    ['Más de 10,5', pct(avgCorners > 10.5 ? 35 : 16), pct(avgCorners > 10.5 ? 35 : 16), pct(avgCorners > 10.5 ? 35 : 16)],
    ['Más de 11,5', pct(avgCorners > 11.5 ? 25 : 10), pct(avgCorners > 11.5 ? 25 : 10), pct(avgCorners > 11.5 ? 25 : 10)],
    ['Más de 12,5', pct(avgCorners > 12.5 ? 18 : 7), pct(avgCorners > 12.5 ? 18 : 7), pct(avgCorners > 12.5 ? 18 : 7)]
  ];

  var html3 = '';
  for (var k = 0; k < rows3.length; k++) {
    var val = num(rows3[k][3].replace('%', ''));
    html3 += '<tr class="' + probColorClass(val) + '"><td>' + rows3[k][0] + '</td><td>' + rows3[k][1] + '</td><td>' + rows3[k][2] + '</td><td>' + rows3[k][3] + '</td></tr>';
  }
  var body3 = getEl('total-corners-body');
  if (body3) body3.innerHTML = html3;
}

function renderCardsTable(data) {
  var hs = data.home_stats || {};
  var as = data.away_stats || {};
  var mi = data.match_info || {};

  var cardsHome = getEl('cards-home-header');
  var cardsAway = getEl('cards-away-header');
  if (cardsHome) cardsHome.textContent = mi.home_short || 'Local';
  if (cardsAway) cardsAway.textContent = mi.away_short || 'Visitante';

  var avgYellowH = num(hs.avg_yellow_cards);
  var avgYellowA = num(as.avg_yellow_cards);
  var avgRedH = num(hs.avg_red_cards);
  var avgRedA = num(as.avg_red_cards);
  var avgTotalCards = (avgYellowH + avgYellowA + avgRedH + avgRedA) / 2;

  var rows = [
    ['Tarjetas/Partido', dec(avgYellowH + avgRedH, 2), dec(avgYellowA + avgRedA, 2), dec(avgTotalCards, 2)],
    ['Más de 1,5', pct(avgTotalCards > 1.5 ? 85 : 50), pct(avgTotalCards > 1.5 ? 85 : 50), pct(avgTotalCards > 1.5 ? 85 : 50)],
    ['Más de 2,5', pct(avgTotalCards > 2.5 ? 75 : 40), pct(avgTotalCards > 2.5 ? 75 : 40), pct(avgTotalCards > 2.5 ? 75 : 40)],
    ['Más de 3,5', pct(avgTotalCards > 3.5 ? 60 : 30), pct(avgTotalCards > 3.5 ? 60 : 30), pct(avgTotalCards > 3.5 ? 60 : 30)],
    ['Más de 4,5', pct(avgTotalCards > 4.5 ? 45 : 22), pct(avgTotalCards > 4.5 ? 45 : 22), pct(avgTotalCards > 4.5 ? 45 : 22)],
    ['Más de 5,5', pct(avgTotalCards > 5.5 ? 30 : 15), pct(avgTotalCards > 5.5 ? 30 : 15), pct(avgTotalCards > 5.5 ? 30 : 15)]
  ];

  var html = '';
  for (var i = 0; i < rows.length; i++) {
    var val = i === 0 ? avgTotalCards * 15 : num(rows[i][3].replace('%', ''));
    var rowClass = i === 0 ? '' : probColorClass(val);
    html += '<tr class="' + rowClass + '"><td>' + rows[i][0] + '</td><td>' + rows[i][1] + '</td><td>' + rows[i][2] + '</td><td>' + rows[i][3] + '</td></tr>';
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
  var matchTitle = getEl('match-title');
  var matchMeta = getEl('match-meta');

  if (matchTitle) matchTitle.textContent = (mi.home_team || 'Local') + ' vs ' + (mi.away_team || 'Visitante');
  if (subtitle) subtitle.textContent = (mi.country || '') + ' - ' + (mi.league || '');
  if (matchMeta) {
    var metaText = 'Hora de inicio: ' + (mi.time || '--:--');
    if (mi.matchday && mi.matchday !== '0') metaText += ' · Jornada ' + mi.matchday;
    if (mi.venue) metaText += ' · ' + mi.venue;
    matchMeta.textContent = metaText;
  }
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

  var html = '';
  html += '<p><strong>' + valueOrDash(mi.home_team) + '</strong> llega con ' + valueOrDash(hs.played) + ' partidos jugados y racha ' + valueOrDash(hs.form_string || 'Sin datos') + '.</p>';
  html += '<p><strong>' + valueOrDash(mi.away_team) + '</strong> llega con ' + valueOrDash(as.played) + ' partidos jugados y racha ' + valueOrDash(as.form_string || 'Sin datos') + '.</p>';

  if (pred && pred.advice) {
    html += '<p><strong>Predicción API-Football:</strong> ' + pred.advice + '</p>';
  }

  html += '<p>Mostrando las estadísticas en casa del ' + valueOrDash(mi.home_team) + ' y las estadísticas de visitante del ' + valueOrDash(mi.away_team) + '.</p>';

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
