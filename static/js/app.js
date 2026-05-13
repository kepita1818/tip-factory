/* ============ RESET & BASE ============ */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

:root {
    --bg-primary: #0a0e17;
    --bg-secondary: #111827;
    --bg-card: #1a2234;
    --bg-card-hover: #243047;
    --text-primary: #ffffff;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --accent: #22c55e;
    --accent-hover: #16a34a;
    --accent-light: #4ade80;
    --success: #22c55e;
    --warning: #eab308;
    --danger: #ef4444;
    --info: #3b82f6;
    --border: #1e293b;
    --radius: 16px;
    --radius-sm: 12px;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
    overflow-x: hidden;
    -webkit-tap-highlight-color: transparent;
}

#app {
    max-width: 500px;
    margin: 0 auto;
    padding: 16px;
    padding-bottom: 40px;
}

/* ============ HEADER ============ */
.app-header {
    padding: 16px 0 20px;
    margin-bottom: 4px;
}

.app-header h1 {
    font-size: 28px;
    font-weight: 900;
    letter-spacing: -1px;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.subtitle {
    font-size: 13px;
    color: var(--text-muted);
    font-weight: 500;
}

/* ============ DATE SELECTOR ============ */
.date-selector {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin-bottom: 16px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 12px 16px;
}

.date-nav {
    background: none;
    border: none;
    color: var(--text-secondary);
    font-size: 14px;
    cursor: pointer;
    padding: 4px 8px;
    transition: color 0.2s;
}

.date-nav:hover {
    color: var(--text-primary);
}

.date-display {
    flex: 1;
    text-align: center;
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
    cursor: pointer;
    position: relative;
}

#date-picker {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    opacity: 0;
    cursor: pointer;
}

.hidden {
    display: none !important;
}

/* ============ LEAGUE FILTERS ============ */
.league-filters {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
    overflow-x: auto;
    padding-bottom: 4px;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
}

.league-filters::-webkit-scrollbar {
    display: none;
}

.filter-btn {
    background: var(--bg-card);
    border: 1px solid var(--border);
    color: var(--text-secondary);
    padding: 8px 16px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s;
}

.filter-btn.active {
    background: var(--accent);
    border-color: var(--accent);
    color: #000;
    font-weight: 700;
}

.filter-btn:hover:not(.active) {
    background: var(--bg-card-hover);
    color: var(--text-primary);
}

/* ============ MATCHES CONTAINER ============ */
.matches-container {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

/* ============ MATCH CARD ============ */
.match-card-main {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 14px 16px;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.match-card-main:hover {
    background: var(--bg-card-hover);
    border-color: var(--accent);
    transform: translateY(-1px);
}

.match-card-main:active {
    transform: scale(0.99);
}

.match-card-main.live {
    border-color: var(--danger);
}

.match-card-main.finished {
    opacity: 0.85;
}

.match-time-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12px;
    color: var(--text-muted);
    font-weight: 600;
}

.match-time {
    font-size: 13px;
    font-weight: 700;
}

.status-badge {
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 800;
}

.status-badge.live {
    background: var(--danger);
    color: white;
    animation: pulse 1.5s infinite;
}

.status-badge.finished {
    background: var(--text-muted);
    color: var(--bg-primary);
}

.status-badge.postponed {
    background: var(--warning);
    color: #000;
}

.match-score {
    font-size: 16px;
    font-weight: 900;
    color: var(--text-primary);
}

.match-teams-row {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.match-team-row {
    display: flex;
    align-items: center;
    gap: 10px;
}

.match-team-row img {
    width: 28px;
    height: 28px;
    object-fit: contain;
    flex-shrink: 0;
}

.match-team-row span {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    flex: 1;
}

.team-score {
    font-size: 16px;
    font-weight: 900;
    color: var(--text-primary);
    min-width: 24px;
    text-align: right;
}

.match-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-top: 4px;
}

.match-league-tag {
    font-size: 10px;
    color: var(--text-muted);
    background: var(--bg-secondary);
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
}

.match-venue {
    font-size: 10px;
    color: var(--text-muted);
    font-weight: 500;
}

.loading, .no-matches {
    text-align: center;
    padding: 50px 20px;
    color: var(--text-muted);
    font-size: 14px;
    font-weight: 500;
}

.no-matches-icon {
    font-size: 48px;
    margin-bottom: 12px;
}

/* ============ SECTIONS ============ */
.section {
    animation: fadeIn 0.3s ease;
}

.section.hidden {
    display: none;
}

.section-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
}

