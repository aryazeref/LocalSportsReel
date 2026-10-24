"use client";

import styles from "./paywall.module.css";

type PaywallProps = {
  matchup: string;
  onUnlockReport: () => void;
  onGetPremium: () => void;
};

/** A preview uses only known feature and simulation names; it makes no new predictions. */
export default function Paywall({ matchup, onUnlockReport, onGetPremium }: PaywallProps) {
  return <div className={styles.paywall} aria-labelledby="report-preview-title">
    <div className={styles.previewTop}><span className={styles.lock} aria-hidden="true">⌑</span>
      <span className={styles.label}>ADVANCED REPORT PREVIEW</span><span className={styles.price}>€0.49</span></div>
    <h3 id="report-preview-title">Unlock the full report</h3>
    <p className={styles.matchup}>{matchup}</p>
    <p className={styles.description}>Your free view includes the basic match winner probabilities. The existing advanced analysis for this match includes:</p>
    <ul>
      <li>Regulation and overtime probability breakdown</li>
      <li>Forecast factors and available team-history context</li>
      <li>Four outcome comparisons in the league-impact simulation</li>
      <li>Model methodology, historical evaluation and limitations</li>
    </ul>
    <p className={styles.note}>The report appears only when the relevant data is available. Forecasts are experimental, uncertain estimates, not guarantees.</p>
    <div className={styles.actions}>
      <button type="button" className={styles.primary} onClick={onUnlockReport}>Unlock report — €0.49</button>
      <button type="button" className={styles.secondary} onClick={onGetPremium}>Get Premium — €4.99/month</button>
    </div>
  </div>;
}
