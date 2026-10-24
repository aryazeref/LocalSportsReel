"use client";  // Tells Next.js that this component runs in the browser and can use React state and effects.

// A Client Component can respond to clicks and update the browser immediately.
// Later we can move non-interactive sections into Next.js Server Components.
import { useEffect, useState } from "react"; // React hooks for state and side effects
import type { FeedResponse, Moment, Story } from "../lib/types"; // Built-in TypeScript types for the API responses and data structures

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const cities = ["Oulu", "Rovaniemi", "Tampere", "Helsinki"];
const sports = ["All", "Ice hockey", "Football", "Basketball"];

// Function that transforms sport names into emoji icons for display in the UI.
function sportIcon(sport: string): string {
  if (sport === "Ice hockey") return "🏒";
  if (sport === "Football") return "⚽";
  if (sport === "Basketball") return "🏀";
  return "🏅";
}

// Turns timestamp into a readable date format.
function momentDate(value: string): string {
  return new Intl.DateTimeFormat("en-GB", { month: "short", day: "numeric" }).format(new Date(value));
}

function MomentCard({ moment, featured, onOpen }: {
  moment: Moment;
  featured: boolean;
  onOpen: (moment: Moment) => void;
}) {
  //const styleClass = moment.sport === "Ice hockey" ? "ice" : moment.sport === "Football" ? "football" : "basketball";
  let styleClass;
  switch(moment.sport) {
    case "Ice Hockey": styleClass = "ice"; break; 
    case "Football": styleClass = "football"; break;
    case "Basketball": styleClass = "basketball"; break;
    default: 
    styleClass = "basketball"; break;
  }
  return (
    <article className={`momentCard ${featured ? "featured" : ""}`}>
      {/* This is deliberately an illustrated event card, NOT a video. */}
      <div className={`momentArt ${styleClass}`}>
        <div className="artCircle artCircleOne" />
        <div className="artCircle artCircleTwo" />
        <span className="sportArt" aria-hidden="true">{sportIcon(moment.sport)}</span>
        <div className="artTop">
          <span className="artChip">✦ {moment.sport}</span>
          <span className="artChip darkChip">{moment.city}</span>
        </div>
        <span className="artBottom">DATA-DRIVEN STORY · NO VIDEO FOOTAGE</span>
      </div>
      <div className="momentBody">
        <div className="eyebrow">{moment.team} <span>·</span> {momentDate(moment.happened_at)}</div>
        <h3>{moment.title}</h3>
        <p><strong>{moment.athlete}</strong> · {moment.moment_type} · {moment.score}</p>
        <div className="momentFooter">
          <span className="distance">⌖ {moment.distance_km.toFixed(0)} km away</span>
          <button className="storyButton" onClick={() => onOpen(moment)} aria-label={`Read the AI story for ${moment.title}`}>
            Explore story <span aria-hidden="true">↗</span>
          </button>
        </div>
      </div>
    </article>
  );
}

