"use client";

import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import DemoCheckout, { type CheckoutProduct } from "../../components/demo-checkout";
import Paywall from "../../components/paywall";
import { activateDemoPremium, hasReportAccess, purchaseDemoReport, reportId as getReportId, resetDemoPurchases } from "../../lib/entitlements";
import { useEntitlements } from "../../lib/use-entitlements";
import type { Forecast, ImpactResponse, Outcome, PredictionsResponse } from "../../lib/prediction-types";
import { emptyImpactSnapshot, impactSnapshotKey, parseImpactSnapshot, readStoredImpact,
  saveImpactSnapshot, subscribeImpactSnapshots, validImpact } from "../../lib/impact-snapshot";
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

function outcomeLabel(outcome: Outcome, fixture: Forecast): string {
  const winner = outcome.startsWith("home") ? fixture.home_team.name : fixture.away_team.name;
  return `${winner} wins ${outcome.endsWith("regulation") ? "in regulation" : "in extra time"}`;
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

function ForecastCard({ fixture, selected, unlocked, onSelect }: { fixture: Forecast; selected: boolean; unlocked: boolean; onSelect: () => void }) {
  const { probabilities, home_team: home, away_team: away } = fixture;
  return <article className={`${styles.fixtureCard} ${selected ? styles.selectedCard : ""}`}>
    <button className={styles.fixtureChoice} onClick={onSelect} aria-pressed={selected}
      aria-controls="scenario-section" aria-label={`Explore impact: ${home.name} vs ${away.name}`}>
      <span className={styles.fixtureTop}><time dateTime={fixture.start}>{dateLabel(fixture.start)}</time><span>{selected ? "SELECTED" : "PRE-MATCH"}</span></span>
      <span className={styles.matchup}><strong>{home.name}</strong><span>vs</span><strong>{away.name}</strong></span>
      <span className={styles.winNumbers}><span>{percent(probabilities.home_win)}</span><span>{percent(probabilities.away_win)}</span></span>
      <span className={styles.winBar} aria-hidden="true"><span style={{ width: percent(probabilities.home_win, 4) }} /></span>
      <span className={styles.winLabels}><span>Home win</span><span>Away win</span></span>
      <span className={styles.explore}>{unlocked ? (selected ? "Viewing advanced report" : "Open advanced report")
        : selected ? "View report preview" : "Preview advanced report"}<span aria-hidden="true">↗</span></span>
    </button>
    {unlocked && <dl className={styles.outcomeBreakdown}>
      {OUTCOMES.map(outcome => <div key={outcome}><dt>{OUTCOME_LABELS[outcome]}</dt><dd>{percent(probabilities[outcome])}</dd></div>)}
    </dl>}
    <p className={styles.cardFootnote}>{fixture.features?.cold_start
      ? "Limited team history · interpret cautiously"
      : unlocked ? "Final-win chances include overtime and shootouts" : "Advanced outcome breakdown available in the full report"}</p>
  </article>;
}

export default function PredictionsPage() {
  const entitlements = useEntitlements();
  const [checkoutProduct, setCheckoutProduct] = useState<CheckoutProduct | null>(null);
  const [accessNotice, setAccessNotice] = useState("");
  const [reload, setReload] = useState(0);
  const [forecastResult, setForecastResult] = useState<{
    key: number; data: PredictionsResponse | null; error: string | null;
  } | null>(null);
  const loading = forecastResult?.key !== reload;
  const data = forecastResult?.data ?? null;
  const error = loading ? null : forecastResult.error;
  const [selectedGame, setSelectedGame] = useState<number | null>(null);
  const [selectedOutcome, setSelectedOutcome] = useState<Outcome>("home_regulation");
  // Points-only top-four comparison: this is not an official playoff forecast.
  const topN = 4;
  const [impactResult, setImpactResult] = useState<{
    key: string; data: ImpactResponse | null; error: string | null;
  } | null>(null);
  const [impactRetry, setImpactRetry] = useState(0);
  const [showAllFixtures, setShowAllFixtures] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    async function loadForecasts() {
      try {
        const response = await fetch(`${API_BASE}/api/liiga/predictions?limit=12`, { signal: controller.signal });
        const result = await readResponse<PredictionsResponse>(response);
        if (!Array.isArray(result.fixtures) || !result.model || !result.evaluation || !result.fixtures.every(validForecast)) {
          throw new Error("The forecast response has an unexpected format.");
        }
        if (controller.signal.aborted) return;
        setForecastResult({ key: reload, data: result, error: null });
        setSelectedGame(current => current != null && result.fixtures.some(fixture => fixture.game_id === current)
          ? current : result.fixtures[0]?.game_id ?? null);
      } catch (caught) {
        if (!controller.signal.aborted) setForecastResult(previous => ({ key: reload, data: previous?.data ?? null,
          error: caught instanceof Error ? caught.message : "Forecasts are unavailable." }));
      }
    }
    void loadForecasts();
    return () => controller.abort();
  }, [reload]);

  const fixture = data?.fixtures.find(item => item.game_id === selectedGame);
  // Season plus game ID prevents a report unlock carrying over to another season.
  const selectedReportId = fixture ? getReportId(fixture.season, fixture.game_id) : null;
  const selectedReportUnlocked = selectedReportId ? hasReportAccess(entitlements, selectedReportId) : false;
  const forecastVersion = data?.generated_at;
  const modelVersion = data?.model.model_version;
  const snapshotContext = useMemo(() => fixture && modelVersion ? {
    apiBase: API_BASE, season: fixture.season, gameId: fixture.game_id,
    homeId: fixture.home_team.team_id, awayId: fixture.away_team.team_id,
    modelVersion, topN,
  } : null, [fixture, modelVersion, topN]);
  const snapshotKey = snapshotContext ? impactSnapshotKey(snapshotContext) : "";
  const getStoredSnapshot = useCallback(() => readStoredImpact(snapshotKey), [snapshotKey]);
  const storedSnapshot = useSyncExternalStore(subscribeImpactSnapshots, getStoredSnapshot, emptyImpactSnapshot);
  const savedImpact = useMemo(() => snapshotContext ? parseImpactSnapshot(storedSnapshot, snapshotContext) : null,
    [snapshotContext, storedSnapshot]);
  const impactRequestKey = JSON.stringify([selectedGame, topN, forecastVersion, modelVersion, impactRetry]);
  // Keep the existing simulation API behind the same demo access rule as its report UI.
  const canLoadImpact = selectedGame != null && Boolean(forecastVersion) && selectedReportUnlocked;
  const impactLoading = canLoadImpact && impactResult?.key !== impactRequestKey;
  const impact = canLoadImpact && impactResult?.key === impactRequestKey ? impactResult.data : null;
  const impactError = canLoadImpact && impactResult?.key === impactRequestKey ? impactResult.error : null;

  useEffect(() => {
    const controller = new AbortController();
    if (selectedGame == null || !forecastVersion || !snapshotContext || !selectedReportUnlocked) return () => controller.abort();
    const context = snapshotContext;
    async function loadImpact() {
      try {
        const query = new URLSearchParams({ top_n: String(topN), simulations: "4000" });
        if (modelVersion) query.set("model_version", modelVersion);
        const response = await fetch(`${API_BASE}/api/liiga/predictions/${selectedGame}/impact?${query}`, { signal: controller.signal });
        const result = await readResponse<ImpactResponse>(response);
        if (!validImpact(result, context)) {
          throw new Error("The league-impact response has an unexpected format.");
        }
        if (!controller.signal.aborted) {
          setImpactResult({ key: impactRequestKey, data: result, error: null });
          saveImpactSnapshot(context, result);
        }
      } catch (caught) {
        if (!controller.signal.aborted) setImpactResult({ key: impactRequestKey, data: null,
          error: caught instanceof Error ? caught.message : "League-impact calculations are unavailable." });
      }
    }
    void loadImpact();
    return () => controller.abort();
  }, [selectedGame, topN, forecastVersion, modelVersion, impactRetry, impactRequestKey, snapshotContext, selectedReportUnlocked]);

  const activeImpact = impact ?? savedImpact;
  const showingSnapshot = Boolean(activeImpact && (!impact || loading || error));
  const scenario = activeImpact?.scenarios.find(item => item.outcome === selectedOutcome);
  const baseline = [...(activeImpact?.baseline ?? [])].sort((a, b) => a.expected_rank - b.expected_rank || a.name.localeCompare(b.name));
  const scenarioByTeam = new Map((scenario?.teams ?? []).map(team => [team.team_id, team]));
  const selectedLabel = fixture ? outcomeLabel(selectedOutcome, fixture) : "";
  // Rival movements use existing scenario results, never new calculations.
  const competingTeams = fixture && scenario ? baseline
    .filter(team => team.team_id !== fixture.home_team.team_id && team.team_id !== fixture.away_team.team_id)
    .map(before => ({ before, after: scenarioByTeam.get(before.team_id) }))
    .filter(item => item.after !== undefined)
    .sort((a, b) => Math.abs(b.after!.delta_rank) - Math.abs(a.after!.delta_rank) || a.before.name.localeCompare(b.before.name))
    .slice(0, 5) : [];
  const visibleFixtures = showAllFixtures ? data?.fixtures ?? [] : (data?.fixtures ?? []).slice(0, 6);

  function confirmCheckout(product: CheckoutProduct) {
    // The checkout only updates the shared browser store; it never contacts a payment service.
    if (product.kind === "report") {
      purchaseDemoReport(product.reportId);
      setAccessNotice(`${product.title} is unlocked in this browser.`);
    } else {
      activateDemoPremium();
      setAccessNotice("Premium demo access is active. All current reports are unlocked in this browser.");
    }
    setCheckoutProduct(null);
  }

  function resetAccess() {
    resetDemoPurchases();
    setAccessNotice("Demo purchases reset. Free access is active.");
  }

  return <main className={styles.page}>
    <header className={styles.header}>
      <div><p className={styles.eyebrow}>BEFORE THE BUZZER · LIIGA FORECASTS</p>
        <h1>Who wins.<br /><span>What changes.</span></h1>
        <p className={styles.description}>Pick a matchup, see each team’s chances, and discover what a win or loss could mean for the rest of the league.</p>
      </div>
      <div className={styles.headerActions}>
        <span className={styles.experimental}>Experimental forecasts</span>
        <button className={styles.primaryButton} disabled={loading} onClick={() => setReload(value => value + 1)}>
          {loading ? "Preparing forecasts…" : "Refresh forecasts"}
        </button>
      </div>
    </header>

    <div className={styles.demoAccessBar}>
      <span className={styles.accessStatus}>Demo access: {entitlements.plan === "premium" ? "Premium · all current advanced reports unlocked"
        : `Free${entitlements.purchasedReportIds.length ? ` · ${entitlements.purchasedReportIds.length} report${entitlements.purchasedReportIds.length === 1 ? "" : "s"} unlocked` : ""}`}</span>
      {accessNotice && <span className={styles.accessNotice} role="status">{accessNotice}</span>}
      <Link href="/pricing">View plans</Link>
      <button type="button" onClick={resetAccess}>Reset demo purchases</button>
    </div>

    {loading && <div role="status" className={styles.loading}><span className={styles.spinner} aria-hidden="true" />
      <div><strong>Preparing the next matchday</strong><p>Getting the latest match forecasts ready.</p></div>
    </div>}
    {error && <div role="alert" className={styles.error}><strong>{data ? "Could not refresh forecasts." : "Forecasts are unavailable."}</strong> {error}
      <button className={styles.textButton} onClick={() => setReload(value => value + 1)}>Try again</button></div>}

    {data && <>
      <div className={styles.contextStrip}>
        <span><strong>{data.season - 1}–{String(data.season).slice(-2)}</strong> regular season</span>
        <span><strong>{data.fixtures.length}</strong> upcoming forecasts</span>
        <span>Pre-match estimates</span>
        <a href="#scenario-section">See what happens next <span aria-hidden="true">↗</span></a>
      </div>
      <p className={styles.forecastNote}>These chances are estimates, not guarantees. Injuries, lineups and starting goalies can change a match.</p>


      <section className={styles.forecastsSection} aria-labelledby="forecast-heading">
        <div className={styles.sectionHeading}><div><p className={styles.eyebrow}>THE NEXT MATCHUPS</p><h2 id="forecast-heading">Who has the edge?</h2></div>
          <span className={styles.sectionTag}>WIN PROBABILITIES</span></div>
        {data.fixtures.length === 0 && <p className={styles.notice}>No upcoming matches are available for prediction. Completed and live games are not shown as pre-match forecasts.</p>}
        <div className={styles.fixtureGrid}>{visibleFixtures.map(item => <ForecastCard key={`${item.season}-${item.game_id}`} fixture={item}
          selected={item.game_id === selectedGame} unlocked={hasReportAccess(entitlements, getReportId(item.season, item.game_id))}
          onSelect={() => setSelectedGame(item.game_id)} />)}</div>
        {data.fixtures.length > 6 && <button className={styles.showMore} onClick={() => setShowAllFixtures(value => !value)}>
          {showAllFixtures ? "Show fewer matches" : `Show all ${data.fixtures.length} matches`} <span aria-hidden="true">{showAllFixtures ? "−" : "+"}</span>
        </button>}
        <p className={styles.updated}>Source: {data.source} · Data fetched {dateLabel(data.data_updated_at)} · Match times shown in Helsinki time</p>
      </section>

      <section id="scenario-section" className={styles.scenarioSection} aria-labelledby="scenario-heading">
        <div className={styles.sectionHeading}><div><p className={styles.eyebrow}>ONE RESULT. EVERY RIVAL.</p><h2 id="scenario-heading">What happens if…?</h2></div>
          <span className={styles.sectionTag}>WHAT IF?</span></div>
        {fixture && !selectedReportUnlocked && <Paywall matchup={`${fixture.home_team.name} vs ${fixture.away_team.name}`}
          onUnlockReport={() => setCheckoutProduct({ kind: "report", title: `${fixture.home_team.name} vs ${fixture.away_team.name}`, reportId: selectedReportId as string })}
          onGetPremium={() => setCheckoutProduct({ kind: "premium", title: "Unlimited reports and simulations" })} />}
        {!fixture && <p className={styles.notice}>Select an upcoming fixture to preview its advanced report.</p>}
        {fixture && selectedReportUnlocked && <>
        <p className={styles.scope}>Choose a possible result. See how it changes both clubs’ projected seasons—and which rivals could be affected.</p>
          <div className={styles.scenarioControls}>
            <div><span className={styles.controlLabel}>Selected match</span><h3>{fixture.home_team.name} <span>vs</span> {fixture.away_team.name}</h3>
              <p>{dateLabel(fixture.start)}</p></div>
            
          </div>
          <div className={styles.scenarioButtons} role="group" aria-label="Match outcome scenario">
            {OUTCOMES.map(outcome => <button key={outcome} className={styles.scenarioButton} aria-pressed={selectedOutcome === outcome}
              onClick={() => setSelectedOutcome(outcome)}>
              <strong>{outcome.startsWith("home") ? fixture.home_team.name : fixture.away_team.name} wins</strong>
              <span>{outcome.endsWith("regulation") ? "In regulation" : "Overtime / shootout"}</span>
              <small>{percent(fixture.probabilities[outcome])} chance · {POINTS[outcome][0]}–{POINTS[outcome][1]} league points</small>
            </button>)}
          </div>

          {historicalTable && activeImpact && <div role="status" className={styles.snapshotNotice}>
            <strong>{showingSnapshot ? "Last saved calculation · not live standings" : "Pre-game standings snapshot · not live standings"}</strong>
            <p>Showing an earlier pre-match estimate from {dateLabel(activeImpact.generated_at)}. It may not reflect the latest results.</p>
            {showingSnapshot && <>
              <p>{impactLoading || loading ? "Updating; keeping the previous table visible."
                : impactError || "The latest forecasts could not be refreshed."}</p>

              <button className={styles.textButton} disabled={impactLoading || loading} onClick={() => setImpactRetry(value => value + 1)}>Retry league impact</button>
            </>}
          </div>}
          {impactLoading && !activeImpact && <div role="status" className={styles.loading}><span className={styles.spinner} aria-hidden="true" />
            <div><strong>Projecting the remaining schedule</strong><p>Comparing this outcome with the baseline points race.</p></div></div>}
          {impactError && !activeImpact && <div role="alert" className={styles.error}><strong>League impact is unavailable.</strong> {impactError}

            <button className={styles.textButton} onClick={() => setImpactRetry(value => value + 1)}>Retry league impact</button></div>}

          {activeImpact && scenario && <>
            <div className={styles.scenarioSummary}><span className={styles.summaryIcon} aria-hidden="true">↗</span><div>
              <span className={styles.controlLabel}>If this result happens</span><h3>{selectedLabel}</h3>
              <p>Compare what this match result could mean for each club’s season.</p>
            </div></div>
            <div className={styles.impactHighlights}>
              {[fixture.home_team, fixture.away_team].map(team => {
                const before = baseline.find(row => row.team_id === team.team_id);
                const after = scenarioByTeam.get(team.team_id);
                if (!before || !after) return null;
                const movement = before.expected_rank - after.expected_rank;
                return <article key={team.team_id} className={styles.impactHighlight}>
                  <p className={styles.controlLabel}>{team.name}</p>
                  <h4>{after.expected_points.toFixed(1)} <small>projected season points</small></h4>
                  <p className={styles.beforeAfter}>Before: {before.expected_points.toFixed(1)} · Change: {signed(after.delta_points)}</p>
                  <div className={styles.impactDetail}>
                    <span>Average projected league position</span>
                    <strong>{before.expected_rank.toFixed(1)} → {after.expected_rank.toFixed(1)}</strong>
                    <small>{Math.abs(movement) < 0.05 ? "Almost unchanged" : movement > 0 ? "Moving up" : "Moving down"}</small>
                  </div>
                  <div className={styles.impactDetail}>
                    <span>Chance of finishing top {topN} on points</span>
                    <strong>{probabilityRange(after.top_n_lower, after.top_n_upper)}</strong>
                  </div>
                </article>;
              })}
            </div>
            <div className={styles.rivalSummary}>
              <h4>And what about the rivals?</h4>
              <p className={styles.scope}>Other clubs with the largest projected position changes.</p>
              <div className={styles.rivalList}>
                {competingTeams.map(({ before, after }) => after && <div key={before.team_id} className={styles.rivalRow}>
                  <strong>{before.name}</strong>
                  <span>{before.expected_rank.toFixed(1)} → {after.expected_rank.toFixed(1)}</span>
                  <span className={Math.abs(after.delta_rank) < 0.05 ? styles.muted : after.delta_rank < 0 ? styles.positive : styles.negative}>
                    {Math.abs(after.delta_rank) < 0.05 ? "Little change" : after.delta_rank < 0 ? "↑ Better" : "↓ Lower"}
                  </span>
                </div>)}
              </div>
            </div>
            <p className={styles.tableHint}>“Top {topN} on points” is not an official playoff chance. Teams tied on points may finish in a different order. These are estimates, not promises.</p>
            <p className={styles.updated}>Based on information updated {dateLabel(activeImpact.standings_updated_at)}.</p>
            </>}

          </>}
      </section>

      <footer className={styles.footer}><span>LocalSportsReel · Match probabilities and season possibilities.</span><span>Estimated outcomes · Actual results may differ</span></footer>
    </>}
    <DemoCheckout product={checkoutProduct} onClose={() => setCheckoutProduct(null)} onConfirm={confirmCheckout} />
  </main>;
}
