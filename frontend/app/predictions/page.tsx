"use client";

import { useEffect, useState } from "react";
import type { Forecast, ImpactResponse, ModelMetric, Outcome, PredictionsResponse } from "../../lib/prediction-types";
import styles from "./predictions.module.css";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const OUTCOMES: Outcome[] = ["home_regulation", "home_overtime", "away_overtime", "away_regulation"];
const POINTS: Record<Outcome, [number, number]> = {
  home_regulation: [3, 0], home_overtime: [2, 1], away_overtime: [1, 2], away_regulation: [0, 3],
};
const OUTCOME_LABELS: Record<Outcome, string> = {
  home_regulation: "Home · regulation", home_overtime: "Home · extra time",
  away_overtime: "Away · extra time", away_regulation: "Away · regulation",
};

function percent(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

function signed(value: number, digits = 1): string {
  const rounded = Number(value.toFixed(digits));
  return `${rounded > 0 ? "+" : ""}${rounded.toFixed(digits)}`;
}

function probabilityRange(lower: number, upper: number): string {
  const from = percent(lower);
  const to = percent(upper);
  return from === to ? from : `${from}–${to}`;
}

function dateLabel(value?: string | null, includeTime = true): string {
  if (!value) return "Not reported";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not reported";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Helsinki", dateStyle: "medium", ...(includeTime ? { timeStyle: "short" as const } : {}),
  }).format(date);
}

function modelLabel(name: string): string {
  const normalized = name.toLowerCase();
  if (normalized.includes("knn")) return "Paper-inspired kNN";
  if (normalized.includes("logistic")) return "Regularized logistic model";
  if (normalized.includes("elo")) return "Elo baseline";
  if (normalized.includes("prior") || normalized.includes("frequency")) return "League-frequency baseline";
  return name.replace(/_/g, " ");
}

function seasonLabel(season: number): string {
  return `${season - 1}–${String(season).slice(-2)}`;
}

function seasonSpan(seasons?: number[]): string | null {
  if (!seasons?.length) return null;
  const ordered = [...new Set(seasons)].sort((a, b) => a - b);
  return ordered.length === 1 ? `1 season · ${seasonLabel(ordered[0])}`
    : `${ordered.length} seasons · ${ordered[0] - 1}–${ordered[ordered.length - 1]}`;
}

function validMetrics(metrics?: ModelMetric[]): ModelMetric[] {
  return (metrics ?? []).filter(metric => Number.isFinite(metric.log_loss)
    && Number.isFinite(metric.brier) && Number.isFinite(metric.final_winner_accuracy));
}

function outcomeLabel(outcome: Outcome, fixture: Forecast): string {
  const winner = outcome.startsWith("home") ? fixture.home_team.name : fixture.away_team.name;
  return `${winner} wins ${outcome.endsWith("regulation") ? "in regulation" : "in extra time"}`;
}

function featureLabel(name: string, fixture: Forecast): string {
  const match = /^(home|away)_(total|home|away)_(goals_for|goals_against|form_rank)$/.exec(name);
  if (!match) return name.replace(/_/g, " ");
  const team = match[1] === "home" ? fixture.home_team.name : fixture.away_team.name;
  const context = match[2] === "total" ? "all venues" : match[2] === "home" ? "at home" : "away";
  const quantity = match[3] === "goals_for" ? "Goals scored / game"
    : match[3] === "goals_against" ? "Goals conceded / game" : "Form strength (0–1)";
  return `${team} · ${quantity} · ${context}`;
}

