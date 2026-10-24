# Roadmap — from prototype to hackathon demo

## Milestone 1: Local discovery agent (implemented)
- Synthetic data, explicit geo city selection, 5–500 km radius
- Filters and a readable ranking formula
- Source reference integrity checks
- Local sports moments in a Next.js dashboard
- Deterministic grounded summaries and optional AI draft generator

## Milestone 2: Replace the sample adapter with Liiga data
- Confirm exact organizer API contract, rate limits, fields, licensing and credentials
- Add a dedicated adapter, store raw response provenance and ingestion timestamps
- Map API event IDs to our internal Moment model (match, club, player, time)
- Add event reconciliation tests for postponed games, duplicates and corrections
- Keep any API key on the backend, never `NEXT_PUBLIC_...`

## Milestone 3: Genuine short-video highlights
- Ask Kaleva whether match video exists and what clipping/redistribution rights apply
- Ingest licensed video references with timestamps
- Pair event clock to video clock and manually verify offset correctness
- Label the presence/absence of footage clearly; no invented animations as 'replay'
- Build an actual vertical swipe feed only after authorized clips exist

## Milestone 4: Audience personalization
- Opt-in favorite sports, clubs, athletes, selected hometown (not precise GPS)
- Ranking: preferences + proximity + freshness + video availability
- Diversity guardrails to avoid flooding the feed with one popular team
- Save users' followed entities and hide content they don't want

## Milestone 5: Human trust and newsroom standards
- Distinguish official sources, raw stats, predictions and AI interpretation
- Editorial review queue, logged version history and corrections
- Evaluate story factual precision, geographic relevance and satisfaction
- Extra safeguards and consent requirements around minors/junior leagues

## Milestone 6: Commercial demo
- Advertiser placement examples that don't masquerade as editorial stories
- Premium story bundles, audio digests, and community follow notifications
- Show one user journey: location → standout moment → evidence → follow player
- Add a simple 'Would you subscribe?' user-research flow; measure intent

## Optional later: prediction agent
- Elo/Poisson match model, Monte Carlo standings forecasts
- Backtesting and calibration; source-driven model inputs
- What-if playoff scenarios, never presented as certainties

## Success metrics for the hackathon pitch
- Users understand a nearby sports moment with minimal context
- Every claim has traceable source data; zero unsupported claims in audited demo
- At least one story clearly illustrates why it matters beyond the final score
- Demonstrate a feasible path to local ad inventory and subscriptions
