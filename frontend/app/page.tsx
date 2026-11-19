"use client";

/**
 * Homepage = reels first, not a schedule of illustrated match cards.
 *
 * The metadata (goals, scorers, teams, scores) comes from the SAME Liiga
 * API/cache as our match centre and predictions. Video is deliberately
 * separate: only rights-approved clips can be played. Otherwise the UI
 * explicitly says "Video unavailable". Comments are kept browser-local.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import ReelViewer from "../components/reel-viewer";
import { isDiscoveryResponse } from "../lib/liiga-discovery";
import type { DiscoveryResponse } from "../lib/liiga-discovery";
import { reelsFromGames } from "../lib/reel-feed";

const API = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

function matchTime(value: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Helsinki", dateStyle: "medium", timeStyle: "short",
  }).format(new Date(value));
}

export default function HomePage() {
  const [city, setCity] = useState("");
  const [reload, setReload] = useState(0);
  const [result, setResult] = useState<{
    key: string; data: DiscoveryResponse | null; error: string | null;
  } | null>(null);
  const requestKey = JSON.stringify([city, reload]);
  const loading = result?.key !== requestKey;
  const data = loading ? null : result?.data ?? null;
  const error = loading ? null : result?.error;
  const knownCities = result?.data?.cities ?? [];
  const reels = data ? reelsFromGames(data) : [];

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const query = new URLSearchParams();
        if (city) query.set("city", city);
        const response = await fetch(
          API + "/api/liiga/discover" + (query.size ? "?" + query : ""),
          { signal: controller.signal },
        );
        if (!response.ok) {
          let detail = "Unable to retrieve Liiga highlights (" + response.status + ").";
          try {
            const errorBody: unknown = await response.json();
            if (errorBody && typeof errorBody === "object" && "detail" in errorBody
              && typeof (errorBody as { detail: unknown }).detail === "string")
              detail = (errorBody as { detail: string }).detail;
          } catch { /* The backend/proxy can respond with non-JSON errors. */ }
          throw new Error(detail);
        }
        const payload: unknown = await response.json();
        if (!isDiscoveryResponse(payload)) throw new Error("Unexpected Liiga response format.");
        if (!controller.signal.aborted) setResult({ key: requestKey, data: payload, error: null });
      } catch (reason) {
        if (!controller.signal.aborted) setResult({
          key: requestKey, data: null,
          error: reason instanceof Error ? reason.message : "Unable to load match highlights.",
        });
      }
    }
    void load();
    return () => controller.abort();
  }, [city, reload, requestKey]);

  return <main className="appShell">
    <section className="hero reelHero">
      <div className="heroText">
        <div className="sectionLabel"><span className="labelDash" /> REAL MATCHES · FAN REACTIONS</div>
        <h1>THE GAME.<br /><span>THE <em>MOMENT.</em></span></h1>
        <p>Catch the latest Liiga goal moments, discover the match behind each clip and talk about it with other fans—starting with a local demo discussion.</p>
        <div className="heroPills">
          <span>▶ Short-video concept</span>
          <span>🏒 Real Liiga goal data</span>
          <span>♡ Reactions for every moment</span>
        </div>
      </div>
      <div className="heroGraphic" aria-hidden="true">
        <div className="orbit orbitOne" /><div className="orbit orbitTwo" />
        <span className="heroAsterisk">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round">
            <path d="M12 2v20M2 12h20M5 5l14 14M5 19 19 5"/>
          </svg>
        </span>
        <div className="heroSticker">WATCH<br/>REACT<br/>REPEAT <span>↗</span></div>
      </div>
    </section>

    <section className="discover" aria-labelledby="reels-heading">
      <div className="sectionHeading">
        <div>
          <div className="sectionLabel"><span className="labelDash"/> HIGHLIGHT FEED</div>
          <h2 id="reels-heading">Moments worth replaying<span className="headingDot">.</span></h2>
          <p>Recent goals from actual Liiga matches, ready to be paired with approved video clips.</p>
        </div>
        <div className="demoBanner">
          <span className="notice-label">Video unavailable</span>
          <span>Real match moments and comments are available. Highlight footage is not included in this demo.</span>
        </div>
      </div>
      <div className="filters">
        <label>VENUE CITY
          <select value={city} onChange={event => setCity(event.target.value)}>
            <option value="">All Liiga cities</option>
            {knownCities.map(value => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
        <span className="sportStatic">🏒 Liiga · Ice hockey</span>
        <button type="button" className="reloadButton" disabled={loading}
          onClick={() => setReload(value => value + 1)}>
          {loading ? "Updating…" : "↻ Refresh"}
        </button>
        <span className="resultCount">{loading ? "LOADING…" : reels.length + " MOMENTS"}</span>
      </div>

      {error && <div className="errorMessage" role="alert">{error} Check the FastAPI backend at {API}.</div>}
      {loading && <p className="statusMessage" role="status">Loading the latest Liiga goal moments…</p>}
      {data && reels.length === 0 && <p className="statusMessage">
        No completed games with goal information are available for this venue city. Try all Liiga cities.
      </p>}
      {data && reels.length > 0 && <>
        <ReelViewer reels={reels} />
        <p className="feedSource">Match facts: {data.source} · Updated {matchTime(data.updated_at)} (Helsinki time).
          Highlight footage is unavailable without approved media. Comments are stored in this browser only.</p>
      </>}
    </section>

    <section className="vision">
      <div>
        <span className="visionKicker">THE NEXT MATCHDAY</span>
        <h2>See it. <span>Feel it. Discuss it.</span></h2>
        <p>Keep following the game after the highlight. Explore live scores, the fan community,
          and how the next win or loss could change the league.</p>
        <div className="visionLinks">
          <Link href="/liiga">Liiga match centre ↗</Link>
          <Link href="/predictions">What happens next? ↗</Link>
          <Link href="/companion">Ask the Fan Companion ↗</Link>
        </div>
      </div>
      <div className="visionStamp">BEYOND<br/>THE<br/>SCOREBOARD <span>↗</span></div>
    </section>
    <footer className="footer"><span>LOCALSPORTSREEL © 2026 · HOCKEY MOMENTS</span>
      <span>REAL MATCH DATA · VIDEO RIGHTS REQUIRED FOR PUBLICATION</span></footer>
  </main>;
}
