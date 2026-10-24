"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import type { ChatMessage, CompanionReply, CompanionTeam, TeamsResponse } from "../../lib/companion-types";
import type { Forecast, PredictionsResponse } from "../../lib/prediction-types";
import styles from "./companion.module.css";

type Tab = "chat" | "tonight" | "table" | "podcast";
type TeamStats = {
  team_id: string; name: string; matches_played: number; wins: number; losses: number;
  goals_for: number; goals_against: number; win_percentage: number | null;
};
type TeamStatsResponse = { data_mode: "real"; teams: TeamStats[] };
const API = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const FAVORITE_KEY = "localsportsreel:companion:favourite-team:v1";
const TABS: Tab[] = ["chat", "tonight", "table", "podcast"];
const PROMPTS = [
  "How is our recent form?", "Who's our next opponent?",
  "What are our chances of winning?", "Where is my team in the table?",
];

async function jsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = "Request failed (HTTP " + response.status + ").";
    try {
      const body: unknown = await response.json();
      if (body && typeof body === "object" && "detail" in body) {
        const message = (body as { detail: unknown }).detail;
        if (typeof message === "string") detail = message;
      }
    } catch { /* An upstream proxy may return an HTML error. */ }
    throw new Error(detail);
  }
  return await response.json() as T;
}

/** Treat all AI-generated content as plain text, never HTML. */
function Answer({ reply }: { reply: CompanionReply }) {
  return <div className={styles.answer}>
    <p className={styles.replyText}>{reply.text}</p>
    <div className={styles.meta}>
      <span>{reply.engine}</span><span>Fact check: {reply.verification_status}</span>
    </div>
    {reply.forecast_warning && <p className={styles.muted}>{reply.forecast_warning}</p>}
    {reply.impact_warning && <p className={styles.muted}>{reply.impact_warning}</p>}
    {reply.impact && <div className={styles.forecastPreview}>
      <strong>What-if: expected season points</strong>
      <p className={styles.muted}>From the API_integration league-impact engine.
        These are regular-season points scenarios, not exact qualification probabilities.</p>
      {reply.impact.outcomes.map(outcome => <p key={outcome.outcome}>
        {outcome.outcome.replaceAll("_", " ")}: {outcome.expected_points.toFixed(1)} expected points
        {" "}({outcome.delta_points > 0 ? "+" : ""}{outcome.delta_points.toFixed(1)} vs baseline)
      </p>)}
      <Link href="/predictions">See scenario assumptions and limitations ↗</Link>
    </div>}
    {reply.forecast && <div className={styles.forecastPreview}>
      <strong>Experimental forecast · {reply.forecast.model}</strong>
      <p>{reply.forecast.home_team}: {(reply.forecast.home_win * 100).toFixed(1)}% to win</p>
      <p>{reply.forecast.away_team}: {(reply.forecast.away_win * 100).toFixed(1)}% to win</p>
      <Link href="/predictions">Explore full forecasts ↗</Link>
    </div>}
    {reply.receipts.length > 0 && <details className={styles.receipts}>
      <summary>Verified fact receipts ({reply.receipts.length})</summary>
      <dl>{reply.receipts.map(fact => <div key={fact.id}>
        <dt>{fact.id} · {fact.label}</dt>
        <dd>{fact.value}<small> · {fact.source}</small></dd>
      </div>)}</dl>
    </details>}
    <p className={styles.muted}>Source: {reply.data_source} · {reply.data_as_of}.
      Predictions are experimental, not betting advice.</p>
  </div>;
}

