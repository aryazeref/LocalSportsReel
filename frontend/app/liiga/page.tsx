"use client";

// This page is intentionally independent of the existing mock-data homepage.
// Keeping real matches separate prevents synthetic moments from appearing to
// be authentic Liiga events while we're still developing the integration.
import { useEffect, useState } from "react";
import styles from "./liiga.module.css";

// The frontend only depends on the SMALL contract returned by our FastAPI
// adapter, never on the huge nested JSON produced directly by Liiga.
type Team = {
  name: string;
  team_id: string | null;
  goals: number | null;
  logo_url: string | null;
};

type GoalEvent = {
  team_side: "home" | "away";
  scorer: string;
  period: number | null;
  game_time_seconds: number | null;
  has_video: boolean;
};

type LiigaGame = {
  id: number;
  season: number;
  start: string;
  status: "upcoming" | "live" | "finished";
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
  games: LiigaGame[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

function formatStart(value: string): string {
  if (!value) return "Time not available";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;

  // Dates ending in Z are UTC. Display them in Finnish local time (EET/EEST).
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Helsinki",
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function scoreText(game: LiigaGame): string {
  // Future games may have 0, null, or placeholder scores from the provider.
  // We do not show them as if the match had already been played.
  if (game.status === "upcoming") return "vs";
  return `${game.home_team.goals ?? "–"} : ${game.away_team.goals ?? "–"}`;
}

export default function LiigaPage() {
  const [data, setData] = useState<LiigaResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    // AbortController avoids updating state after navigating away from page.
    const controller = new AbortController();

    async function loadRealMatches() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`${API_BASE}/api/liiga/games?season=2027&limit=12`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`Our backend returned HTTP ${response.status}`);
        }
        const result: LiigaResponse = await response.json();
        if (!Array.isArray(result.games)) {
          throw new Error("The backend returned an unexpected data format.");
        }
        setData(result);
      } catch (caught) {
        if (controller.signal.aborted) return;
        setError(caught instanceof Error ? caught.message : "Unable to retrieve match data.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    loadRealMatches();
    return () => controller.abort();
  }, [reload]);

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <a href="/" className={styles.back}>← LocalSportsReel home</a>
          <p className={styles.eyebrow}>REAL DATA · LIIGA FINLAND</p>
          <h1>Liiga match centre</h1>
          <p className={styles.description}>
            Finnish ice hockey fixtures, scores and available goal events.
            Powered by the Liiga Stats API via our FastAPI backend.
          </p>
        </div>
        <button className={styles.refresh} disabled={loading} onClick={() => setReload(v => v + 1)}>
          {loading ? "Loading…" : "Refresh matches"}
        </button>
      </header>

      {error && (
        <div role="alert" className={styles.error}>
          <strong>Couldn't load Liiga data.</strong> {error}
          <p>Your original demo homepage is still available.</p>
        </div>
      )}

      {loading && !data && <p className={styles.notice}>Loading Liiga games…</p>}

      {data && (
        <>
          <div className={styles.meta}>
            <span>{data.count} matches</span>
            <span>2026–27 season</span>
            <span>Source: {data.source}</span>
          </div>
          {data.games.length === 0 && (
            <p className={styles.notice}>No matches were returned for this date range.</p>
          )}
          <section className={styles.grid} aria-label="Liiga matches">
            {data.games.map(game => (
              <article key={game.id} className={styles.card}>
                <div className={styles.cardHeader}>
                  <span>{formatStart(game.start)}</span>
                  <span className={game.status === "live" ? styles.live : styles.status}>
                    {game.status.toUpperCase()}
                  </span>
                </div>
                <div className={styles.scoreboard}>
                  <span className={styles.team}>{game.home_team.name}</span>
                  <strong>{scoreText(game)}</strong>
                  <span className={styles.team}>{game.away_team.name}</span>
                </div>
                <p className={styles.venue}>
                  {[game.venue, game.city].filter(Boolean).join(" · ") || "Venue not available"}
                </p>
                {game.goal_events.length > 0 && (
                  <details className={styles.details}>
                    <summary>{game.goal_events.length} goal events</summary>
                    <ul>
                      {game.goal_events.map((event, index) => (
                        <li key={`${game.id}-${index}`}>
                          {event.game_time_seconds != null
                            ? `${Math.floor(event.game_time_seconds / 60)}:${String(event.game_time_seconds % 60).padStart(2, "0")}`
                            : "Time unknown"}
                          {" · "}{event.team_side === "home" ? game.home_team.name : game.away_team.name}
                          {" · "}{event.scorer}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </article>
            ))}
          </section>
        </>
      )}

      <p className={styles.disclaimer}>
        Matches are real provider data. The existing fictional AI-story demo remains on the homepage.
        This page does not automatically reproduce broadcaster video clips.
      </p>
    </main>
  );
}