export default function HomePage() {
  // React state is the current screen's memory: update it, then React redraws.
  const [city, setCity] = useState("Oulu"); // city = current value, setCity = function to update it
  const [radius, setRadius] = useState(50);
  const [sport, setSport] = useState("All");
  const [feed, setFeed] = useState<FeedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedMoment, setSelectedMoment] = useState<Moment | null>(null);
  const [story, setStory] = useState<Story | null>(null);
  const [storyLoading, setStoryLoading] = useState(false);

  // Whenever a filter changes, load a fresh filtered list from FastAPI.
  useEffect(() => {
    const controller = new AbortController();
    async function loadFeed() {
      setLoading(true);
      setError(null);
      try {
        const query = new URLSearchParams({ city, radius_km: String(radius), sport });
        const response = await fetch(`${API}/api/feed?${query}`, { signal: controller.signal });
        if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`);
        setFeed((await response.json()) as FeedResponse);
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "Unable to load local moments");
          setFeed(null);
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void loadFeed();
    return () => controller.abort();
  }, [city, radius, sport]);

  async function openStory(moment: Moment) {
    setSelectedMoment(moment);
    setStory(null);
    setStoryLoading(true);
    try {
      const response = await fetch(`${API}/api/stories/${encodeURIComponent(moment.id)}`, { method: "POST" });
      if (!response.ok) throw new Error(`Could not create story (HTTP ${response.status})`);
      setStory((await response.json()) as Story);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate the story");
      setSelectedMoment(null);
    } finally {
      setStoryLoading(false);
    }
  }

  return (
    <main className="appShell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Local SportsReel homepage">
          <span className="brandMark">↗</span><span>KUCING<span className="brandThin">MAEW</span><span className="brandDot">.</span></span>
        </a>
        <span className="topbarRight"><span className="pulse" /> THE STORIES NEAR YOU <span className="beta">HACKATHON DEMO</span></span>
      </header>

      <section className="hero">
        <div className="heroText">
          <div className="sectionLabel"><span className="labelDash" /> A NEW WAY TO FOLLOW SPORTS</div>
          <h1>THE BEST MOMENTS<br /><span>HAPPEN <em>CLOSER.</em></span></h1>
          <p>Discover the remarkable players, unforgettable plays, and local stories happening right around you. You don’t have to follow the league to feel the game.</p>
          <div className="heroPills"><span>◎ Local-first</span><span>✦ AI storytelling</span><span>↗ Hidden talent</span></div>
        </div>
        <div className="heroGraphic" aria-hidden="true"><div className="orbit orbitOne" /><div className="orbit orbitTwo" /><span className="heroAsterisk">✳</span><div className="heroSticker">YOUR CITY<br />YOUR GAME<span>↗</span></div></div>
      </section>

      <section className="discover" aria-labelledby="discover-heading">
        <div className="sectionHeading"><div><div className="sectionLabel"><span className="labelDash" /> THE LOCAL PULSE</div><h2 id="discover-heading">Around your city<span className="headingDot">.</span></h2><p>A feed of moments you might have missed.</p></div><div className="demoBanner">ⓘ All match events are fictional demo data. No licensed footage is included.</div></div>
        <div className="filters">
          <label>YOUR CITY <select value={city} onChange={(e) => setCity(e.target.value)}>{cities.map((c) => <option key={c} value={c}>{c}</option>)}</select></label>
          <label>SPORT <select value={sport} onChange={(e) => setSport(e.target.value)}>{sports.map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
          <label className="radiusLabel">DISTANCE <div className="rangeRow"><input aria-label="Discovery distance" type="range" min="5" max="500" step="5" value={radius} onChange={(e) => setRadius(Number(e.target.value))} /><span>{radius} KM</span></div></label>
          <span className="resultCount">{loading ? "SEARCHING…" : `${feed?.total ?? 0} MOMENTS FOUND`}</span>
        </div>

        {error && <div className="errorMessage" role="alert">{error}. Make sure the Python backend is running at {API}.</div>}
        {loading && <div className="statusMessage">Finding nearby stories…</div>}
        {!loading && feed?.moments.length === 0 && <div className="statusMessage">No moments match these filters. Try a different sport or increase your distance.</div>}
        {!loading && feed && feed.moments.length > 0 && <div className="cardsGrid">{feed.moments.map((moment, index) => <MomentCard key={moment.id} moment={moment} featured={index === 0} onOpen={(m) => void openStory(m)} />)}</div>}
      </section>

      <section className="vision"><div><span className="visionKicker">THE NEXT CHAPTER</span><h2>Big stories. <span>Small towns.</span></h2><p>Next: authorized video clips, athlete-follow feeds, short audio briefings, and match-impact simulations. Built for the communities behind every game.</p></div><div className="visionStamp">BEYOND<br />THE<br />SCOREBOARD <span>↗</span></div></section>
      <footer className="footer"><span>LOCALREEL © 2026 · CONCEPT PROTOTYPE</span><span>BUILT FOR KALEVA MEDIA HACKATHON</span></footer>

      {selectedMoment && <div className="modalBackdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setSelectedMoment(null); }}>
        <section className="storyModal" role="dialog" aria-modal="true" aria-label="Sports story">
          <div className="modalTop"><span className="sectionLabel">✦ MOMENT EXPLAINED</span><button className="closeButton" onClick={() => setSelectedMoment(null)} aria-label="Close story">×</button></div>
          <p className="modalMetadata">{selectedMoment.city} · {selectedMoment.sport} · {selectedMoment.league}</p>
          {storyLoading ? <p className="modalLoading">Preparing the grounded story…</p> : story && <>
            <h2>{story.headline}</h2><p className="narration">{story.narration}</p>
            <div className="storyNotice">{story.disclaimer}</div>
            <h3 className="evidenceHeading">Evidence used</h3>
            <ul className="evidenceList">{story.evidence.map((f) => <li key={f.id}><span>↳</span> {f.text}<small>{f.source_id}</small></li>)}</ul>
            <div className="storyMeta">{story.mode === "llm_draft" ? "AI-GENERATED DRAFT · REQUIRES HUMAN REVIEW" : "GROUNDED DEMONSTRATION TEMPLATE"}</div>
          </>}
        </section>
      </div>}
    </main>
  );
}