export default function CompanionPage() {
  const [tab, setTab] = useState<Tab>("chat");
  const [teams, setTeams] = useState<CompanionTeam[]>([]);
  const [season, setSeason] = useState<number | null>(null);
  const [teamId, setTeamId] = useState("");
  const [teamsError, setTeamsError] = useState("");
  const [teamsLoading, setTeamsLoading] = useState(true);
  const [persona, setPersona] = useState<"buddy" | "analyst" | "stats">("buddy");
  const [language, setLanguage] = useState<"English" | "Finnish">("English");
  const [useAi, setUseAi] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [script, setScript] = useState<CompanionReply | null>(null);
  // Speech support is only relevant after the client opens Podcast.
  // Initial SSR and hydration both render the Chat tab.
  const hasSpeech = typeof window !== "undefined" && "speechSynthesis" in window;
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [forecastModel, setForecastModel] = useState("");
  const [forecastLoading, setForecastLoading] = useState(false);
  const [forecastError, setForecastError] = useState("");
  const [stats, setStats] = useState<TeamStats[]>([]);
  const [statsError, setStatsError] = useState("");
  const [statsLoading, setStatsLoading] = useState(false);
  const sequence = useRef(0);

  // Read localStorage after hydration; never include browser-only state in SSR.
  useEffect(() => {
    const controller = new AbortController();
    async function loadTeams() {
      try {
        const data = await jsonResponse<TeamsResponse>(
          await fetch(API + "/api/companion/teams", { signal: controller.signal }),
        );
        if (data.data_mode !== "real" || !Array.isArray(data.teams))
          throw new Error("Unexpected Liiga team data.");
        if (controller.signal.aborted) return;
        setTeams(data.teams);
        setSeason(data.season);
        let saved = "";
        try { saved = localStorage.getItem(FAVORITE_KEY) || ""; } catch { /* optional */ }
        const preferred = data.teams.find(item => item.id === saved)
          || data.teams.find(item => item.name.toLowerCase().includes("kärpät"))
          || data.teams[0];
        setTeamId(preferred?.id || "");
      } catch (failure) {
        if (!controller.signal.aborted)
          setTeamsError(failure instanceof Error ? failure.message : "Unable to load teams.");
      } finally {
        if (!controller.signal.aborted) setTeamsLoading(false);
      }
    }
    void loadTeams();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!teamId) return;
    try { localStorage.setItem(FAVORITE_KEY, teamId); } catch { /* optional */ }
  }, [teamId]);

  // Forget old team context when a fan switches to a different club.
  function changeTeam(nextId: string) {
    sequence.current++;
    setTeamId(nextId);
    setMessages([]);
    setScript(null);
    setForecast(null);
    setForecastLoading(true);
    setForecastError("");
    setSending(false);
    setError("");
  }

  const team = teams.find(item => item.id === teamId);
  async function ask(kind: "chat" | "brief" | "podcast", message = "") {
    if (!teamId || sending || (kind === "chat" && !message.trim())) return;
    setSending(true);
    setError("");
    const current = ++sequence.current;
    const oldMessages = messages;
    if (kind === "chat") {
      setMessages(previous => [...previous, { id: current * 2, role: "user", content: message.trim() }]);
      setDraft("");
    }
    try {
      const data = await jsonResponse<CompanionReply>(await fetch(API + "/api/companion/respond", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          team_id: teamId, season, kind, message: message.trim(),
          persona, language, use_ai: useAi,
          include_forecast: kind === "chat" &&
            /\b(predict|forecast|chances?|probabilit|win|lose|tonight|what if|what happens|impact|points)\b/i.test(message),
          include_impact: kind === "chat" &&
            /what if|what happens|league.?impact|impact on|if .* win|if .* los|scenario/i.test(message),
          history: oldMessages.slice(-12).map(item => ({
            role: item.role, content: item.content,
          })),
        }),
      }));
      if (sequence.current !== current) return;
      if (kind === "chat") {
        setMessages(previous => [...previous,
          { id: current * 2 + 1, role: "assistant", content: data.text, reply: data }]);
      } else setScript(data);
    } catch (failure) {
      if (sequence.current === current)
        setError(failure instanceof Error ? failure.message : "Companion unavailable.");
    } finally {
      if (sequence.current === current) setSending(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void ask("chat", draft);
  }

  // Read only the evaluated main prediction service, not Streamlit simulations.
  useEffect(() => {
    if (tab !== "tonight" || !teamId) return;
    const controller = new AbortController();
    async function load() {
      try {
        const query = new URLSearchParams({ team_id: teamId, limit: "1" });
        const data = await jsonResponse<PredictionsResponse>(
          await fetch(API + "/api/liiga/predictions?" + query, { signal: controller.signal }),
        );
        if (!controller.signal.aborted) {
          setForecast(data.fixtures[0] || null);
          setForecastModel(data.model.display_name);
        }
      } catch (failure) {
        if (!controller.signal.aborted)
          setForecastError(failure instanceof Error ? failure.message : "Forecast unavailable.");
      } finally {
        if (!controller.signal.aborted) setForecastLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [tab, teamId]);

  useEffect(() => {
    if (tab !== "table" || season === null) return;
    const controller = new AbortController();
    async function load() {
      try {
        const data = await jsonResponse<TeamStatsResponse>(
          await fetch(API + "/api/liiga/analysis?season=" + season, { signal: controller.signal }),
        );
        if (data.data_mode !== "real") throw new Error("Expected real Liiga statistics.");
        if (!controller.signal.aborted) setStats(data.teams);
      } catch (failure) {
        if (!controller.signal.aborted)
          setStatsError(failure instanceof Error ? failure.message : "Statistics unavailable.");
      } finally {
        if (!controller.signal.aborted) setStatsLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [tab, season]);

  useEffect(() => {
    return () => { if ("speechSynthesis" in window) window.speechSynthesis.cancel(); };
  }, []);

  function readAloud(text: string) {
    if (!hasSpeech) return;
    window.speechSynthesis.cancel();
    const voice = new SpeechSynthesisUtterance(text.replace(/\[[A-Z]\d+\]/g, ""));
    voice.lang = language === "Finnish" ? "fi-FI" : "en-GB";
    window.speechSynthesis.speak(voice);
  }

  return <main className={styles.page}>
    <header className={styles.hero}>
      <p className={styles.eyebrow}>LOCALSPORTSREEL / YOUR TEAM, EXPLAINED</p>
      <h1>Fan Companion<span>.</span></h1>
      <p>Ask about your favourite club, explore match probabilities, and hear
        fact-verified briefings. One website, using the existing Liiga API.</p>
    </header>
    <div className={styles.layout}>
      <aside className={styles.sidebar} aria-label="Fan preferences">
        <h2>Personalise</h2>
        <label>Favourite team
          <select value={teamId} onChange={event => changeTeam(event.target.value)}
            disabled={teamsLoading || !teams.length}>
            {!teams.length && <option value="">Choose a team</option>}
            {teams.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>
        {teamsLoading && <p className={styles.muted}>Loading Liiga teams…</p>}
        {teamsError && <p role="alert" className={styles.error}>{teamsError}</p>}
        <label>Style
          <select value={persona} onChange={event => setPersona(event.target.value as typeof persona)}>
            <option value="buddy">Friendly fan</option>
            <option value="analyst">Calm analyst</option>
            <option value="stats">Stats enthusiast</option>
          </select>
        </label>
        <label>Language
          <select value={language} onChange={event => setLanguage(event.target.value as typeof language)}>
            <option value="English">English</option><option value="Finnish">Suomi</option>
          </select>
        </label>
        <label className={styles.toggle}>
          <input type="checkbox" checked={useAi} onChange={event => setUseAi(event.target.checked)} />
          <span>Use configured AI model</span>
        </label>
        <p className={styles.muted}>Otherwise the companion uses its original fact-verified offline templates. AI credentials stay in FastAPI.</p>
        <nav className={styles.sidebarLinks} aria-label="Related pages">
          <Link href="/predictions">Full predictions ↗</Link>
          <Link href="/liiga">Liiga and Fan Zone ↗</Link>
          <Link href="/pricing">Pricing ↗</Link>
        </nav>
      </aside>
      <section className={styles.content}>
        <div className={styles.teamBar}>
          <div><span className={styles.eyebrow}>FOLLOWING</span>
            <h2>{team?.name || "Choose your team"}</h2>
            <p>{team?.city || "Liiga"} · {season ? String(season - 1) + "–" + String(season).slice(-2) : ""}</p>
          </div>
          <span className={styles.sourceBadge}>REAL LIIGA DATA</span>
        </div>
        <nav className={styles.tabs} aria-label="Companion sections">
          {TABS.map(key => <button key={key} aria-current={tab === key ? "page" : undefined}
            onClick={() => {
              setTab(key);
              if (key === "tonight") {
                setForecastLoading(true);
                setForecastError("");
                setForecast(null);
              }
              if (key === "table") {
                setStatsLoading(true);
                setStatsError("");
              }
            }}>{key === "table" ? "Teams" : key === "tonight" ? "Tonight" : key === "podcast" ? "Podcast" : "Chat"}</button>)}
        </nav>

        {tab === "chat" && <section className={styles.panel} aria-label="Chat with the companion">
          <div className={styles.chatWindow} aria-live="polite">
            {!messages.length && <div className={styles.empty}>
              <h3>Hi! I follow {team?.name || "your team"}.</h3>
              <p>Ask about form, fixtures and experimental match predictions.</p>
              <div className={styles.chips}>
                {PROMPTS.map(p => <button key={p} disabled={!teamId || sending}
                  onClick={() => void ask("chat", p)}>{p}</button>)}
              </div>
            </div>}
            {messages.map(msg => <article key={msg.id}
              className={msg.role === "user" ? styles.userMessage : styles.assistantMessage}>
              <strong>{msg.role === "user" ? "You" : "Fan Companion"}</strong>
              {msg.reply ? <Answer reply={msg.reply} /> : <p>{msg.content}</p>}
            </article>)}
            {sending && <p role="status" className={styles.muted}>Checking sources and writing your reply…</p>}
          </div>
          <form className={styles.chatForm} onSubmit={submit}>
            <label htmlFor="fan-chat">Ask your companion</label>
            <textarea id="fan-chat" value={draft} rows={3} maxLength={1200}
              onChange={event => setDraft(event.target.value)}
              placeholder="What happens if Kärpät wins?" disabled={sending || !teamId}/>
            <div className={styles.formActions}>
              <span>{draft.length}/1200</span>
              <button type="submit" disabled={!draft.trim() || !teamId || sending}>Send ↗</button>
            </div>
          </form>
        </section>}

        {tab === "tonight" && <section className={styles.panel} aria-label="Upcoming match">
          <h3>Next forecasted match</h3>
          <p className={styles.muted}>Probabilities come only from the evaluated prediction engine.</p>
          {forecastLoading && <p role="status">Preparing the forecast…</p>}
          {forecastError && <p role="alert" className={styles.error}>{forecastError}</p>}
          {!forecastLoading && !forecastError && !forecast && <p>No upcoming forecast is available for this team.</p>}
          {forecast && <div className={styles.matchCard}>
            <p className={styles.eyebrow}>{forecastModel} · Experimental</p>
            <h4>{forecast.home_team.name} <span>vs</span> {forecast.away_team.name}</h4>
            <p>{new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Helsinki", dateStyle: "medium", timeStyle: "short" }).format(new Date(forecast.start))} Helsinki time</p>
            <div className={styles.probabilities}>
              <div><span>{forecast.home_team.name} win</span><strong>{(forecast.probabilities.home_win * 100).toFixed(1)}%</strong></div>
              <div><span>{forecast.away_team.name} win</span><strong>{(forecast.probabilities.away_win * 100).toFixed(1)}%</strong></div>
            </div>
            {forecast.warnings.map(warning => <p className={styles.muted} key={warning}>{warning}</p>)}
            <Link href="/predictions">Compare four outcomes and league-impact scenarios ↗</Link>
          </div>}
          <p className={styles.muted}>No simulation is performed in the AI Companion. These probabilities are not betting odds or guarantees.</p>
        </section>}

        {tab === "table" && <section className={styles.panel} aria-label="Liiga performance table">
          <h3>Season performance</h3>
          <p className={styles.muted}>Completed-match statistics, not official points standings or projected final rank.</p>
          {statsLoading && <p role="status">Loading results…</p>}
          {statsError && <p role="alert" className={styles.error}>{statsError}</p>}
          {!statsLoading && stats.length > 0 && <div className={styles.tableWrap}>
            <table><thead><tr><th>Team</th><th>P</th><th>W</th><th>L</th><th>GF</th><th>GA</th><th>Win %</th></tr></thead>
              <tbody>{stats.map(item => <tr key={item.team_id}
                className={item.team_id === teamId ? styles.myTeam : ""}>
                <th scope="row">{item.name}</th><td>{item.matches_played}</td>
                <td>{item.wins}</td><td>{item.losses}</td>
                <td>{item.goals_for}</td><td>{item.goals_against}</td>
                <td>{item.win_percentage == null ? "–" : item.win_percentage.toFixed(1) + "%"}</td>
              </tr>)}</tbody>
            </table>
          </div>}
          <Link href="/liiga">Open complete Liiga dashboard ↗</Link>
        </section>}

        {tab === "podcast" && <section className={styles.panel} aria-label="Briefs and podcasts">
          <h3>Audio briefings</h3>
          <p className={styles.muted}>The Fan Companion writes fact-verified scripts.
            Your browser can read them aloud if a system voice is available.</p>
          <div className={styles.podcastButtons}>
            <button disabled={!teamId || sending} onClick={() => void ask("brief")}>Daily briefing</button>
            <button disabled={!teamId || sending} onClick={() => void ask("podcast")}>Podcast script</button>
          </div>
          {sending && <p role="status">Preparing and checking the script…</p>}
          {script && <div className={styles.script}>
            <h4>{script.kind === "podcast" ? "Podcast script" : "Daily briefing"}</h4>
            <Answer reply={script}/>
            {hasSpeech && <div className={styles.podcastButtons}>
              <button onClick={() => readAloud(script.text)}>▶ Read aloud</button>
              <button onClick={() => window.speechSynthesis.cancel()}>■ Stop</button>
            </div>}
          </div>}
        </section>}
        {error && <p role="alert" className={styles.error}>{error}</p>}
      </section>
    </div>
  </main>;
}