.section-header h2 {
    font-size: 18px;
    font-weight: 800;
}

.back-btn {
    background: var(--bg-card);
    border: 1px solid var(--border);
    color: var(--text-secondary);
    width: 36px;
    height: 36px;
    border-radius: 10px;
    font-size: 16px;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
}

.back-btn:hover {
    background: var(--bg-card-hover);
    color: var(--text-primary);
}

/* ============ MATCH HEADER ============ */
.match-header {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px 20px;
    margin-bottom: 20px;
    text-align: center;
}

.match-teams {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    margin-bottom: 12px;
}

.team {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    flex: 1;
}

.team img {
    width: 56px;
    height: 56px;
    object-fit: contain;
}

.team span {
    font-size: 14px;
    font-weight: 800;
    text-align: center;
}

.team small {
    font-size: 11px;
    color: var(--text-muted);
    font-weight: 600;
}

.vs {
    font-size: 13px;
    font-weight: 900;
    color: var(--text-muted);
    background: var(--bg-secondary);
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    border: 2px solid var(--border);
    flex-direction: column;
}

.score-box {
    font-size: 24px;
    font-weight: 900;
    color: var(--text-primary);
}

.score-sep {
    font-size: 18px;
    color: var(--text-muted);
    margin: 0 4px;
}

.ht-score {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 4px;
}

.match-meta {
    font-size: 12px;
    color: var(--text-muted);
    font-weight: 500;
    margin-bottom: 8px;
}

.match-details {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 8px;
    font-size: 11px;
    color: var(--text-secondary);
}

.match-details span {
    background: var(--bg-secondary);
    padding: 4px 10px;
    border-radius: 6px;
}

/* ============ TABS ============ */
.tabs {
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
    overflow-x: auto;
    padding-bottom: 4px;
    scrollbar-width: none;
}

.tabs::-webkit-scrollbar {
    display: none;
}

.tab-btn {
    background: var(--bg-card);
    border: 1px solid var(--border);
    color: var(--text-muted);
    padding: 10px 16px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s;
}

.tab-btn.active {
    background: var(--accent);
    border-color: var(--accent);
    color: #000;
    font-weight: 800;
}

.tab-btn:hover:not(.active) {
    background: var(--bg-card-hover);
    color: var(--text-secondary);
}

/* ============ TAB CONTENT ============ */
.tab-content {
    display: none;
    animation: fadeIn 0.3s ease;
}

.tab-content.active {
    display: block;
}

/* ============ CARDS ============ */
.card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    margin-bottom: 14px;
}

.card-title {
    font-size: 15px;
    font-weight: 800;
    color: var(--text-primary);
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border);
}

/* ============ STANDINGS ============ */
.standings-row {
    display: flex;
    justify-content: space-between;
    align-items: stretch;
    gap: 12px;
}

.standing-box {
    flex: 1;
    background: var(--bg-secondary);
    border-radius: var(--radius-sm);
    padding: 16px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
}

.standing-vs {
    display: flex;
    align-items: center;
    font-size: 14px;
    font-weight: 900;
    color: var(--text-muted);
}

.pos-badge {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    font-weight: 900;
    color: white;
}

.standing-info {
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.6;
}

.form-string {
    font-size: 14px;
    font-weight: 800;
    letter-spacing: 2px;
}

/* ============ ODDS ============ */
.odds-row {
    display: flex;
    justify-content: center;
    gap: 16px;
}

.odd-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    background: var(--bg-secondary);
    padding: 12px 20px;
    border-radius: var(--radius-sm);
    min-width: 70px;
}

.odd-label {
    font-size: 12px;
    font-weight: 800;
    color: var(--text-muted);
}

.odd-value {
    font-size: 18px;
    font-weight: 900;
    color: var(--accent);
}

/* ============ H2H ============ */
.h2h-stats {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 8px;
    margin-bottom: 16px;
}

