"use client";

import { useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import Link from "next/link";
import type { Reel } from "../lib/reel-feed";
import { reelScore } from "../lib/reel-feed";
import {
  MAX_REEL_COMMENTS, type ReelComment, readReelComments, saveReelComments,
} from "../lib/reel-comments";
import styles from "./reel-viewer.module.css";

type Props = { reels: Reel[] };

function localDate(value: string): string {
  const date = new Date(value);
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium", timeZone: "Europe/Helsinki",
  }).format(date);
}

/** Every goal has a different browser-local comments thread. */
function ReelComments({ reel }: { reel: Reel }) {
  const [comments, setComments] = useState<ReelComment[]>(() => readReelComments(reel.id));
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [warning, setWarning] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const author = name.trim(), body = message.trim();
    if (!author || !body || author.length > 40 || body.length > 500) return;
    const updated = [...comments, {
      id: crypto.randomUUID(), author, body, createdAt: new Date().toISOString(),
    }].slice(-MAX_REEL_COMMENTS);
    setComments(updated);
    setWarning(saveReelComments(reel.id, updated) ? "" : "Browser storage is unavailable. This comment won't be saved.");
    setMessage("");
  }

  return <aside className={styles.comments} aria-label={"Comments for " + reel.title}>
    <div className={styles.commentsHeader}>
      <span className={styles.eyebrow}>FAN REACTIONS</span>
      <h3>Comments <small>({comments.length})</small></h3>
      <p>Talk about this specific goal or match.</p>
    </div>
    <div className={styles.commentList} aria-live="polite">
      {comments.length === 0 ? <p className={styles.noComments}>
        No comments on this device yet. What did you think of this moment?
      </p> : [...comments].reverse().map(item => <article className={styles.comment} key={item.id}>
        <div className={styles.commentTop}>
          <strong>{item.author}</strong>
          <time dateTime={item.createdAt}>{localDate(item.createdAt)}</time>
        </div>
        <p>{item.body}</p>
      </article>)}
    </div>
    <form onSubmit={submit} className={styles.commentForm}>
      <label htmlFor={"reel-name-" + reel.id}>Display name</label>
      <input id={"reel-name-" + reel.id} autoComplete="nickname" maxLength={40} required
        value={name} placeholder="Your name"
        onChange={event => setName(event.target.value)} />
      <label htmlFor={"reel-text-" + reel.id}>Your reaction</label>
      <textarea id={"reel-text-" + reel.id} rows={3} maxLength={500} required
        value={message} placeholder="What a goal! …"
        onChange={event => setMessage(event.target.value)} />
      <div className={styles.submitRow}>
        <span>{message.length}/500</span>
        <button type="submit" disabled={!name.trim() || !message.trim()}>Post locally ↗</button>
      </div>
      {warning && <p role="alert" className={styles.warning}>{warning}</p>}
    </form>
    <p className={styles.privateNote}>
      <strong>Demo discussion:</strong> Comments are saved only in this browser,
      not visible to other fans. Public comments require accounts and moderation.
    </p>
  </aside>;
}

/**
 * Only the selected reel has a video player; no other video auto-plays.
 * When there is no rights-approved clip, show "Video unavailable".
 * Never offer file selection or pretend an illustration is genuine footage.
 */
export default function ReelViewer({ reels }: Props) {
  const [selectedId, setSelectedId] = useState(reels[0]?.id || "");
  const activeIndex = Math.max(0, reels.findIndex(item => item.id === selectedId));
  const active = reels[activeIndex];
  if (!active) return <p className={styles.empty}>No recent goal or match reels are available yet.</p>;

  function choose(next: number) {
    const target = reels[Math.max(0, Math.min(reels.length - 1, next))];
    if (!target) return;
    setSelectedId(target.id);
  }

  function onKeyboard(event: KeyboardEvent<HTMLElement>) {
    const tag = (event.target as HTMLElement).tagName;
    if (["INPUT", "TEXTAREA", "SELECT", "BUTTON", "VIDEO"].includes(tag)) return;
    if (event.key === "ArrowDown" || event.key === "ArrowRight") {
      event.preventDefault();
      choose(activeIndex + 1);
    } else if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
      event.preventDefault();
      choose(activeIndex - 1);
    }
  }

  const videoSrc = active.videoSrc;
  return <section className={styles.reels} aria-label="Hockey reel player" onKeyDown={onKeyboard}>
    <div className={styles.toolbar}>
      <div>
        <span className={styles.eyebrow}>REAL MATCH MOMENTS</span>
        <h2>Pick a reel<span>.</span></h2>
      </div>
      <p>Clip {activeIndex + 1} of {reels.length}</p>
    </div>
    <div className={styles.content}>
      <nav className={styles.playlist} aria-label="Available match reels">
        {reels.map((reel, index) => <button key={reel.id} type="button"
          className={styles.playlistItem + (reel.id === active.id ? " " + styles.activeItem : "")}
          aria-current={reel.id === active.id ? "true" : undefined}
          onClick={() => choose(index)}>
          <span className={styles.index}>{String(index + 1).padStart(2, "0")}</span>
          <span className={styles.playlistText}>
            <strong>{reel.title}</strong>
            <small>{reel.homeTeam} – {reel.awayTeam} · {reelScore(reel)}</small>
          </span>
          <span className={styles.mediaSymbol} aria-label={reel.videoSrc ? "Clip available" : "Video not connected"}>
            {reel.videoSrc ? "▶" : "○"}
          </span>
        </button>)}
      </nav>
      <div className={styles.stage}>
        <div className={styles.portrait}>
          <div className={styles.videoArea}>
            {videoSrc ? <video key={videoSrc} className={styles.video} src={videoSrc}
              controls playsInline preload="metadata"
              aria-label={"Reel video: " + active.title}>
              Your browser does not support video playback.
            </video> : <div className={styles.videoEmpty}>
              <div className={styles.rinkLines} aria-hidden="true" />
              <span className={styles.hockeyIcon} aria-hidden="true">🏒</span>
              <strong>Video unavailable</strong>
              <p>Highlight footage is not available for this moment. Match details and comments remain accessible.</p>
            </div>}
          </div>
          <div className={styles.videoOverlay}>
            <span className={styles.clipTag}>{active.kind === "goal" ? "GOAL MOMENT" : "MATCH RECAP"}</span>
            <h3>{active.title}</h3>
            <p>{active.subtitle}</p>
            <div className={styles.scorePill}>{active.homeTeam} <strong>{reelScore(active)}</strong> {active.awayTeam}</div>
          </div>
        </div>
        <div className={styles.controls}>
          <button type="button" disabled={activeIndex === 0} onClick={() => choose(activeIndex - 1)}>↑ Previous</button>
          <span>{localDate(active.start)} · {active.city || "City unavailable"}</span>
          <button type="button" disabled={activeIndex === reels.length - 1}
            onClick={() => choose(activeIndex + 1)}>Next ↓</button>
        </div>
        <div className={styles.moreLinks}>
          <Link href="/liiga">Match centre &amp; Fan Zone ↗</Link>
          <Link href="/predictions">Explore predictions ↗</Link>
        </div>
        <p className={styles.clipNotice}>
          Only rights-approved clips can be published. Liiga event data does not automatically
          grant footage rights. No match videos are included in this demo.
        </p>
      </div>
      <ReelComments key={active.id} reel={active} />
    </div>
  </section>;
}
