"use client";

/**
 * LocalSportsReel's home is a REAL Liiga match discovery page.
 *
 * The original /api/feed returned fictional Moment objects with an athlete,
 * radius and imaginary story. /api/liiga/discover instead returns actual
 * games, scores, venues and events. We never invent a story, geolocation,
 * athlete, video URL, or score to make the old card format fit.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import type { DiscoveryGame, DiscoveryResponse } from "../lib/liiga-discovery";
import { isDiscoveryResponse } from "../lib/liiga-discovery";

const API = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

function formatGameDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Match time not available";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Helsinki", dateStyle: "medium", timeStyle: "short",
  }).format(date);
}
function score(game: DiscoveryGame): string {
  if (game.status === "upcoming") return "vs";
  const a = game.home_team.goals, b = game.away_team.goals;
  return a == null || b == null ? "Score unavailable" : a + "–" + b;
}
function matchTitle(game: DiscoveryGame): string {
  return game.home_team.name + " vs " + game.away_team.name;
}
function statusLabel(status: DiscoveryGame["status"]): string {
  switch (status) {
    case "live": return "LIVE · AS REPORTED";
    case "finished": return "FINAL RESULT";
    case "upcoming": return "UPCOMING MATCH";
    default: return "MATCH CANCELLED";
  }
}
function MatchCard({ game, featured }: { game: DiscoveryGame; featured: boolean }) {
  const goals = game.goal_events.filter(event => event.scorer && event.scorer !== "Unknown scorer").slice(0, 2);
  const venue = [game.venue, game.city].filter(Boolean).join(" · ");

  return <article className={"momentCard " + (featured ? "featured" : "")}>
    <div className="momentArt ice">
      <div className="artCircle artCircleOne" />
      <div className="artCircle artCircleTwo" />
      <span className="sportArt" aria-hidden="true">🏒</span>
      <div className="artTop">
        <span className="artChip">Liiga · ice hockey</span>
        <span className="artChip darkChip">{game.city || "Venue not reported"}</span>
      </div>
      <span className="artBottom">REAL MATCH DATA · NO VIDEO FOOTAGE</span>
    </div>
    <div className="momentBody">
      <div className="eyebrow"><time dateTime={game.start}>{formatGameDate(game.start)}</time> <span>·</span> {statusLabel(game.status)}</div>
      <h3>{matchTitle(game)}</h3>
      <p className="homeScore"><strong>{score(game)}</strong></p>
      <p className="matchVenue">{venue || "Venue not available"}</p>
      {goals.length > 0 && <p className="goalSummary">
        {goals.map(goal => (goal.team_side === "home" ? game.home_team.name : game.away_team.name)
          + ": " + goal.scorer).join(" · ")}
        {game.goal_events.length > 2 ? " · More goals in match centre" : ""}
      </p>}
      <div className="momentFooter">
        <span className="distance">{game.status === "finished" ? "Full time" :
          game.status === "live" ? "Match in progress (provider)" : "Scheduled"}</span>
        <Link className="storyButton" href="/liiga">
          Match centre <span aria-hidden="true">↗</span>
        </Link>
      </div>
    </div>
  </article>;
}

function MatchSection({ title, subtitle, games, label }: {
  title: string; subtitle: string; games: DiscoveryGame[]; label: string;
}) {
  if (!games.length) return null;
  return <section className="matchGroup" aria-label={title}>
    <div className="sectionHeading">
      <div><div className="sectionLabel"><span className="labelDash" /> {label}</div>
        <h3 className="groupHeading">{title}</h3><p>{subtitle}</p></div>
      <span className="resultCount">{games.length} {games.length === 1 ? "MATCH" : "MATCHES"}</span>
    </div>
    <div className="cardsGrid">{games.map((game, index) => <MatchCard
      key={game.season + ":" + game.id} game={game} featured={index === 0}/>)}</div>
  </section>;
}

export default function HomePage() {
  // A city means the location of the venue, not a radius around the user.
  // Liiga does not provide a reliable "distance from me" field.
  const [city, setCity] = useState("");
  const [reload, setReload] = useState(0);
  const [result, setResult] = useState<{
    key: string; response: DiscoveryResponse | null; error: string | null;
  } | null>(null);
  const requestKey = JSON.stringify([city, reload]);
  const loading = result?.key !== requestKey;
  const data = loading ? null : result?.response ?? null;
  const error = loading ? null : result?.error;
  const availableCities = result?.response?.cities ?? [];

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const params = new URLSearchParams();
        if (city) params.set("city", city);
        const query = params.size ? "?" + params.toString() : "";
        const response = await fetch(API + "/api/liiga/discover" + query, { signal: controller.signal });
        if (!response.ok) {
          let detail = "Liiga data is currently unavailable (HTTP " + response.status + ").";
          try {
            const body: unknown = await response.json();
            if (body && typeof body === "object" && "detail" in body
              && typeof (body as { detail: unknown }).detail === "string") {
              detail = (body as { detail: string }).detail;
            }
          } catch { /* Provider/proxy may return plain text. */ }
          throw new Error(detail);
        }
        const payload: unknown = await response.json();
        if (!isDiscoveryResponse(payload)) throw new Error("Unexpected Liiga match format.");
        if (!controller.signal.aborted) setResult({ key: requestKey, response: payload, error: null });
      } catch (reason) {
        if (!controller.signal.aborted) setResult({
          key: requestKey, response: null,
          error: reason instanceof Error ? reason.message : "Could not load matches.",
        });
      }
    }
    void load();
    return () => controller.abort();
  }, [city, reload, requestKey]);

  const total = data ? data.live.length + data.recent.length + data.upcoming.length : 0;
  return <main className="appShell">
    <section className="hero">
      <div className="heroText">
        <div className="sectionLabel"><span className="labelDash" /> FINNISH HOCKEY, CLOSER TO HOME</div>
        <h1>YOUR CITY.<br /><span>YOUR <em>GAME.</em></span></h1>
        <p>Discover real Liiga results and upcoming games, follow your favourite clubs and explore what each match means for the season.</p>
        <div className="heroPills">
          <span>◎ Real Liiga matches</span><span>↗ Matchday community</span><span>✦ Predictions</span>
        </div>
      </div>
      <div className="heroGraphic" aria-hidden="true">
        <div className="orbit orbitOne"/><div className="orbit orbitTwo"/>
        <span className="heroAsterisk"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round"><path d="M12 2v20M2 12h20M5 5l14 14M5 19 19 5"/></svg></span>
        <div className="heroSticker">YOUR CITY<br/>YOUR GAME<span>↗</span></div>
      </div>
    </section>

    <section className="discover" aria-labelledby="discover-heading">
      <div className="sectionHeading">
        <div><div className="sectionLabel"><span className="labelDash"/> THE LOCAL PULSE</div>
          <h2 id="discover-heading">Matchday near you<span className="headingDot">.</span></h2>
          <p>Latest real results and fixtures from the Liiga regular season.</p></div>
        <div className="demoBanner">
          <span className="notice-label">Match data</span>
          <span>Scores and schedules come from Liiga. These are illustrated match cards, not video highlights.</span>
        </div>
      </div>
      <div className="filters">
        <label>VENUE CITY
          <select value={city} onChange={event => setCity(event.target.value)}>
            <option value="">All cities</option>
            {availableCities.map(value => <option value={value} key={value}>{value}</option>)}
          </select>
        </label>
        <span className="sportStatic">🏒 Liiga · Ice hockey</span>
        <button type="button" className="reloadButton" onClick={() => setReload(count => count + 1)}
          disabled={loading}>{loading ? "Updating…" : "↻ Refresh"}</button>
        <span className="resultCount">{loading ? "LOADING…" : total + " MATCHES"}</span>
      </div>
      {error && <div className="errorMessage" role="alert">
        {error} Make sure FastAPI is running on {API}.</div>}
      {loading && <p className="statusMessage" role="status">Loading real Liiga fixtures…</p>}
      {data && total === 0 && <p className="statusMessage">There are no matches for this venue city in the selected season.</p>}
      {data && <>
        <MatchSection label="AS REPORTED BY LIIGA" title="Games in progress"
          subtitle="Match status and scores are based on the latest available API snapshot."
          games={data.live} />
        <MatchSection label="RECENT RESULTS" title="The latest final scores"
          subtitle="Completed matches, most recent first."
          games={data.recent} />
        <MatchSection label="LOOKING AHEAD" title="Coming up next"
          subtitle="The next scheduled games in the regular season."
          games={data.upcoming} />
        <p className="feedSource">Source: {data.source} · Fetched {formatGameDate(data.updated_at)} (Helsinki time) · Only venues with available city information can be city-filtered.</p>
      </>}
    </section>

    <section className="vision">
      <div><span className="visionKicker">FOLLOW EVERY MATCH</span>
        <h2>More than <span>the scoreboard.</span></h2>
        <p>Visit the Liiga match hub for fan reactions and match information.
          Explore predictions to see how possible results could change the league.</p>
        <div className="visionLinks"><Link href="/liiga">Liiga &amp; Fan Zone ↗</Link>
          <Link href="/predictions">Explore predictions ↗</Link></div>
      </div>
      <div className="visionStamp">BEYOND<br/>THE<br/>SCOREBOARD <span>↗</span></div>
    </section>
    <footer className="footer"><span>LOCALSPORTSREEL © 2026 · LIIGA MATCH DISCOVERY</span>
      <span>STATISTICAL FORECASTS ARE EXPERIMENTAL · NO LICENSED FOOTAGE</span></footer>
  </main>;
}