.h2h-stat-item {
    background: var(--bg-secondary);
    border-radius: var(--radius-sm);
    padding: 12px 8px;
    text-align: center;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.h2h-stat-item.win .h2h-number {
    color: var(--success);
}

.h2h-stat-item.draw .h2h-number {
    color: var(--warning);
}

.h2h-number {
    font-size: 18px;
    font-weight: 900;
    color: var(--text-primary);
}

.h2h-label {
    font-size: 9px;
    color: var(--text-muted);
    font-weight: 600;
}

.h2h-matches {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.h2h-match {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    background: var(--bg-secondary);
    padding: 10px 14px;
    border-radius: 10px;
    font-size: 12px;
    align-items: center;
}

.h2h-date {
    color: var(--text-muted);
    font-weight: 600;
    min-width: 80px;
}

.h2h-comp {
    color: var(--accent);
    font-weight: 700;
    font-size: 10px;
}

.h2h-result {
    flex: 1;
    text-align: right;
    font-weight: 700;
    color: var(--text-primary);
}

/* ============ FORM ============ */
.form-section {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.form-team-block h4 {
    font-size: 14px;
    color: var(--text-secondary);
    margin-bottom: 10px;
    font-weight: 700;
}

.form-badges {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
}

.badge {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 900;
    color: white;
}

.badge.W { background: var(--success); }
.badge.D { background: var(--warning); }
.badge.L { background: var(--danger); }

.form-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.form-item {
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--bg-secondary);
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 12px;
}

.form-result {
    font-size: 14px;
}

.form-score {
    font-weight: 800;
    min-width: 40px;
    color: var(--text-primary);
}

.form-opp {
    flex: 1;
    color: var(--text-secondary);
}

.form-venue {
    font-size: 12px;
}

.form-date {
    color: var(--text-muted);
    font-size: 11px;
}

/* ============ PROBABILITIES ============ */
.prob-list {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.prob-item {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.prob-label {
    font-size: 13px;
    font-weight: 700;
    color: var(--text-secondary);
}

.prob-bar-container {
    display: flex;
    align-items: center;
    gap: 12px;
    background: var(--bg-primary);
    border-radius: 12px;
    padding: 4px;
    height: 36px;
    position: relative;
    border: 1px solid var(--border);
}

.prob-bar {
    height: 100%;
    border-radius: 10px;
    transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
    min-width: 4px;
    background: linear-gradient(90deg, var(--success), #84cc16);
}

.prob-bar.medium {
    background: linear-gradient(90deg, var(--warning), #f97316);
}

.prob-bar.low {
    background: linear-gradient(90deg, #f97316, var(--danger));
}

.prob-bar-info {
    background: linear-gradient(90deg, var(--info), #8b5cf6);
}

.prob-value {
    font-size: 14px;
    font-weight: 800;
    color: var(--text-primary);
    min-width: 50px;
    text-align: right;
}

/* ============ STATS TABLE ============ */
.stats-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 13px;
}

.stats-table th {
    text-align: left;
    padding: 12px 10px;
    color: var(--text-muted);
    font-weight: 700;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid var(--border);
}

.stats-table td {
    padding: 14px 10px;
    border-bottom: 1px solid var(--border);
    color: var(--text-secondary);
    font-weight: 600;
}

.stats-table tr:last-child td {
    border-bottom: none;
}

.stats-table .value-high {
    color: var(--success);
    font-weight: 800;
}

.stats-table .value-medium {
    color: var(--warning);
    font-weight: 800;
}

.stats-table .value-low {
    color: var(--danger);
    font-weight: 800;
}

/* ============ EVENTS ============ */
.event-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    background: var(--bg-secondary);
    border-radius: 10px;
    font-size: 13px;
    margin-bottom: 6px;
}

.event-minute {
    font-weight: 800;
    color: var(--danger);
    min-width: 36px;
}

.event-icon {
    font-size: 16px;
}

.event-icon.yellow {
    color: var(--warning);
}

.event-icon.red {
    color: var(--danger);
}

.event-player {
    flex: 1;
    font-weight: 600;
    color: var(--text-primary);
}

.event-team {
    font-size: 11px;
    color: var(--text-muted);
    font-weight: 700;
}

.event-type {
    font-size: 11px;
    color: var(--text-muted);
}

.sub-out {
    color: var(--danger);
    text-decoration: line-through;
}

.sub-in {
    color: var(--success);
}

/* ============ NO DATA ============ */
.no-data {
    text-align: center;
    padding: 20px;
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 500;
}

.no-data-small {
    color: var(--text-muted);
    font-size: 12px;
}

/* ============ ANIMATIONS ============ */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}

/* ============ SCROLLBAR ============ */
::-webkit-scrollbar {
    width: 4px;
}

::-webkit-scrollbar-track {
    background: var(--bg-primary);
}

::-webkit-scrollbar-thumb {
    background: var(--border);
    border-radius: 4px;
}
