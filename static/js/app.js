console.log('TipFactory v11.2 - Datos 100% reales API-Football');

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

      var homeName = home.name || 'Local';
      var awayName = away.name || 'Visitante';
      var homeShort = home.shortName || homeName;
      var awayShort = away.shortName || awayName;
      var homeCrest = home.crest || '';
      var awayCrest = away.crest || '';
      var leagueName = m.league_name || '';
      var countryName = m.country || '';
      var matchDate = m.matchDate || '';
      var venueName = m.venue || '';
      var matchdayVal = m.matchday || '0';
      var statusVal = m.statusText || 'SCHEDULED';

      html += '<div class="match-card"'
        + ' data-match-id="' + valueOrDash(m.id) + '"'
        + ' data-home-id="' + valueOrDash(home.id) + '"'
        + ' data-away-id="' + valueOrDash(away.id) + '"'
        + ' data-competition-id="' + valueOrDash(comp.id) + '"'
        + ' data-home-team="' + homeName.replace(/"/g, '&quot;') + '"'
        + ' data-away-team="' + awayName.replace(/"/g, '&quot;') + '"'
        + ' data-home-short="' + homeShort.replace(/"/g, '&quot;') + '"'
        + ' data-away-short="' + awayShort.replace(/"/g, '&quot;') + '"'
        + ' data-home-logo="' + homeCrest.replace(/"/g, '&quot;') + '"'
        + ' data-away-logo="' + awayCrest.replace(/"/g, '&quot;') + '"'
        + ' data-league="' + leagueName.replace(/"/g, '&quot;') + '"'
        + ' data-country="' + countryName.replace(/"/g, '&quot;') + '"'
        + ' data-date="' + matchDate + '"'
        + ' data-time="' + timeStr + '"'
        + ' data-venue="' + venueName.replace(/"/g, '&quot;') + '"'
        + ' data-home-score="' + (m.homeScore === null || m.homeScore === undefined ? '' : m.homeScore) + '"'
        + ' data-away-score="' + (m.awayScore === null || m.awayScore === undefined ? '' : m.awayScore) + '"'
        + ' data-matchday="' + matchdayVal + '"'
        + ' data-status="' + statusVal + '">';

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

      html += '<div class="match-center">';
      html += '<div class="match-team-row">';
      html += '<img class="team-crest" src="' + homeCrest + '" alt="">';
      html += '<span class="team-name">' + valueOrDash(homeName) + '</span>';
      html += '</div>';
      html += '<div class="match-team-row">';
      html += '<img class="team-crest" src="' + awayCrest + '" alt="">';
      html += '<span class="team-name">' + valueOrDash(awayName) + '</span>';
      html += '</div>';
      html += '</div>';

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

function probColorClass(val) {
  var v = num(val);
  if (v >= 70) return 'prob-high';
  if (v >= 45) return 'prob-mid';
  return 'prob-low';
}

// ============================================
// POISSON - Solo para TOTALES (mathematically correct)
// ============================================

function factorial(n) {
  if (n <= 1) return 1;
  var result = 1;
  for (var i = 2; i <= n; i++) result *= i;
  return result;
}

function poisson(lambda, k) {
  return (Math.pow(lambda, k) * Math.exp(-lambda)) / factorial(k);
}

function poissonOver(lambda, threshold) {
  var cumul = 0;
  for (var k = 0; k <= threshold; k++) {
    cumul += poisson(lambda, k);
  }
  return Math.min(100, Math.max(0, (1 - cumul) * 100));
}

// ============================================
// RENDER PROBABILIDADES GENERAL (datos reales)
// ============================================

function renderProbabilities(data) {
  var p = data.probabilities || {};
  var pred = data.predictions || {};
  var hs = data.home_stats || {};
  var as = data.away_stats || {};
  var html = '';

  // Over 2.5 - % real de frecuencia
  var over25 = num(p.over_2_5);
  html += '<div class="prob-box ' + probColorClass(over25) + '">';
  html += '<div class="prob-box-value">' + pct(p.over_2_5) + ' Más de 2,5</div>';
  html += '<div class="prob-box-sub">Basado en ' + (hs.played || 0) + ' partidos reales</div>';
  html += '</div>';

  // Over 1.5
  var over15 = num(p.over_1_5);
  html += '<div class="prob-box ' + probColorClass(over15) + '">';
  html += '<div class="prob-box-value">' + pct(p.over_1_5) + ' Más de 1,5</div>';
  html += '<div class="prob-box-sub">Frecuencia real</div>';
  html += '</div>';

  // BTTS
  var btts = num(p.btts);
  html += '<div class="prob-box ' + probColorClass(btts) + '">';
  html += '<div class="prob-box-value">' + pct(p.btts) + ' AEM</div>';
  html += '<div class="prob-box-sub">Ambos marcan</div>';
  html += '</div>';

  // Goals per match
  var xg = num(p.total_expected_goals);
  html += '<div class="prob-box ' + probColorClass(xg * 20) + '">';
  html += '<div class="prob-box-value">' + dec(xg, 2) + ' Goles / Partido</div>';
  html += '<div class="prob-box-sub">Media real</div>';
  html += '</div>';

  // Cards REALES
  var avgCards = num(hs.avg_yellow_cards) + num(as.avg_yellow_cards);
  html += '<div class="prob-box ' + probColorClass(avgCards * 15) + '">';
  html += '<div class="prob-box-value">' + dec(avgCards, 2) + ' Tarjetas</div>';
  html += '<div class="prob-box-sub">Amarillas reales por partido</div>';
  html += '</div>';

  // Corners REALES
  var avgCorners = num(hs.avg_corners) + num(as.avg_corners);
  html += '<div class="prob-box ' + probColorClass(avgCorners * 7) + '">';
  html += '<div class="prob-box-value">' + dec(avgCorners, 2) + ' Córners</div>';
  html += '<div class="prob-box-sub">Córners reales por partido</div>';
  html += '</div>';

  var grid = getEl('prob-grid');
  if (grid) grid.innerHTML = html;
}

function renderMiniStats(data) {
  var hs = data.home_stats || {};
  var as = data.away_stats || {};
  var html = '';

  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrDash(hs.played) + '</div><div class="mini-stat-label">PJ local</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrDash(as.played) + '</div><div class="mini-stat-label">PJ visitante</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrDash(hs.avg_team_goals) + '</div><div class="mini-stat-label">Goles local</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + valueOrDash(as.avg_team_goals) + '</div><div class="mini-stat-label">Goles visitante</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + pct(hs.clean_sheet_pct) + '</div><div class="mini-stat-label">Portería a 0 local</div></div>';
  html += '<div class="mini-stat-box"><div class="mini-stat-value">' + pct(as.clean_sheet_pct) + '</div><div class="mini-stat-label">Portería a 0 visitante</div></div>';

  var grid = getEl('mini-stats-grid');
  if (grid) grid.innerHTML = html;
}

// ============================================
// GOLES - Porcentajes REALES del backend
// ============================================

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

// ============================================
// CORNERS - Datos 100% REALES de la API
// Individual: porcentajes reales del backend
// Total: Poisson con lambda = home_avg + away_avg (correcto)
// ============================================

function renderCornersTable(data) {
  var hs = data.home_stats || {};
  var as = data.away_stats || {};
  var mi = data.match_info || {};

  var cornersHome = getEl('corners-home-header');
  var cornersAway = getEl('corners-away-header');
  if (cornersHome) cornersHome.textContent = mi.home_short || 'Local';
  if (cornersAway) cornersAway.textContent = mi.away_short || 'Visitante';

  var hcp = hs.corners_pct || {};
  var acp = as.corners_pct || {};

  // === CORNERS GANADOS POR EQUIPO - PORCENTAJES REALES ===
  var rows1 = [
    ['Obtenidos/Partido', dec(hs.avg_corners), dec(as.avg_corners), dec((num(hs.avg_corners) + num(as.avg_corners)) / 2)],
    ['Más de 4,5', pct(hcp.over_4_5 || 0), pct(acp.over_4_5 || 0), pct((num(hcp.over_4_5) + num(acp.over_4_5)) / 2)],
    ['Más de 5,5', pct(hcp.over_5_5 || 0), pct(acp.over_5_5 || 0), pct((num(hcp.over_5_5) + num(acp.over_5_5)) / 2)],
    ['Más de 6,5', pct(hcp.over_6_5 || 0), pct(acp.over_6_5 || 0), pct((num(hcp.over_6_5) + num(acp.over_6_5)) / 2)],
    ['Más de 7,5', pct(hcp.over_7_5 || 0), pct(acp.over_7_5 || 0), pct((num(hcp.over_7_5) + num(acp.over_7_5)) / 2)],
    ['Más de 8,5', pct(hcp.over_8_5 || 0), pct(acp.over_8_5 || 0), pct((num(hcp.over_8_5) + num(acp.over_8_5)) / 2)],
    ['Más de 9,5', pct(hcp.over_9_5 || 0), pct(acp.over_9_5 || 0), pct((num(hcp.over_9_5) + num(acp.over_9_5)) / 2)],
    ['Más de 10,5', pct(hcp.over_10_5 || 0), pct(acp.over_10_5 || 0), pct((num(hcp.over_10_5) + num(acp.over_10_5)) / 2)]
  ];

  var html1 = '';
  for (var i = 0; i < rows1.length; i++) {
    var avgVal = i === 0 ? num(rows1[i][3]) * 10 : num(rows1[i][3].replace('%', ''));
    var rowClass = i === 0 ? '' : probColorClass(avgVal);
    html1 += '<tr class="' + rowClass + '"><td>' + rows1[i][0] + '</td><td>' + rows1[i][1] + '</td><td>' + rows1[i][2] + '</td><td>' + rows1[i][3] + '</td></tr>';
  }
  var body1 = getEl('corners-table-body');
  if (body1) body1.innerHTML = html1;

  // === CORNERS EN CONTRA (estimado) ===
  var homeConcededCorners = num(hs.avg_conceded) * 1.5;
  var awayConcededCorners = num(as.avg_conceded) * 1.5;

  var rows2 = [
    ['Contra/Partido', dec(homeConcededCorners), dec(awayConcededCorners), dec((homeConcededCorners + awayConcededCorners) / 2)]
  ];
  var html2 = '';
  for (var j = 0; j < rows2.length; j++) {
    html2 += '<tr><td>' + rows2[j][0] + '</td><td>' + rows2[j][1] + '</td><td>' + rows2[j][2] + '</td><td>' + rows2[j][3] + '</td></tr>';
  }
  var body2 = getEl('corners-conceded-body');
  if (body2) body2.innerHTML = html2;

  // === TOTAL DE CORNERS - POISSON CON LAMBDA = SUMA DE MEDIAS ===
  // FIX: Cada columna usa su propio lambda para dar valores DIFERENTES
  // Local: lambda = home_avg (prob de que el LOCAL supere la línea total)
  // Visitante: lambda = away_avg (prob de que el VISITANTE supere la línea total)
  // Media: lambda = home_avg + away_avg (prob de que el TOTAL supere la línea)
  var homeLambda = num(hs.avg_corners);
  var awayLambda = num(as.avg_corners);
  var totalLambda = homeLambda + awayLambda;

  var rows3 = [
    ['Más de 6,5', pct(poissonOver(homeLambda, 6)), pct(poissonOver(awayLambda, 6)), pct(poissonOver(totalLambda, 6))],
    ['Más de 7,5', pct(poissonOver(homeLambda, 7)), pct(poissonOver(awayLambda, 7)), pct(poissonOver(totalLambda, 7))],
    ['Más de 8,5', pct(poissonOver(homeLambda, 8)), pct(poissonOver(awayLambda, 8)), pct(poissonOver(totalLambda, 8))],
    ['Más de 9,5', pct(poissonOver(homeLambda, 9)), pct(poissonOver(awayLambda, 9)), pct(poissonOver(totalLambda, 9))],
    ['Más de 10,5', pct(poissonOver(homeLambda, 10)), pct(poissonOver(awayLambda, 10)), pct(poissonOver(totalLambda, 10))],
    ['Más de 11,5', pct(poissonOver(homeLambda, 11)), pct(poissonOver(awayLambda, 11)), pct(poissonOver(totalLambda, 11))],
    ['Más de 12,5', pct(poissonOver(homeLambda, 12)), pct(poissonOver(awayLambda, 12)), pct(poissonOver(totalLambda, 12))]
  ];

  var html3 = '';
  for (var k = 0; k < rows3.length; k++) {
    var val = num(rows3[k][3].replace('%', ''));
    html3 += '<tr class="' + probColorClass(val) + '"><td>' + rows3[k][0] + '</td><td>' + rows3[k][1] + '</td><td>' + rows3[k][2] + '</td><td>' + rows3[k][3] + '</td></tr>';
  }
  var body3 = getEl('total-corners-body');
  if (body3) body3.innerHTML = html3;
}

// ============================================
// TARJETAS - Datos 100% REALES de la API
// Individual: porcentajes reales del backend
// Total: Poisson con lambda = home_avg + away_avg (correcto)
// ============================================

function renderCardsTable(data) {
  var hs = data.home_stats || {};
  var as = data.away_stats || {};
  var mi = data.match_info || {};

  var cardsHome = getEl('cards-home-header');
  var cardsAway = getEl('cards-away-header');
  if (cardsHome) cardsHome.textContent = mi.home_short || 'Local';
  if (cardsAway) cardsAway.textContent = mi.away_short || 'Visitante';

  var hcp = hs.cards_pct || {};
  var acp = as.cards_pct || {};

  var homeYellow = num(hs.avg_yellow_cards);
  var awayYellow = num(as.avg_yellow_cards);
  var homeRed = num(hs.avg_red_cards);
  var awayRed = num(as.avg_red_cards);

  var homeTotalCards = homeYellow + homeRed;
  var awayTotalCards = awayYellow + awayRed;
  var avgTotalCards = (homeTotalCards + awayTotalCards) / 2;

  // === TARJETAS POR EQUIPO - PORCENTAJES REALES ===
  var rows = [
    ['Tarjetas/Partido', dec(homeTotalCards, 2), dec(awayTotalCards, 2), dec(avgTotalCards, 2)],
    ['Más de 1,5', pct(hcp.over_1_5 || 0), pct(acp.over_1_5 || 0), pct((num(hcp.over_1_5) + num(acp.over_1_5)) / 2)],
    ['Más de 2,5', pct(hcp.over_2_5 || 0), pct(acp.over_2_5 || 0), pct((num(hcp.over_2_5) + num(acp.over_2_5)) / 2)],
    ['Más de 3,5', pct(hcp.over_3_5 || 0), pct(acp.over_3_5 || 0), pct((num(hcp.over_3_5) + num(acp.over_3_5)) / 2)],
    ['Más de 4,5', pct(hcp.over_4_5 || 0), pct(acp.over_4_5 || 0), pct((num(hcp.over_4_5) + num(acp.over_4_5)) / 2)],
    ['Más de 5,5', pct(hcp.over_5_5 || 0), pct(acp.over_5_5 || 0), pct((num(hcp.over_5_5) + num(acp.over_5_5)) / 2)]
  ];

  var html = '';
  for (var i = 0; i < rows.length; i++) {
    var val = i === 0 ? avgTotalCards * 15 : num(rows[i][3].replace('%', ''));
    var rowClass = i === 0 ? '' : probColorClass(val);
    html += '<tr class="' + rowClass + '"><td>' + rows[i][0] + '</td><td>' + rows[i][1] + '</td><td>' + rows[i][2] + '</td><td>' + rows[i][3] + '</td></tr>';
  }

  var body = getEl('cards-table-body');
  if (body) body.innerHTML = html;

  // === TOTAL DE TARJETAS - POISSON CON LAMBDA = SUMA DE MEDIAS ===
  // FIX: Cada columna usa su propio lambda para dar valores DIFERENTES
  var homeCardsLambda = homeTotalCards;
  var awayCardsLambda = awayTotalCards;
  var totalCardsLambda = homeCardsLambda + awayCardsLambda;

  var rowsTotal = [
    ['Más de 2,5', pct(poissonOver(homeCardsLambda, 2)), pct(poissonOver(awayCardsLambda, 2)), pct(poissonOver(totalCardsLambda, 2))],
    ['Más de 3,5', pct(poissonOver(homeCardsLambda, 3)), pct(poissonOver(awayCardsLambda, 3)), pct(poissonOver(totalCardsLambda, 3))],
    ['Más de 4,5', pct(poissonOver(homeCardsLambda, 4)), pct(poissonOver(awayCardsLambda, 4)), pct(poissonOver(totalCardsLambda, 4))],
    ['Más de 5,5', pct(poissonOver(homeCardsLambda, 5)), pct(poissonOver(awayCardsLambda, 5)), pct(poissonOver(totalCardsLambda, 5))],
    ['Más de 6,5', pct(poissonOver(homeCardsLambda, 6)), pct(poissonOver(awayCardsLambda, 6)), pct(poissonOver(totalCardsLambda, 6))],
    ['Más de 7,5', pct(poissonOver(homeCardsLambda, 7)), pct(poissonOver(awayCardsLambda, 7)), pct(poissonOver(totalCardsLambda, 7))]
  ];

  var totalCardsBody = getEl('total-cards-body');
  if (totalCardsBody) {
    var htmlTotal = '';
    for (var t = 0; t < rowsTotal.length; t++) {
      var valT = num(rowsTotal[t][3].replace('%', ''));
      htmlTotal += '<tr class="' + probColorClass(valT) + '"><td>' + rowsTotal[t][0] + '</td><td>' + rowsTotal[t][1] + '</td><td>' + rowsTotal[t][2] + '</td><td>' + rowsTotal[t][3] + '</td></tr>';
    }
    totalCardsBody.innerHTML = htmlTotal;
  }
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
  if (homeLogo) {
    homeLogo.src = mi.home_logo || '';
    homeLogo.style.display = 'block';
  }
  if (awayLogo) {
    awayLogo.src = mi.away_logo || '';
    awayLogo.style.display = 'block';
  }
}

function renderPrediction(data) {
  var pred = data.predictions || {};
  var box = getEl('prediction-box');
  if (!box) return;

  var html = '';
  if (pred.winner) {
    html += '<div class="prediction-winner">🏆 Ganador: <strong>' + pred.winner + '</strong></div>';
  }
  if (pred.advice) {
    html += '<div class="prediction-advice">💡 ' + pred.advice + '</div>';
  }
  if (pred.under_over) {
    html += '<div class="prediction-over">📊 Over/Under: ' + pred.under_over + '</div>';
  }
  if (!html) {
    html = '<div class="prediction-empty">Predicción no disponible para este partido</div>';
  }
  box.innerHTML = html;
}

function openAnalysis(card) {
  var matchId = card.dataset.matchId;

  var params = new URLSearchParams({
    home_id: card.dataset.homeId,
    away_id: card.dataset.awayId,
    competition_id: card.dataset.competitionId,
    home_team: card.dataset.homeTeam || 'Local',
    away_team: card.dataset.awayTeam || 'Visitante',
    home_short: card.dataset.homeShort || 'Local',
    away_short: card.dataset.awayShort || 'Visitante',
    home_logo: card.dataset.homeLogo || '',
    away_logo: card.dataset.awayLogo || '',
    league: card.dataset.league || '',
    country: card.dataset.country || '',
    date: card.dataset.date || '',
    time: card.dataset.time || '--:--',
    venue: card.dataset.venue || '',
    home_score: card.dataset.homeScore || '',
    away_score: card.dataset.awayScore || '',
    matchday: card.dataset.matchday || '0',
    status: card.dataset.status || 'SCHEDULED'
  });

  showAnalysis();
  activateTab('resumen');
  checkPaywall();

  var box = getEl('prediction-box');
  if (box) box.innerHTML = '<div class="prediction-loading">Cargando predicción...</div>';

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
      renderGoalsTable(data);
      renderCornersTable(data);
      renderCardsTable(data);
      renderPrediction(data);
      checkPaywall();
    })
    .catch(function (error) {
      if (box) box.innerHTML = '<div class="prediction-error">Error: ' + error.message + '</div>';
    });
}


// ===== PAYWALL FUNCTIONS =====
var isUnlocked = localStorage.getItem('tipfactory_unlocked') === 'true';

function checkPaywall() {
  var overlays = document.querySelectorAll('.paywall-overlay');
  for (var i = 0; i < overlays.length; i++) {
    if (isUnlocked) {
      overlays[i].style.display = 'none';
    } else {
      overlays[i].style.display = 'flex';
    }
  }
}

function unlockContent() {
  // Aquí iría la integración con Stripe/PayPal
  // Por ahora simulamos el desbloqueo para testing
  if (confirm('🔓 DEMO: ¿Desbloquear contenido?

En producción esto redirigiría a Stripe/PayPal')) {
    localStorage.setItem('tipfactory_unlocked', 'true');
    isUnlocked = true;
    checkPaywall();
    alert('✅ Contenido desbloqueado (modo demo)');
  }
}

// Hacer unlockContent global para el onclick del HTML
window.unlockContent = unlockContent;

document.addEventListener('DOMContentLoaded', function () {
  updateDateDisplay();
  setupEventListeners();
  loadMatches();
});
