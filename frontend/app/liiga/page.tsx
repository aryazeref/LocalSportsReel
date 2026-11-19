"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import MatchFanZone from "../../components/match-fan-zone";
import styles from "./liiga.module.css";

type Team = { name: string; team_id: string | null; goals: number | null; logo_url: string | null };
type GoalEvent = { team_side: "home" | "away"; scorer: string; period: number | null; game_time_seconds: number | null; has_video: boolean };
type LiigaGame = {
  id: number;
  season: number;
  start: string;
  status: "upcoming" | "live" | "finished" | "cancelled";
  home_team: Team;
  away_team: Team;
  venue: string | null;
  city: string | null;
  goal_events: GoalEvent[];
};
type LiigaResponse = {
  source: string;
  data_mode: "real";
  season: number;
  count: number;
  games_in_dataset: number;
  updated_at: string;
  games: LiigaGame[];
};
type FormResult = "W" | "L" | "D";
type TeamAnalysis = {
  team_id: string;
  name: string;
  matches_played: number;
  wins: number;
  losses: number;
  draws: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  win_percentage: number | null;
  form: FormResult[];
};
type AnalysisResponse = {
  source: string;
  data_mode: "real";
  season: number;
  updated_at: string;
  games_in_dataset: number;
  completed_games: number;
  excluded_games: number;
  scope: "regular_season_games_returned_by_provider";
  teams: TeamAnalysis[];
};

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

function currentSeason(): number {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Helsinki", year: "numeric", month: "numeric",
  }).formatToParts(new Date());
  const year = Number(parts.find(part => part.type === "year")?.value);
  const month = Number(parts.find(part => part.type === "month")?.value);
  return year + (month >= 7 ? 1 : 0);
}

function seasonLabel(season: number): string {
  return `${season - 1}–${String(season).slice(-2)}`;
}

function formatStart(value: string): string {
  if (!value) return "Time not available";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Time not available";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Helsinki", dateStyle: "medium", timeStyle: "short",
  }).format(parsed);
}

function scoreText(game: LiigaGame): string {
  if (game.status === "cancelled") return "Cancelled";
  if (game.status === "upcoming") return "vs";
  return `${game.home_team.goals ?? "–"} : ${game.away_team.goals ?? "–"}`;
}

function signed(value: number): string {
  return value > 0 ? `+${value}` : String(value);
}

