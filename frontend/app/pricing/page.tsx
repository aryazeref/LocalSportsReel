"use client";

import { useState } from "react";
import DemoCheckout, { type CheckoutProduct } from "../../components/demo-checkout";
import PricingCard from "../../components/pricing-card";
import { activateDemoPremium, resetDemoPurchases } from "../../lib/entitlements";
import { useEntitlements } from "../../lib/use-entitlements";
import styles from "./pricing.module.css";

export default function PricingPage() {
  const entitlements = useEntitlements();
  const [checkoutProduct, setCheckoutProduct] = useState<CheckoutProduct | null>(null);
  const [notice, setNotice] = useState("");

  function confirmCheckout() {
    activateDemoPremium();
    setNotice("Premium demo access is now active in this browser.");
    setCheckoutProduct(null);
  }

  function reset() {
    resetDemoPurchases();
    setNotice("Demo purchases reset. Free access is active.");
  }

  return <main className={styles.page}>
    <header className={styles.header}>
      <p className={styles.eyebrow}>SIMPLE ACCESS · DEMO PRICING</p>
      <h1>Follow the game.<br /><span>Choose your depth.</span></h1>
      <p className={styles.lede}>Schedules, results and basic match probabilities stay free. Try the advanced report flow with simulated access; no real payments are collected.</p>
    </header>

    <div className={styles.cards}>
      <PricingCard name="Free" price="€0" description="The essentials for every fan."
        features={["Schedules and final results", "Liiga team statistics", "Basic match winner probabilities", "Preview of advanced analysis", "Planned: community features"]}
        actionLabel="Explore predictions" href="/predictions" />
      <PricingCard name="Single Report" price="€0.49" cadence="per match" description="Unlock one advanced report for a match you choose."
        features={["Full probability breakdown", "How each possible result changes season projections", "Match-specific league-impact scenarios", "What it could mean for both teams and their rivals"]}
        actionLabel="Choose a match" href="/predictions#forecast-heading" />
      <PricingCard name="Premium" price="€4.99" cadence="/month" description="Unlimited access to currently implemented analysis."
        features={["Unlimited advanced match reports", "All implemented prediction features", "Unlimited league-impact simulations", "Planned: personalized AI and matchday experiences", "Planned: ad-free experience when ads exist"]}
        actionLabel="Get Premium — €4.99/month" onAction={() => setCheckoutProduct({ kind: "premium", title: "Unlimited reports and simulations" })}
        featured badge="Full access" current={entitlements.plan === "premium"} />
    </div>

    <section className={styles.demoTools} aria-labelledby="demo-access-heading">
      <div><p className={styles.eyebrow}>TRY EACH TIER</p><h2 id="demo-access-heading">Demo access on this browser</h2>
        <p>{entitlements.plan === "premium"
          ? "Premium is active. All current advanced reports are available."
          : `Free access is active${entitlements.purchasedReportIds.length ? ` · ${entitlements.purchasedReportIds.length} report${entitlements.purchasedReportIds.length === 1 ? "" : "s"} unlocked` : ""}.`}</p>
        {notice && <p className={styles.accessNotice} role="status">{notice}</p>}</div>
      <button type="button" className={styles.reset} onClick={reset}>Reset demo purchases</button>
    </section>

    <aside className={styles.planned}>
      <strong>Planned features</strong>
      <span>Personalized AI analysis, personalized matchday experiences, and ad-free viewing are roadmap items. They are not available in this demo.</span>
    </aside>
    <p className={styles.security}>Demo access is stored in localStorage and can be edited by the user. It only demonstrates the experience. A production launch needs authenticated accounts, server-verified entitlements, secure payment processing, subscription lifecycle handling, and backend authorization before paid data is returned.</p>
    <DemoCheckout product={checkoutProduct} onClose={() => setCheckoutProduct(null)} onConfirm={confirmCheckout} />
  </main>;
}