async function readResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Unable to retrieve data (HTTP ${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // Network proxies may return a non-JSON error response.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

function validForecast(fixture: Forecast): boolean {
  if (!fixture || !fixture.probabilities || !fixture.home_team || !fixture.away_team) return false;
  const values = OUTCOMES.map(outcome => fixture.probabilities[outcome]);
  const final = [fixture.probabilities.home_win, fixture.probabilities.away_win];
  return [...values, ...final].every(value => Number.isFinite(value) && value >= 0 && value <= 1)
    && Math.abs(values.reduce((sum, value) => sum + value, 0) - 1) < 0.0001
    && Math.abs(final[0] + final[1] - 1) < 0.0001;
}

function Notes({ items, title = "Data and model notes" }: { items: string[]; title?: string }) {
  const notes = [...new Set(items.filter(Boolean))];
  if (notes.length === 0) return null;
  return <details className={styles.notes}>
    <summary>{title} <span>{notes.length}</span></summary>
    <ul>{notes.map((note, index) => <li key={index}>{note}</li>)}</ul>
  </details>;
}

function ForecastCard({ fixture, selected, onSelect }: { fixture: Forecast; selected: boolean; onSelect: () => void }) {
  const { probabilities, home_team: home, away_team: away } = fixture;
  return <article className={`${styles.fixtureCard} ${selected ? styles.selectedCard : ""}`}>
    <button className={styles.fixtureChoice} onClick={onSelect} aria-pressed={selected}
      aria-controls="scenario-section" aria-label={`Explore impact: ${home.name} vs ${away.name}`}>
      <span className={styles.fixtureTop}><time dateTime={fixture.start}>{dateLabel(fixture.start)}</time><span>{selected ? "SELECTED" : "PRE-MATCH"}</span></span>
      <span className={styles.matchup}><strong>{home.name}</strong><span>vs</span><strong>{away.name}</strong></span>
      <span className={styles.winNumbers}><span>{percent(probabilities.home_win)}</span><span>{percent(probabilities.away_win)}</span></span>
      <span className={styles.winBar} aria-hidden="true"><span style={{ width: percent(probabilities.home_win, 4) }} /></span>
      <span className={styles.winLabels}><span>Home win</span><span>Away win</span></span>
      <span className={styles.explore}>{selected ? "Viewing league impact" : "Explore league impact"}<span aria-hidden="true">↗</span></span>
    </button>
    <dl className={styles.outcomeBreakdown}>
      {OUTCOMES.map(outcome => <div key={outcome}><dt>{OUTCOME_LABELS[outcome]}</dt><dd>{percent(probabilities[outcome])}</dd></div>)}
    </dl>
    <p className={styles.cardFootnote}>{fixture.features?.cold_start
      ? "Limited team history · interpret cautiously"
      : "Final-win chances include overtime and shootouts"}</p>
  </article>;
}

function MetricTable({ metrics, selected, rolling = false }: { metrics: ModelMetric[]; selected?: string; rolling?: boolean }) {
  return <div className={styles.tableWrap}>
    <table className={styles.metricTable}>
      <caption>{rolling ? "Rolling historical policy comparison" : "Historical test results"} · lower log loss and Brier score are better</caption>
      <thead><tr><th scope="col">{rolling ? "Forecast policy" : "Model"}</th><th scope="col">Log loss</th><th scope="col">Brier score</th><th scope="col">Final-winner accuracy</th></tr></thead>
      <tbody>{metrics.map(metric => <tr key={metric.name} className={metric.selected || metric.name === selected ? styles.selectedMetric : undefined}>
        <th scope="row">{metric.display_name || modelLabel(metric.name)}{(metric.selected || metric.name === selected) && <span className={styles.chosen}>{rolling ? "Selected policy" : "Selected"}</span>}
          {metric.feature_set && metric.window != null && <small className={styles.metricVariant}>{metric.feature_set === "homeaway" ? "18-feature" : "6-feature"} context · {metric.window}-match window</small>}</th>
        <td>{metric.log_loss.toFixed(3)}</td><td>{metric.brier.toFixed(3)}</td><td>{percent(metric.final_winner_accuracy)}</td>
      </tr>)}</tbody>
    </table>
  </div>;
}

export default function PredictionsPage() {
  const [data, setData] = useState<PredictionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [selectedGame, setSelectedGame] = useState<number | null>(null);
  const [selectedOutcome, setSelectedOutcome] = useState<Outcome>("home_regulation");
  const [topN, setTopN] = useState(4);
  const [impact, setImpact] = useState<ImpactResponse | null>(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [impactError, setImpactError] = useState<string | null>(null);
  const [impactRetry, setImpactRetry] = useState(0);
  const [showAllFixtures, setShowAllFixtures] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setData(null); setImpact(null); setError(null); setLoading(true);
    async function loadForecasts() {
      try {
        const response = await fetch(`${API_BASE}/api/liiga/predictions?limit=12`, { signal: controller.signal });
        const result = await readResponse<PredictionsResponse>(response);
        if (!Array.isArray(result.fixtures) || !result.model || !result.evaluation || !result.fixtures.every(validForecast)) {
          throw new Error("The forecast response has an unexpected format.");
        }
        if (controller.signal.aborted) return;
        setData(result);
        setSelectedGame(current => current != null && result.fixtures.some(fixture => fixture.game_id === current)
          ? current : result.fixtures[0]?.game_id ?? null);
      } catch (caught) {
        if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : "Forecasts are unavailable.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void loadForecasts();
    return () => controller.abort();
  }, [reload]);

  const fixture = data?.fixtures.find(item => item.game_id === selectedGame);
  const forecastVersion = data?.generated_at;
  const modelVersion = data?.model.model_version;

  useEffect(() => {
    const controller = new AbortController();
    setImpact(null); setImpactError(null);
    if (selectedGame == null || !forecastVersion) { setImpactLoading(false); return () => controller.abort(); }
    setImpactLoading(true);
    async function loadImpact() {
      try {
        const query = new URLSearchParams({ top_n: String(topN), simulations: "4000" });
        if (modelVersion) query.set("model_version", modelVersion);
        const response = await fetch(`${API_BASE}/api/liiga/predictions/${selectedGame}/impact?${query}`, { signal: controller.signal });
        const result = await readResponse<ImpactResponse>(response);
        if (!Array.isArray(result.baseline) || !Array.isArray(result.scenarios) || result.game_id !== selectedGame
          || result.top_n !== topN || result.scope !== "regular_season_points" || result.model_version !== modelVersion
          || !OUTCOMES.every(outcome => result.scenarios.some(scenario => scenario.outcome === outcome))) {
          throw new Error("The league-impact response has an unexpected format.");
        }
        if (!controller.signal.aborted) setImpact(result);
      } catch (caught) {
        if (!controller.signal.aborted) setImpactError(caught instanceof Error ? caught.message : "League-impact calculations are unavailable.");
      } finally {
        if (!controller.signal.aborted) setImpactLoading(false);
      }
    }
    void loadImpact();
    return () => controller.abort();
  }, [selectedGame, topN, forecastVersion, modelVersion, impactRetry]);

  const activeImpact = impact?.game_id === selectedGame && impact.top_n === topN ? impact : null;
  const scenario = activeImpact?.scenarios.find(item => item.outcome === selectedOutcome);
  const baseline = [...(activeImpact?.baseline ?? [])].sort((a, b) => a.expected_rank - b.expected_rank || a.name.localeCompare(b.name));
  const scenarioByTeam = new Map((scenario?.teams ?? []).map(team => [team.team_id, team]));
  const model = data?.model;
  const test = data?.evaluation.test;
  const rollingEvaluation = test?.kind === "retrospective_rolling_origin"
    && (test.seasons?.length ?? test.per_season?.length ?? 0) > 1;
  const metricRows = validMetrics(test?.metrics);
  const testedModel = metricRows.find(metric => metric.selected || metric.name === data?.evaluation.selected_model);
  const calibration = (testedModel?.calibration_bins ?? []).filter(bin => bin.count > 0
    && bin.predicted != null && bin.observed != null && Number.isFinite(bin.predicted) && Number.isFinite(bin.observed));
  const selectedLabel = fixture ? outcomeLabel(selectedOutcome, fixture) : "";
  const teamCount = activeImpact?.baseline.length;
  const topOptions = [...new Set([1, 4, 8, 12, 16, topN])].filter(value => !teamCount || value <= teamCount).sort((a, b) => a - b);
  const visibleFixtures = showAllFixtures ? data?.fixtures ?? [] : (data?.fixtures ?? []).slice(0, 6);

  return <main className={styles.page}>
    <header className={styles.header}>
      <div><p className={styles.eyebrow}>BEFORE THE BUZZER · LIIGA FORECASTS</p>
        <h1>Who wins.<br /><span>What changes.</span></h1>
        <p className={styles.description}>Explore match probabilities, then see how one result can change the points race for every team.</p>
      </div>
      <div className={styles.headerActions}>
        <span className={styles.experimental}>Experimental forecasts</span>
        <button className={styles.primaryButton} disabled={loading} onClick={() => { setData(null); setImpact(null); setReload(value => value + 1); }}>
          {loading ? "Preparing forecasts…" : "Refresh forecasts"}
        </button>
      </div>
    </header>

    {loading && <div role="status" className={styles.loading}><span className={styles.spinner} aria-hidden="true" />
      <div><strong>Preparing the next matchday</strong><p>The first visit may take a minute while historical results and model comparisons are prepared.</p></div>
    </div>}
    {error && <div role="alert" className={styles.error}><strong>Forecasts are unavailable.</strong> {error}
      <button className={styles.textButton} onClick={() => setReload(value => value + 1)}>Try again</button></div>}

    {data && <>
      <div className={styles.contextStrip}>
        <span><strong>{data.season - 1}–{String(data.season).slice(-2)}</strong> regular season</span>
        <span><strong>{data.fixtures.length}</strong> upcoming forecasts</span>
        <span>{model?.display_name || modelLabel(model?.name ?? "Model")}</span>
        <a href="#scenario-section">Explore league impact <span aria-hidden="true">↗</span></a>
      </div>
      <p className={styles.forecastNote}>Estimated chances, not guaranteed results. The model uses historical data; late lineup and goalie changes may not be reflected.</p>
      <Notes items={data.warnings ?? []} />

      <section className={styles.forecastsSection} aria-labelledby="forecast-heading">
        <div className={styles.sectionHeading}><div><p className={styles.eyebrow}>THE NEXT MATCHUPS</p><h2 id="forecast-heading">Read the chances</h2></div>
          <span className={styles.sectionTag}>WIN PROBABILITIES</span></div>
        {data.fixtures.length === 0 && <p className={styles.notice}>No upcoming matches are available for prediction. Completed and live games are not shown as pre-match forecasts.</p>}
        <div className={styles.fixtureGrid}>{visibleFixtures.map(item => <ForecastCard key={`${item.season}-${item.game_id}`} fixture={item}
          selected={item.game_id === selectedGame} onSelect={() => setSelectedGame(item.game_id)} />)}</div>
        {data.fixtures.length > 6 && <button className={styles.showMore} onClick={() => setShowAllFixtures(value => !value)}>
          {showAllFixtures ? "Show fewer matches" : `Show all ${data.fixtures.length} matches`} <span aria-hidden="true">{showAllFixtures ? "−" : "+"}</span>
        </button>}
        <p className={styles.updated}>Source: {data.source} · Data fetched {dateLabel(data.data_updated_at)} · Match times shown in Helsinki time</p>
      </section>

      <section id="scenario-section" className={styles.scenarioSection} aria-labelledby="scenario-heading">
        <div className={styles.sectionHeading}><div><p className={styles.eyebrow}>ONE RESULT. EVERY RIVAL.</p><h2 id="scenario-heading">Explore the ripple effect</h2></div>
          <span className={styles.sectionTag}>WHAT IF?</span></div>
        <p className={styles.scope}>Regular-season points projections. Tied teams have probability ranges; official tie-breakers and playoff rules are not included.</p>
        {!fixture && <p className={styles.notice}>Select an upcoming fixture to explore its effect on the points race.</p>}
        {fixture && <>
          <div className={styles.scenarioControls}>
            <div><span className={styles.controlLabel}>Selected match</span><h3>{fixture.home_team.name} <span>vs</span> {fixture.away_team.name}</h3>
              <p>{dateLabel(fixture.start)}</p></div>
            <label className={styles.targetSelect}>Points-finish target
              <select value={topN} onChange={event => setTopN(Number(event.target.value))}>
                {topOptions.map(value => <option key={value} value={value}>Top {value} on points</option>)}
              </select>
            </label>
          </div>
          <div className={styles.scenarioButtons} role="group" aria-label="Match outcome scenario">
            {OUTCOMES.map(outcome => <button key={outcome} className={styles.scenarioButton} aria-pressed={selectedOutcome === outcome}
              onClick={() => setSelectedOutcome(outcome)}>
              <strong>{outcome.startsWith("home") ? fixture.home_team.name : fixture.away_team.name} wins</strong>
              <span>{outcome.endsWith("regulation") ? "In regulation" : "Overtime / shootout"}</span>
              <small>{POINTS[outcome][0]}–{POINTS[outcome][1]} points · {percent(fixture.probabilities[outcome])} forecast</small>
            </button>)}
          </div>

          {impactLoading && <div role="status" className={styles.loading}><span className={styles.spinner} aria-hidden="true" />
            <div><strong>Projecting the remaining schedule</strong><p>Comparing this outcome with the baseline points race.</p></div></div>}
          {impactError && <div role="alert" className={styles.error}><strong>League impact is unavailable.</strong> {impactError}
            <button className={styles.textButton} onClick={() => setImpactRetry(value => value + 1)}>Retry league impact</button></div>}

          {activeImpact && scenario && <>
            <div className={styles.scenarioSummary}><span className={styles.summaryIcon} aria-hidden="true">↗</span><div>
              <span className={styles.controlLabel}>If this result happens</span><h3>{selectedLabel}</h3>
              <p>{activeImpact.simulations.toLocaleString()} simulations · {activeImpact.remaining_fixtures} remaining fixtures · top {topN} on points</p>
            </div></div>
            <div className={styles.tableWrap} tabIndex={0} role="region" aria-label="League points projections, scroll horizontally for all columns">
              <table className={styles.impactTable}>
                <caption>Scenario: {selectedLabel}. Baseline order retained for comparison.</caption>
                <thead><tr><th scope="col">Team</th><th scope="col">Points now</th><th scope="col">Baseline points</th><th scope="col">Scenario points</th>
                  <th scope="col">Change</th><th scope="col">Points rank <span>baseline → scenario</span></th><th scope="col">Top {topN} baseline</th><th scope="col">Top {topN} scenario</th></tr></thead>
                <tbody>{baseline.map(team => {
                  const projected = scenarioByTeam.get(team.team_id);
                  if (!projected) return null;
                  const featured = team.team_id === fixture.home_team.team_id || team.team_id === fixture.away_team.team_id;
                  return <tr key={team.team_id} className={featured ? styles.featuredTeam : undefined}>
                    <th scope="row">{team.name}{featured && <span className={styles.inMatch}>In this match</span>}</th>
                    <td>{team.current_points}</td><td>{team.expected_points.toFixed(1)}</td><td>{projected.expected_points.toFixed(1)}</td>
                    <td className={projected.delta_points > 0.05 ? styles.positive : projected.delta_points < -0.05 ? styles.negative : styles.muted}>{signed(projected.delta_points)}</td>
                    <td><span className={styles.muted}>{team.expected_rank.toFixed(1)}</span> → {projected.expected_rank.toFixed(1)}
                      <small className={projected.delta_rank < -0.05 ? styles.positive : projected.delta_rank > 0.05 ? styles.negative : styles.muted}> ({signed(projected.delta_rank)})</small></td>
                    <td>{probabilityRange(team.top_n_lower, team.top_n_upper)}</td><td>{probabilityRange(projected.top_n_lower, projected.top_n_upper)}</td>
                  </tr>;
                })}</tbody>
              </table>
            </div>
            <p className={styles.tableHint}>Ranks are average positions based on points; a negative rank change is an improvement. Ranges reflect unresolved tied-point ordering, not confidence intervals.</p>
            <p className={styles.scope}>Remaining-match probabilities are held fixed. The sampling margin is at most approximately ±{(activeImpact.max_mc_margin_95 * 100).toFixed(1)} percentage points at 95% for each reported probability; model uncertainty is additional.</p>
            <p className={styles.updated}>Standings fetched {dateLabel(activeImpact.standings_updated_at)} · This scenario does not predict playoff qualification or a championship.</p>
            <Notes items={[...(activeImpact.warnings ?? []), ...(activeImpact.limitations ?? [])]} title="Scenario assumptions" />
          </>}

          <details className={styles.notes}>
            <summary>Team context for this forecast</summary>
            <p>{fixture.home_team.name}: {fixture.features.home_history} prior results. {fixture.away_team.name}: {fixture.features.away_history} prior results.
              {fixture.features.cold_start && " One or both teams have limited usable history."}</p>
            <p>{model?.name.includes("prior") ? "The selected league baseline uses historical outcome frequencies; the team statistics below are shown for context."
              : model?.name.includes("elo") ? "The selected Elo baseline uses sequential result ratings; the recent-form statistics below are shown for context."
              : "The model uses these historical scoring and recent-form features."}</p>
            <p>History cutoff: {dateLabel(fixture.features.history_cutoff, false)}. Only results from earlier Helsinki calendar dates contribute. Form strength is separate from the official league table; 1 represents the top of the recent-form table and 0 the bottom.</p>
            <div className={styles.inputGrid}>{fixture.features.names.map((name, index) => <div key={`${name}-${index}`}>
              <span>{featureLabel(name, fixture)}</span><strong>{Number.isFinite(fixture.features.values[index]) ? fixture.features.values[index].toFixed(2) : "Unknown"}</strong>
            </div>)}</div>
            <Notes items={fixture.warnings ?? []} title="Match data notes" />
          </details>
        </>}
      </section>

      <section className={styles.evidenceSection} aria-labelledby="evidence-heading">
        <div className={styles.sectionHeading}><div><p className={styles.eyebrow}>THE EVIDENCE BEHIND THE ESTIMATE</p><h2 id="evidence-heading">Historical evidence</h2></div>
          <span className={styles.sectionTag}>HISTORICAL EVALUATION</span></div>
        <div className={styles.evidenceCards}>
          <div><span>Current forecast model</span><strong>{model?.display_name || modelLabel(model?.name ?? "Model")}</strong><small>Chosen using earlier validation data, then refit on known history</small></div>
          <div><span>Historical training</span><strong>{model?.training_matches?.toLocaleString() ?? "Not reported"}<small> matches</small></strong>
            {seasonSpan(model?.training_seasons) && <small>{seasonSpan(model?.training_seasons)}</small>}
            <small>Trained through {dateLabel(model?.training_cutoff, false)}</small></div>
          <div><span>{rollingEvaluation ? "Rolling historical evaluation" : "Historical test period"}</span><strong>{test?.count?.toLocaleString() ?? "Not reported"}<small> matches</small></strong>
            {seasonSpan(test?.seasons ?? (test?.season != null ? [test.season] : undefined)) && <small>{seasonSpan(test?.seasons ?? (test?.season != null ? [test.season] : undefined))}</small>}
            <small>{dateLabel(test?.start, false)} – {dateLabel(test?.end, false)}</small></div>
        </div>
        {rollingEvaluation && <p className={styles.scope}>Each season was predicted using earlier data; the selected method and history window can change between seasons. These pooled results evaluate that selection policy, not the current fixed model. Retrospective evaluation, not a new blind test.</p>}
        {!rollingEvaluation && test?.independent_blind === false && <p className={styles.scope}>Retrospective historical evaluation, not a new blind test.</p>}
        {metricRows.length > 0 ? <MetricTable metrics={metricRows} selected={data.evaluation.selected_model} rolling={rollingEvaluation} />
          : <p className={styles.notice}>Detailed historical metrics were not provided by the model response.</p>}
        <p className={styles.scope}>Log loss and Brier score evaluate the four regulation/extra-time probabilities. Final-winner accuracy measures which team won, including overtime and shootouts. Historical performance does not guarantee future results.</p>
        {(test?.per_season?.length ?? 0) > 0 && <details className={styles.notes}>
          <summary>Season-by-season evaluation ({test?.per_season?.length} seasons)</summary>
          <p>Each season has its own earlier validation period and selected configuration. The comparison below retains the models selected before that season&apos;s evaluation.</p>
          {test?.per_season?.map(period => <section key={period.season} className={styles.seasonEvaluation} aria-label={`Evaluation for ${seasonLabel(period.season)}`}>
            <h3>{seasonLabel(period.season)} · {period.count?.toLocaleString() ?? "Not reported"} matches</h3>
            <p>{dateLabel(period.start, false)} – {dateLabel(period.end, false)}.
              {period.selected_model && ` Selected: ${modelLabel(period.selected_model)}.`}</p>
            {period.validation && <p>Earlier validation: {dateLabel(period.validation.start, false)} – {dateLabel(period.validation.end, false)}
              {period.validation.count != null && ` · ${period.validation.count.toLocaleString()} matches`}.</p>}
            <MetricTable metrics={validMetrics(period.metrics)} selected={period.selected_model} />
          </section>)}
        </details>}
        {calibration.length > 0 && <details className={styles.notes}>
          <summary>Did the home-win chances match past outcomes?</summary>
          <p>{rollingEvaluation ? "Pooled historical forecasts from the selected policy" : "Historical test forecasts"} grouped by home-win probability. Compare the average forecast with how often the home team actually won. Small groups are less reliable.</p>
          <div className={styles.tableWrap}><table className={styles.metricTable}>
            <caption>{rollingEvaluation ? "Selected policy" : "Selected model"} · historical home-win calibration check</caption>
            <thead><tr><th scope="col">Forecast band</th><th scope="col">Matches</th><th scope="col">Average forecast</th><th scope="col">Observed home wins</th></tr></thead>
            <tbody>{calibration.map((bin, index) => <tr key={index}><th scope="row">{percent(bin.lower, 0)}–{percent(bin.upper, 0)}</th>
              <td>{bin.count}</td><td>{percent(bin.predicted as number)}</td><td>{percent(bin.observed as number)}</td></tr>)}</tbody>
          </table></div>
        </details>}
        <Notes items={data.evaluation.limitations ?? []} title="Evaluation limitations" />
      </section>
      <footer className={styles.footer}><span>LocalSportsReel · Predictions with context.</span><span>Statistical forecasts · No LLM key required</span></footer>
    </>}
  </main>;
}