async function readResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Unable to retrieve data (HTTP ${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // A proxy or upstream server may return an HTML error page.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

function Form({ results }: { results: FormResult[] }) {
  if (results.length === 0) return <span className={styles.muted}>No results yet</span>;
  return (
    <span className={styles.form} aria-label={`Recent form, latest first: ${results.join(", ")}`}>
      {results.map((result, index) => (
        <span key={index}
          className={result === "W" ? styles.win : result === "L" ? styles.loss : styles.draw}
          title={result === "W" ? "Win" : result === "L" ? "Loss" : "Draw"}>
          {result}
        </span>
      ))}
    </span>
  );
}

export default function LiigaPage() {
  const [season, setSeason] = useState(currentSeason);
  const [selectedTeam, setSelectedTeam] = useState("");
  const [reload, setReload] = useState(0);
  const [expandedMatch, setExpandedMatch] = useState<string | null>(null);
  const matchRequestKey = JSON.stringify([season, selectedTeam, reload]);
  const analysisRequestKey = JSON.stringify([season, reload]);
  const [matchResult, setMatchResult] = useState<{
    key: string; data: LiigaResponse | null; error: string | null;
  } | null>(null);
  const [analysisResult, setAnalysisResult] = useState<{
    key: string; data: AnalysisResponse | null; error: string | null;
  } | null>(null);
  // A changed request immediately hides old data without resetting state in effects.
  const loading = matchResult?.key !== matchRequestKey;
  const analysisLoading = analysisResult?.key !== analysisRequestKey;
  const data = loading ? null : matchResult.data;
  const error = loading ? null : matchResult.error;
  const analysis = analysisLoading ? null : analysisResult.data;
  const analysisError = analysisLoading ? null : analysisResult.error;

  // These requests fail independently so analysis errors do not hide matches.
  useEffect(() => {
    const controller = new AbortController();
    async function loadMatches() {
      try {
        const query = new URLSearchParams({ season: String(season), limit: "12" });
        if (selectedTeam) query.set("team_id", selectedTeam);
        const response = await fetch(`${API_BASE}/api/liiga/games?${query}`, { signal: controller.signal });
        const result = await readResponse<LiigaResponse>(response);
        if (!Array.isArray(result.games) || result.data_mode !== "real" || result.season !== season) {
          throw new Error("The match response has an unexpected format.");
        }
        if (!controller.signal.aborted) setMatchResult({ key: matchRequestKey, data: result, error: null });
      } catch (caught) {
        if (!controller.signal.aborted) setMatchResult({ key: matchRequestKey, data: null,
          error: caught instanceof Error ? caught.message : "Unable to retrieve match data." });
      }
    }
    void loadMatches();
    return () => controller.abort();
  }, [season, selectedTeam, reload, matchRequestKey]);

  useEffect(() => {
    const controller = new AbortController();
    async function loadAnalysis() {
      try {
        const response = await fetch(`${API_BASE}/api/liiga/analysis?season=${season}`, { signal: controller.signal });
        const result = await readResponse<AnalysisResponse>(response);
        if (!Array.isArray(result.teams) || result.data_mode !== "real" || result.season !== season) {
          throw new Error("The team analysis response has an unexpected format.");
        }
        if (!controller.signal.aborted) {
          setAnalysisResult({ key: analysisRequestKey, data: result, error: null });
          setSelectedTeam(current => current && !result.teams.some(team => team.team_id === current) ? "" : current);
        }
      } catch (caught) {
        if (!controller.signal.aborted) setAnalysisResult({ key: analysisRequestKey, data: null,
          error: caught instanceof Error ? caught.message : "Unable to retrieve team analysis." });
      }
    }
    void loadAnalysis();
    return () => controller.abort();
  }, [season, reload, analysisRequestKey]);

  const teams = analysis?.season === season ? analysis.teams : [];
  const activeTeam = teams.find(team => team.team_id === selectedTeam);
  const visibleTeams = selectedTeam ? teams.filter(team => team.team_id === selectedTeam) : teams;
  const newestSeason = currentSeason() + 1;
  const seasons = Array.from({ length: newestSeason - 1999 }, (_, index) => newestSeason - index);
  const busy = loading || analysisLoading;

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>THE SCORE. THE FORM. THE BIGGER PICTURE.</p>
          <h1>Liiga match centre<span>.</span></h1>
          <p className={styles.description}>Follow the fixtures. See how your team is performing. Explore team statistics calculated from real Liiga results.</p>
        </div>
        <button className={styles.refresh} disabled={busy} onClick={() => setReload(value => value + 1)}>{busy ? "Loading…" : "↻ Refresh data"}</button>
      </header>

      <section className={styles.filters} aria-label="Liiga filters">
        <label>Season
          <select value={season} onChange={event => {
            setSeason(Number(event.target.value)); setSelectedTeam("");
          }}>
            {seasons.map(value => <option key={value} value={value}>{seasonLabel(value)}</option>)}
          </select>
        </label>
        <label className={styles.teamFilter}>Follow a team
          <select value={selectedTeam} disabled={analysisLoading || teams.length === 0} onChange={event => {
            setSelectedTeam(event.target.value);
          }}>
            <option value="">All teams</option>
            {teams.map(team => <option key={team.team_id} value={team.team_id}>{team.name}</option>)}
          </select>
        </label>
        <p className={styles.filterNote}>Regular season<br /><strong>{seasonLabel(season)}</strong></p>
      </section>

      <section className={styles.analysisSection} aria-labelledby="analysis-heading" aria-busy={analysisLoading}>
        <div className={styles.sectionHeading}>
          <div><p className={styles.eyebrow}>BEYOND THE SCORE</p><h2 id="analysis-heading">{activeTeam ? `${activeTeam.name} at a glance` : "The season in numbers"}</h2></div>
          <span className={styles.sectionTag}>TEAM ANALYSIS</span>
        </div>
        {analysisLoading && <p role="status" className={styles.notice}>Calculating team statistics…</p>}
        {analysisError && <div role="alert" className={styles.error}><strong>Team analysis is unavailable.</strong> {analysisError}</div>}
        {analysis?.season === season && (
          <>
            <div className={styles.statGrid}>
              <div className={styles.statCard}><span>{activeTeam ? "Matches played" : "Completed matches"}</span>
                <strong>{activeTeam?.matches_played ?? analysis.completed_games}</strong>
                <small>{activeTeam ? "With usable final scores" : "With usable final scores in the dataset"}</small></div>
              <div className={styles.statCard}><span>{activeTeam ? "Wins / losses" : "Teams"}</span>
                <strong>{activeTeam ? `${activeTeam.wins} / ${activeTeam.losses}` : analysis.teams.length}</strong>
                <small>{activeTeam ? `${activeTeam.draws} draws · Includes overtime and shootouts` : "Represented in the provider’s games"}</small></div>
              <div className={styles.statCard}><span>{activeTeam ? "Goal difference" : "Season fixtures"}</span>
                <strong className={activeTeam && activeTeam.goal_difference > 0 ? styles.positive : undefined}>{activeTeam ? signed(activeTeam.goal_difference) : analysis.games_in_dataset}</strong>
                <small>{activeTeam ? `${activeTeam.goals_for} scored · ${activeTeam.goals_against} conceded` : "All returned regular-season games"}</small></div>
              <div className={styles.statCard}><span>{activeTeam ? "Win percentage" : "Results coverage"}</span>
                <strong>{activeTeam ? activeTeam.win_percentage == null ? "–" : `${activeTeam.win_percentage.toFixed(1)}%` : `${analysis.completed_games} / ${analysis.games_in_dataset}`}</strong>
                <small>{activeTeam ? "Wins divided by completed matches" : "Completed results / returned fixtures"}</small></div>
            </div>
            <div className={styles.tableWrap} tabIndex={0} role="region" aria-label="Team statistics, scroll horizontally for all columns">
              <table className={styles.statsTable}>
                <caption>Team statistics · {seasonLabel(season)} regular season · Listed alphabetically</caption>
                <thead><tr>
                  <th scope="col">Team</th><th scope="col"><abbr title="Played">P</abbr></th><th scope="col"><abbr title="Wins">W</abbr></th>
                  <th scope="col"><abbr title="Losses">L</abbr></th><th scope="col"><abbr title="Draws">D</abbr></th>
                  <th scope="col"><abbr title="Goals for">GF</abbr></th><th scope="col"><abbr title="Goals against">GA</abbr></th>
                  <th scope="col"><abbr title="Goal difference">GD</abbr></th><th scope="col">Win %</th>
                  <th scope="col">Last five <span className={styles.latest}>latest first</span></th>
                </tr></thead>
                <tbody>
                  {visibleTeams.map(team => <tr key={team.team_id}>
                    <th scope="row">{team.name}</th><td>{team.matches_played}</td><td>{team.wins}</td><td>{team.losses}</td><td>{team.draws}</td>
                    <td>{team.goals_for}</td><td>{team.goals_against}</td><td className={team.goal_difference > 0 ? styles.positive : undefined}>{signed(team.goal_difference)}</td>
                    <td>{team.win_percentage == null ? "–" : `${team.win_percentage.toFixed(1)}%`}</td><td><Form results={team.form} /></td>
                  </tr>)}
                  {visibleTeams.length === 0 && <tr><td colSpan={10}>No team data is available for this season.</td></tr>}
                </tbody>
              </table>
            </div>
            <p className={styles.scope}>Calculated from completed regular-season games returned by Liiga for this season, independently of the match cards below.
              Wins include overtime and shootouts. This is a team performance table; official standings and predictions are not included.
              {analysis.excluded_games > 0 && ` ${analysis.excluded_games} finished matches were excluded because required result data was missing.`}</p>
            <p className={styles.updated}>Source: {analysis.source} · Fetched {formatStart(analysis.updated_at)} (Helsinki time) · Cached for up to 2 minutes</p>
          </>
        )}
      </section>

      <section className={styles.matchesSection} aria-labelledby="matches-heading" aria-busy={loading}>
        <div className={styles.sectionHeading}>
          <div><p className={styles.eyebrow}>ON THE ICE</p><h2 id="matches-heading">{activeTeam ? `${activeTeam.name} matches` : "Fixtures & results"}</h2></div>
          {data?.season === season && <span className={styles.sectionTag}>{data.count} MATCHES</span>}
        </div>
        <p className={styles.scope}>{season === currentSeason()
          ? "Showing up to 12 matches from the past seven days onward, earliest first."
          : "Showing up to 12 matches from the selected season, earliest first."}{selectedTeam && " Filtered to your selected team."}</p>
        {error && <div role="alert" className={styles.error}><strong>Couldn&apos;t load Liiga matches.</strong> {error}</div>}
        {loading && <p role="status" className={styles.notice}>Loading Liiga matches…</p>}
        {data?.season === season && <>
          {data.games.length === 0 && <p className={styles.notice}>No matches were returned for this team and date range. Try another season or team.</p>}
          <div className={styles.grid}>
            {data.games.map(game => <article key={game.id} className={styles.card + (expandedMatch === game.season + ":" + game.id ? " " + styles.cardExpanded : "")}>
              <div className={styles.cardHeader}><time dateTime={game.start}>{formatStart(game.start)}</time>
                <span className={game.status === "live" ? styles.live : styles.status}>{game.status.toUpperCase()}</span></div>
              <div className={styles.scoreboard}><span className={styles.team}>{game.home_team.name}</span>
                <strong className={game.status === "cancelled" ? styles.cancelledScore : undefined}>{scoreText(game)}</strong><span className={styles.team}>{game.away_team.name}</span></div>
              <p className={styles.venue}>{[game.venue, game.city].filter(Boolean).join(" · ") || "Venue not available"}</p>
              {game.goal_events.length > 0 && <details className={styles.details}>
                <summary>{game.goal_events.length} goal events</summary><ul>
                  {game.goal_events.map((event, index) => <li key={`${game.id}-${index}`}>
                    {event.game_time_seconds != null ? `${Math.floor(event.game_time_seconds / 60)}:${String(event.game_time_seconds % 60).padStart(2, "0")}` : "Time unknown"}
                    {" · "}{event.team_side === "home" ? game.home_team.name : game.away_team.name}{" · "}{event.scorer}
                  </li>)}
                </ul>
              </details>}
              <button type="button" className={styles.fanButton}
                aria-expanded={expandedMatch === game.season + ":" + game.id}
                onClick={() => setExpandedMatch(current =>
                  current === game.season + ":" + game.id ? null : game.season + ":" + game.id)}>
                {expandedMatch === game.season + ":" + game.id ? "Close Fan Zone ↑" : "Open Fan Zone ↗"}
              </button>
              {expandedMatch === game.season + ":" + game.id && (
                <MatchFanZone season={game.season} gameId={game.id}
                  homeTeam={game.home_team.name} awayTeam={game.away_team.name} />
              )}
            </article>)}
          </div>
          <p className={styles.updated}>Match times are shown in Helsinki time · Fetched {formatStart(data.updated_at)}</p>
        </>}
      </section>
      <footer className={styles.footer}><span>LocalSportsReel · Real games. More context.</span><Link href="/">Explore the fictional story demo ↗</Link></footer>
    </main>
  );
}
