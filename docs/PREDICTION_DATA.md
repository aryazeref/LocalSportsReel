# Prediction and competition-impact data inventory

Audit date: 2026-10-24. This is an input-data audit, not an implemented prediction model.

Implementation update: a first statistical prediction and points-scenario
prototype now uses the basic historical results. See [the measured evaluation](PREDICTION_EVALUATION.md).
The richer inputs below are not all features of that initial model.

## Sources and verification levels

Base URL: `https://prod.liiga-backend.liiga.fi/stats`.

Official schemas inspected:

- [v1](https://prod.liiga-backend.liiga.fi/stats/v3/api-docs/v1): 49 documented paths.
- [v2](https://prod.liiga-backend.liiga.fi/stats/v3/api-docs/v2): 12 documented paths.
- [v2s](https://prod.liiga-backend.liiga.fi/stats/v3/api-docs/v2s): 14 documented paths.

These are path counts, not counts of independent datasets. Versions overlap.
The endpoint appendix records documented parameters. The v1 schema appendix
records all top-level fields, including metadata that should not be predictors.

**Live verified** means a representative public request returned populated data.
It does not establish complete history, pre-match availability, or coverage for
every team/season. **Documented** means the schema describes a field; values can
be absent, null, placeholders, or source-dependent.

The inspected 2027 regular-season snapshot contains 544 matches, 131 completed
matches, and 17 represented teams. These counts are a snapshot, not constants.
Historical result samples for ending seasons 2026, 2025, and 2020 returned
completed games. The two inspected 2020 matches lacked expected-goals values.
No claim of full historical-season completeness has been established.

## 1. Match identity, schedule and final results — live verified

Endpoints:

- `GET /api/v1/games?season=2027&serie=RUNKOSARJA`
- `GET /api/v1/games/schedule?season=2027&serie=RUNKOSARJA`
- `GET /api/v1/games/{season}/{gameId}` (detailed events and players)

Inputs: `id`, `season`, `serie`, `gameWeek`, `start`, `end`, `started`, `ended`,
`finishedType`, `currentPeriod`, `gameTime`, home/away IDs and names, scores,
rankings, and rink details. Historical game IDs can repeat across seasons;
use `(season, id)` as the game identity. Team IDs require explicit mapping
between numeric aggregate IDs and external strings such as `292293444:jukurit`.

`finishedType` distinguishes regulation, extra time, shootouts, cancellations,
and active/not-started games. `periods[]` supplies category, period scores,
and clocks. Final scores include the extra shootout-winning goal: one inspected
5–4 result had regulation periods totaling 4–4 and a 1–0 shootout period.
Use sums of `category=NORMAL` periods for regulation-score targets. Period 4/5
objects can exist even when no extra time was played.

Derive: Elo, home advantage, last-5/10 results, goals for/against, rest days,
back-to-backs, games in the last 7/14 days, head-to-head history, and strength
of the remaining schedule. Training must use only earlier matches.

## 2. Team attacking, defensive and possession statistics — live verified groups

Endpoint: `GET /api/v1/teams/web/stats/{content}`.

Documented content values and useful inputs:

| Content | Data available |
|---|---|
| `STANDINGS` | Games, rank and previous-day rank, results, points, GF/GA/GD, last-five results, expected goals for/against/difference, expected points, skating distance, puck-control time/percentage, points/game |
| `SHOTS` | Shots for/against, saved/non-blocked shots, shot shares and differences, shooting/save percentages, PDO, and many even-strength/PP/PK splits |
| `PASSES` | Attempts, completions, completion percentages, even-strength and special-team/manpower splits |
| `FACEOFFS` | Wins/losses/totals/percentages, offensive/defensive/center-zone and strength splits |
| `EVEN_STRENGTH` | Goals for/against and time at 5v5/4v4/3v3; time per goal |
| `POWERPLAY` | Opportunities, goals, time, conversion, net conversion, shorthanded goals conceded; one/two-player advantage splits |
| `PENALTY_KILL` | Opportunities, goals conceded, shorthanded goals scored, time, kill/net-kill percentages; one/two-player disadvantage splits |
| `PENALTIES` | Penalty counts/minutes and counts by duration |
| `ATTENDANCE` | Home/away/total crowd averages and totals; historical-use coverage still needs validation |

Live checks returned 17 populated teams for standings, shots, PP, and PK.
Expected-goals fields were populated in team standings. `expectedPoints` was
0.0 in tested rows: do not use it as a reliable forecast without further checks.

Match-list team fields also include `expectedGoals`, `powerplayInstances`,
`powerplayGoals`, `shortHandedInstances`, and `shortHandedGoals`. All 262 team
sides in the inspected completed-game snapshot had xG and those special-team
counts. `shortHandedGoals` means goals scored while shorthanded, not goals
conceded on the penalty kill. Use opponents' power-play goals for the latter.

Filters include season range `from/to`, `fromDate/toDate`, `lastGames`,
`side=HOME|AWAY|ALL`, `result`, `opponent`, `gameWeek`, and `live`.
Compute rolling rates from summed opportunities, not an unweighted mean of
individual-game percentages. Reconcile percentage scales first.

**xG is observed chance quality from played games, not a pre-match predicted
score.** Only lagged/rolling past xG is a valid pre-match input.

## 3. Skater and goalie performance — live verified groups

Endpoint: `GET /api/v1/players/web/stats/{content}`.

| Content | Data available |
|---|---|
| `BASIC` | Goals, assists, points, plus/minus, penalties, shots/on-goal, xG, provider `xge`, PP/SH/game-winning/empty-net goals, TOI |
| `SHOTS` | Attempted/on-goal/saved/missed/blocked shots, shooting percentage, hardest shot |
| `PASSES` | Attempts/completions, strength splits, pressure/high-pressure passing |
| `FACEOFFS` | Wins/losses/totals/percentages with zone splits |
| `GOALS` | Goals by strength, game-winning/empty-net/shootout contributions |
| `PPPK` | PP/PK goals, assists, points, contribution percentages |
| `SKATING` | Distance, per-period/per-match distance, top speed |
| `TIME_ON_ICE` | TOI, averages, period splits, shifts, PP/PK seconds, two-player advantage/disadvantage time |
| `ADVANCED` | Corsi for/against/share/difference, offensive/defensive zone starts, on-ice shots/goals, on-ice shooting/save percentages, PDO |
| `WINNING_SHOTS` | Skater shootout attempts/goals/misses/conversion |
| `GK_BASIC` | Goalie results, appearances/TOI, saves, goals against, save percentage, GAA, shutouts, xGA, provider `xgea`, reserve flag |
| `GK_WINNING_SHOTS` | Goalie shootout attempts faced/saved/conceded and save percentage |
| `ALL` | Combined statistics; scope/shape should be validated before ingestion |

Player content endpoints support season/date ranges plus team/opponent,
home/away, last games, week, result, nationality and transfer-team splitting
filters. The schema warns that pre-2014 data returns a simpler structure.
Do not assume full tracking/advanced coverage merely because older scores exist.

Live BASIC returned 486 skater records (429 with played games); 416 had nonzero
xG. GK_BASIC returned 59 records (41 with played games). An ADVANCED team sample
returned Corsi, zone-start and on-ice metrics. These are coverage examples,
not an automatically cleaned training dataset. Validate the definitions and
units of provider `xge`/`xgea` before giving them derived metric names.

Derive: weighted lineup scoring/defensive strength, prior goalie save and xGA
performance, workload and special-team contributions. Shrink small samples.

## 4. Rosters, lineups, injuries and suspensions — conditional availability

Endpoints include `/api/v1/players`, `/api/v1/players/{teamId}`,
`/api/v1/games/{season}/{gameId}/players`, `/fullRoster`, `/playersWithStats`,
`/goalieComparison`, `/api/v1/players/roles`, and `/api/v1/player/suspensions`.
The abbreviated game suffixes use the same `/games/{season}/{gameId}` prefix.

Player metadata includes stable player ID, team, role, line, handedness,
height/weight, birth date, nationality, captain/rookie status, jersey,
`injured`, `suspended`, `removed`, and transfer/current-team indicators.
Suspensions expose player ID, `startDate`, `lengthInGames`, `gamesSatOut`, and
`finished`. A date-range request returned six suspension records. Current
skater rows included injured/suspended flags.

A finished-game lineup returned 22 players per side with lines and two goalies.
A future-game lineup returned empty lists. Future goalie comparisons returned
multiple keepers, without a uniquely confirmed starter. Therefore:

- An absent lineup is unknown, not proof that every player is missing/injured.
- A goalie comparison is not a confirmed-starting-goalie feed.
- Current injury flags are not a timestamped historical injury/return timeline.
- Historical availability and announced lineups require our own as-of snapshots.

## 5. Shots, events, tracking and live state — live verified with partial coverage

Endpoints: `/api/v1/shotmap/{season}/{gameId}`,
`/api/v1/games/{season}/{gameId}`, and its `/stats` suffix.

Shot events expose shooter/blocker/team IDs, clock, period, x/y position,
outcome (`GOAL`, `GOALIE_BLOCKED`, `PLAYER_BLOCKED`, `MISSED`), xG, strength type,
on-ice counts, and source-dependent player positions. The checked shotmap had
87 shots, 86 with xG and 85 with positions. Positions are documented as
WiseHockey-dependent. The observed even-strength counts were 6v6; do not assume
those counters exclude goalies or map directly to skater manpower.

Detailed game data also exposes goal/assist IDs, goal types, score progression,
penalty fault/type/minutes/start/end, goalie participation/changes, empty-net
intervals, shootout attempts, period team/player/goalie stats, faceoffs, skating,
speed, passing and puck control. PuckStats in the inspected three-period game
contained only one row and zero puck-distance: missing/placeholder coverage
must not be interpreted as true measured zero.

`plusPlayerIds`/`minusPlayerIds` are documented as space-separated jersey
numbers despite their names; map them through the lineup, not player IDs.
Live score/clock/penalties can support a future in-play model. They cannot be
used as inputs to a pre-match backtest for that same game.

## 6. Venue, contextual and market fields

Rink ID/name/city/coordinates support home/away, venue effects and approximate
travel between scheduled venues. This is geographical distance, not actual
transport or travel schedules. Rest can be derived from starts; completion
and event timestamps need reconciliation because seven inspected completed
games had an end before their scheduled start.

Attendance, referees, provider/cache/stale metadata, and betting fields are
also documented. Attendance and odds occurred in the inspected match list;
referees/provider/cache timestamps were omitted there. Raw odds use
`homeTeamOdds`, `awayTeamOdds`, `tieOdds` integers. Units, market definition,
and historical observation time are not established; some completed-game
values appear consistent with late/in-play prices. Do not treat them as
historical pre-match odds. Logos, tickets, video URLs and awards serve display
or editorial features, not the initial prediction model.

## 7. Official standings and competition dynamics — live verified baseline

Use `GET /api/v1/standings/RUNKOSARJA?season=2027&isLive=false` for the current
baseline. It returned 17 teams plus `playoffsLines=[4,12,14]` and a cache timestamp.
Fields include rank, played games, regulation wins/losses, overtime wins/losses,
points, GF/GA, PP/PK totals, penalties, and optional live standings counterparts.

Verified across all current rows:

```text
games = wins + overtimeWins + losses + overtimeLosses
ties = overtimeWins + overtimeLosses
points = 3*wins + 2*overtimeWins + overtimeLosses
```

Here `wins` are regulation wins. `ties` are regulation ties, not final draws.
Our current app's wins count final winners and must not be inserted unchanged
into the official points formula. Modes include POINTS and POINTS_AVERAGE;
the API specifically documents the shortened 2020 season as a special case.

Fixtures expose `serie`, `playOffPair`, `playOffPhase`, `playOffReqWins`, seed
rankings and team placeholders for unresolved brackets. A 2026 PLAYOFFS schedule
returned 60 games with required wins of 1, 3, or 4 depending on the phase.
`/api/v1/games/web/tournament` and `/api/v1/series` provide season/type and
week context, not a complete competition rulebook.

**Not supplied as a complete machine-readable rule set:** season-specific
ordered tie-breakers, meanings of numerical playoff boundaries, qualification
paths, reseeding, home-ice policy, promotion/relegation and competition-format
changes. Obtain these from official rules before presenting exact outcomes.
Do not infer the meaning of [4,12,14] from a familiar earlier league format.
CHL coverage can be partial: the v2s teams endpoint explicitly warns that it
may include only Finnish teams' opponents.

For a 3–2–1 points simulation, model four outcomes at minimum:

1. Home regulation win.
2. Home extra-time/shootout win.
3. Away extra-time/shootout win.
4. Away regulation win.

A two-way final-win probability alone cannot determine which points each team
receives. Compare a baseline simulation against each forced outcome, applying
the same remaining schedule and verified rules, then report changes in rank,
points, qualifying/regular-season-first-place probabilities and rival-team
outcomes. Ultimate championship probabilities additionally require simulation
of the playoff bracket and its rules; first place is not the same outcome.

## 8. Time leakage and ingestion requirements

- Store raw response, source endpoint, season/game ID and our ingestion time.
  Our current two-minute cache is not a persistent historical snapshot archive.
- Recompute historical features strictly before prediction time. Current totals,
  current injury flags, eventual lineups/attendance, match xG, and final scores
  must not leak into earlier predictions.
- Date filtering is not a guarantee for every response field: a Sept 1–10
  team-STANDINGS request returned a three-game record but a five-result
  `last5Results` string. Derive historical form from cutoff-filtered fixtures.
- Missing, null, placeholder zero and genuine zero need separate handling.
- Normalize numeric/external IDs, timestamp consistency, percentage scales and
  string fractions. Standard standings may return percentages as strings in
  a 0–1 scale while other endpoints use 0–100.
- Verify historical completeness, cancellations, duplicates, corrections,
  season rules and changing team membership before training and backtesting.
- `/api/v2/teams/season-stats` explicitly warns it is highly cached and unsuitable
  for current-season stats. Prefer official live/current standings endpoints.
- Provider "beforegame" comparison endpoints are useful candidates, but the
  historical as-of behavior of every field has not been proven.

## 9. Recommended implementation order

1. Extend ingestion/models to retain competition, regulation/extra-time outcome,
   periods, match xG and special teams. Fetch official standings and schedule.
2. Build historical training rows using multiple checked seasons and chronological
   cutoffs; evaluate final winner and regulation/extra-time probabilities.
3. Start with sequential Elo and a home-advantage baseline; compare with regularized
   logistic and/or regulation-goal models using lagged goals/xG/shots/rest.
4. Add goalie/availability/lineup features only when their pre-match snapshots exist.
5. Implement an explicit season-specific rules engine and Monte Carlo scenarios.
6. Let Gemini explain calculated outputs and their evidence. Do not ask it to
   invent numerical probabilities, unavailable inputs, or competition rules.

No prediction accuracy, calibration, full historical-season coverage or competition
simulation has been validated by this data audit.

## Appendix A: documented GET endpoints and parameters

Paths below are relative to the base URL. Parameter names do not imply that
every aggregate field obeys that parameter; verify response semantics.

### v1

| Endpoint | Documented parameters |
|---|---|
| `/api/v1/test` | None |
| `/api/v1/teams` | `serie`, `season` |
| `/api/v1/teams/web/stats/{season}/{serie}` | `season`, `serie`, `team`, `home_away` |
| `/api/v1/teams/web/stats/{content}` | `content`, `from`, `to`, `serie`, `fromDate`, `toDate`, `lastGames`, `side`, `result`, `opponent`, `gameWeek`, `live` |
| `/api/v1/teams/web/stats/maxWeek/{season}/{serie}` | `season`, `serie` |
| `/api/v1/teams/web/nbseasons` | None |
| `/api/v1/teams/web/games/{team}/{season}/{serie}` | `team`, `season`, `serie` |
| `/api/v1/team-comparison` | `teamId` |
| `/api/v1/team-comparison/{season}/{gameId}` | `season`, `gameId`, `nbSeasons` |
| `/api/v1/team-comparison/teamperformance/{season}/{gameId}` | `season`, `gameId`, `nbGames` |
| `/api/v1/team-comparison/beforegame/{season}/{serie}/{gameId}` | `season`, `gameId` |
| `/api/v1/team-comparison/beforegame/{season}/{gameId}` | `season`, `gameId` |
| `/api/v1/standings/{serie}` | `serie`, `season`, `mode`, `isLive` |
| `/api/v1/shotmap/{season}/{gameId}` | `season`, `gameId` |
| `/api/v1/series` | `season`, `serie` |
| `/api/v1/players` | `season`, `includeRemoved`, `serie`, `nationality` |
| `/api/v1/players/{teamId}` | `teamId`, `includeRemoved`, `season`, `serie`, `nationality` |
| `/api/v1/players/{playerId}/stats` | `playerId` |
| `/api/v1/players/web` | `fromSeason`, `toSeason`, `serie`, `team`, `role`, `nationality` |
| `/api/v1/players/web/{playerId}` | `playerId` |
| `/api/v1/players/web/{playerId}/games/{season}` | `playerId`, `season` |
| `/api/v1/players/web/stats/{season}/{serie}` | `season`, `serie`, `includeRemoved` |
| `/api/v1/players/web/stats/{content}` | `content`, `from`, `to`, `serie`, `fromDate`, `toDate`, `forceLastTeamData`, `side`, `result`, `team`, `opposingTeam`, `week`, `lastGames`, `splitByTeam`, `nationality` |
| `/api/v1/players/web/stats/milestones/{serie}` | `serie` |
| `/api/v1/players/web/info/{playerId}/games/{season}` | `playerId`, `season` |
| `/api/v1/players/roles` | `player`, `season` |
| `/api/v1/player/suspensions` | `playerId`, `fromDate`, `toDate`, `finished` |
| `/api/v1/player/suspensions/{playerSuspensionId}` | `playerSuspensionId` |
| `/api/v1/player/penalties` | `season`, `fromDate`, `toDate`, `minutesOver`, `sufferPlayerId`, `playerId` |
| `/api/v1/player/penalties/{penaltyId}` | `penaltyId` |
| `/api/v1/player-point-table/{serie}` | `serie`, `season`, `teamId`, `role` |
| `/api/v1/icerinks` | None |
| `/api/v1/icerinks/{iceRinkId}` | `iceRinkId` |
| `/api/v1/games` | `season`, `teamId`, `fromDate`, `date`, `serie`, `limit`, `earlierThan`, `gameweek`, `includeFutureSeasons` |
| `/api/v1/games/{season}/{gameId}` | `season`, `gameId` |
| `/api/v1/games/{season}/{gameId}/stats` | `season`, `gameId` |
| `/api/v1/games/{season}/{gameId}/players` | `season`, `gameId` |
| `/api/v1/games/{season}/{gameId}/playersWithStats` | `season`, `gameId` |
| `/api/v1/games/{season}/{gameId}/playersToWatch` | `season`, `gameId`, `nbGames`, `role` |
| `/api/v1/games/{season}/{gameId}/playerComparison` | `season`, `gameId`, `nbSeasons`, `nbPlayers` |
| `/api/v1/games/{season}/{gameId}/player-point-table` | `season`, `gameId` |
| `/api/v1/games/{season}/{gameId}/pastAndFutureGames` | `season`, `gameId` |
| `/api/v1/games/{season}/{gameId}/goalieComparison` | `season`, `gameId` |
| `/api/v1/games/{season}/{gameId}/fullRoster` | `season`, `gameId` |
| `/api/v1/games/web/tournament` | None |
| `/api/v1/games/schedule` | `season`, `serie` |
| `/api/v1/games/gameWeek` | None |
| `/api/v1/alumni/rounds` | `season`, `serie`, `fromDate`, `toDate` |
| `/api/v1/alumni/rounds/{alumniRoundId}` | `alumniRoundId` |

### v2

| Endpoint | Documented parameters |
|---|---|
| `/api/v2/teams/stats/{content}` | `content`, `from`, `to`, `serie`, `fromDate`, `toDate`, `lastGames`, `side`, `result`, `opponent`, `gameWeek`, `live` |
| `/api/v2/teams/web/stats/{content}` | `content`, `from`, `to`, `serie`, `fromDate`, `toDate`, `lastGames`, `side`, `result`, `opponent`, `gameWeek`, `live` |
| `/api/v2/teams/season-stats` | `teamId`, `serieId`, `season` |
| `/api/v2/team-comparison` | `teamId` |
| `/api/v2/team-comparison/beforegame/{season}/{gameId}` | `gameId`, `season` |
| `/api/v2/standings/{serie}` | `serie`, `isLive` |
| `/api/v2/shotmap/{season}/{gameId}` | `season`, `gameId` |
| `/api/v2/player-comparison/{season}/{gameId}` | `season`, `gameId`, `nbSeasons`, `nbPlayers`, `criterion` |
| `/api/v2/icerinks` | None |
| `/api/v2/icerinks/{iceRinkId}` | `iceRinkId` |
| `/api/v2/games/{season}/{gameId}/playersWithStats` | `season`, `gameId` |
| `/api/v2/award-stats` | `serie`, `season`, `awardId`, `teamId`, `playerId`, `gameId` |

### v2s

| Endpoint | Documented parameters |
|---|---|
| `/api/v2s/teams` | `serie` |
| `/api/v2s/teams/games/{teamId}/{serie}` | `teamId`, `serie` |
| `/api/v2s/standings/{serie}` | `serie` |
| `/api/v2s/series` | `serie` |
| `/api/v2s/series/current` | None |
| `/api/v2s/players` | `teamId`, `serie` |
| `/api/v2s/players/{playerId}/stats` | `playerId` |
| `/api/v2s/players/point-table/{serie}` | `serie`, `teamId`, `role` |
| `/api/v2s/games` | `teamId`, `fromDate`, `toDate`, `earlierThan`, `date`, `serie`, `limit`, `gameweek`, `includeFutureSeasons` |
| `/api/v2s/games/{gameId}` | `gameId` |
| `/api/v2s/games/{gameId}/stats` | `gameId` |
| `/api/v2s/games/{gameId}/players` | `gameId` |
| `/api/v2s/games/{gameId}/player-point-table` | `gameId` |
| `/api/v2s/games/schedule` | `serie` |

## Appendix B: complete v1 schema field index

A field being documented is not a guarantee of population or pre-match
availability. Nested object definitions have their own entries below.

### `TeamDTO`

```text
id, nameAbbreviation, shortName, logos
```

### `TeamLogosDTO`

```text
darkBg, lightBg, darkBgOriginal, lightBgOriginal
```

### `TeamSerieStatsDTO`

```text
id, season, leagueId, serieId, teamId, awayGames, awayLosses, awayTies, awayWins,
awayWinsInExtraTime, games, goalsAgainst, goalsScored, homeGames, homeLosses, homeTies,
homeWins, homeWinsInExtraTime, losses, points, playoffRank, regularSeasonRank, ties, wins,
winsInExtraTime
```

### `TeamStatsStandingsDTO`

```text
sortDesc, teamId, teamName, teamShortName, teamLogos, games, ranking, previousGameDayRanking,
wins, losses, ties, points, goalsFor, goalsAgainst, goalDifference, last5Results, extraPoints,
previousGameDayPoints, previousGameDayWins, previousGameDayGoalsFor,
previousGameDayGoalsAgainst, expectedGoalsFor, expectedGoalsAgainst, expectedPoints,
skatedDistance, nbSeasons, puckControlTime, playTime, puckControlPercentage, comparator,
expectedGoalsDifference, pointsAverage
```

### `TeamStatsShotsDTO`

```text
sortDesc, teamId, teamName, teamShortName, teamLogos, games, ranking, previousGameDayRanking,
shots, shotsSaved, shotsEvenStrength, shotsPowerplay, shotsPenaltyKill, shotsAgainst, goals,
goalsAgainst, shotsAgainstEvenStrength, shotsAgainstPowerplay, shotsAgainstPenaltyKill,
nonBlockedShots, nonBlockedShotsEvenStrength, nonBlockedShotsPowerplay,
nonBlockedShotsPenaltyKill, nonBlockedShotsAgainst, nonBlockedShotsAgainstEvenStrength,
nonBlockedShotsAgainstPowerplay, nonBlockedShotsAgainstPenaltyKill, powerplayGoals,
powerplayGoalsAgainst, penaltyKillGoals, penaltyKillGoalsAgainst, evenStrengthGoals,
evenStrengthGoalsAgainst, previousGameDayGoals, previousGameDayShots,
shotsForShotsAgainstPercentageEvenStrength, shotsForShotsAgainstPercentagePowerplay,
shotsForShotsAgainstPercentagePenaltyKill, nonBlockedShotsDifferenceEvenStrength,
nonBlockedShotsDifferencePowerplay, nonBlockedShotsDifferencePenaltyKill,
nonBlockedShotsForShotsAgainstPercentage, nonBlockedShotsForShotsAgainstPercentagePenaltyKill,
previousGameDayShotsPercentage, shotsPercentageEvenStrength, shotsPercentagePowerplay,
shotsPercentagePenaltyKill, shotsDifferenceEvenStrength, shotsDifferencePowerplay,
shotsDifferencePenaltyKill, shotsPercentage, shotsDifference, shotsForShotsAgainstPercentage,
nonBlockedShotsDifference, savePercentageEvenStrength, savePercentagePowerplay,
savePercentagePenaltyKill, pdoPenaltyKill, pdoPowerplay,
nonBlockedShotsForShotsAgainstPercentagePowerplay,
nonBlockedShotsForShotsAgainstPercentageEvenStrength, pdoEvenStrength, pdo, savePercentage
```

### `TeamStatsPassesDTO`

```text
sortDesc, teamId, teamName, teamShortName, teamLogos, games, ranking, previousGameDayRanking,
totalPasses, successfulPasses, penaltyKillTotalPasses, penaltyKillSuccessfulPasses,
evenStrengthTotalPasses, evenStrengthSuccessfulPasses, powerplayTotalPasses,
powerplaySuccessfulPasses, penaltyKill1TotalPasses, penaltyKill1SuccessfulPasses,
penaltyKill2TotalPasses, penaltyKill2SuccessfulPasses, powerplay1TotalPasses,
powerplay1SuccessfulPasses, powerplay2TotalPasses, powerplay2SuccessfulPasses,
previousGameDayTotalPasses, previousGameDaySuccessfulPasses, previousGameDayPassesPercentage,
powerplayPassesPercentage, powerplay1PassesPercentage, powerplay2PassesPercentage,
penaltyKillPassesPercentage, penaltyKill1PassesPercentage, penaltyKill2PassesPercentage,
passesPercentage
```

### `TeamStatsFaceoffsDTO`

```text
sortDesc, teamId, teamName, teamShortName, teamLogos, games, ranking, previousGameDayRanking,
faceoffCenterLost, faceoffCenterWon, faceoffDefenceLost, faceoffDefenceWon, faceoffOffenceLost,
faceoffOffenceWon, faceoffWon, faceoffLost, previousGameDayFaceoffWon,
previousGameDayFaceoffLost, faceoffOffenceWonPenaltyKill, faceoffOffenceLostPenaltyKill,
faceoffOffenceWonEvenStrength, faceoffOffenceLostEvenStrength, faceoffOffenceWonPowerplay,
faceoffOffenceLostPowerplay, faceoffCenterWonPenaltyKill, faceoffCenterLostPenaltyKill,
faceoffCenterWonEvenStrength, faceoffCenterLostEvenStrength, faceoffCenterWonPowerplay,
faceoffCenterLostPowerplay, faceoffDefenceWonPenaltyKill, faceoffDefenceLostPenaltyKill,
faceoffDefenceWonEvenStrength, faceoffDefenceLostEvenStrength, faceoffDefenceWonPowerplay,
faceoffDefenceLostPowerplay, faceoffCenterWonPercentagePenaltyKill,
faceoffDefenceWonPercentagePenaltyKill, faceoffOffenceWonPercentagePenaltyKill,
faceoffCenterWonPercentagePowerplay, faceoffDefenceWonPercentagePowerplay,
faceoffOffenceWonPercentagePowerplay, faceoffCenterWonPercentageEvenStrength,
faceoffDefenceWonPercentageEvenStrength, faceoffOffenceWonPercentageEvenStrength,
faceoffWonPercentageEvenStrength, previousGameDayFaceoffWonPercentage, faceoffWonPenaltyKill,
faceoffLostPenaltyKill, faceoffWonEvenStrength, faceoffLostEvenStrength, faceoffWonPowerplay,
faceoffLostPowerplay, faceoffTotalPenaltyKill, faceoffTotalEvenStrength, faceoffTotalPowerplay,
faceoffCenterWonPercentage, faceoffDefenceWonPercentage, faceoffOffenceWonPercentage,
faceoffWonPercentagePowerplay, faceoffWonPercentagePenaltyKill, faceoffWonPercentage,
faceoffTotal
```

### `TeamStatsEvenStrengthDTO`

```text
sortDesc, teamId, teamName, teamShortName, teamLogos, games, ranking, previousGameDayRanking,
previousGameDayEvenStrengthGoalsFor, previousGameDayEvenStrengthTime, evenStrengthTime,
evenStrengthTime5vs5, evenStrengthTime4vs4, evenStrengthTime3vs3, evenStrengthGoalsFor,
evenStrengthGoalsFor5vs5, evenStrengthGoalsFor4vs4, evenStrengthGoalsFor3vs3,
evenStrengthGoalsAgainst, evenStrengthGoalsAgainst5vs5, evenStrengthGoalsAgainst4vs4,
evenStrengthGoalsAgainst3vs3, timeForGoalAgainst3vs3, timeForGoalAgainst4vs4,
timeForGoalAgainst5vs5, timeForGoal3vs3, timeForGoal4vs4, timeForGoal5vs5, timeForGoal,
previousGameDayTimeForGoal, timeForGoalAgainst
```

### `TeamStatsPowerplayDTO`

```text
sortDesc, teamId, teamName, teamShortName, teamLogos, games, ranking, previousGameDayRanking,
powerplay, powerplayGoals, powerplayTime, powerplay1, powerplayGoalsAgainst, powerplayGoals1,
powerplay2, powerplayGoals2, powerplayTime1, powerplayTime2, powerplayGoalsAgainst2,
powerplayGoalsAgainst1, previousGameDayPowerplay, previousGameDayPowerplayGoals,
previousGameDayPowerplayPercentage, powerplayPercentage1, powerplayPercentage2,
timeForGoalPowerplay, timeForGoalPowerplay1, timeForGoalPowerplay2, timeForGoalAgainstPowerplay,
timeForGoalAgainstPowerplay1, timeForGoalAgainstPowerplay2, netPowerplayPercentage,
netPowerplayPercentage1, netPowerplayPercentage2, powerplayPercentage
```

### `TeamStatsPenaltyKillDTO`

```text
sortDesc, teamId, teamName, teamShortName, teamLogos, games, ranking, previousGameDayRanking,
penaltyKill, penaltyKillGoals, penaltyKillTime, penaltyKillGoalsAgainst, penaltyKill1,
penaltyKillGoals1, penaltyKillTime1, penaltyKillGoalsAgainst1, penaltyKill2, penaltyKillGoals2,
penaltyKillTime2, penaltyKillGoalsAgainst2, previousGameDayPenaltyKill,
previousGameDayPenaltyKillGoalsAgainst, previousGameDayPenaltyKillPercentage,
penaltyKillPercentage1, penaltyKillPercentage2, timeForGoalAgainstPK, timeForGoalPK,
timeForGoalPK1, timeForGoalPK2, timeForGoalAgainstPK1, timeForGoalAgainstPK2,
netPenaltyKillPercentage, netPenaltyKillPercentage1, netPenaltyKillPercentage2,
penaltyKillPercentage
```

### `TeamStatsPenaltiesDTO`

```text
sortDesc, teamId, teamName, teamShortName, teamLogos, games, ranking, previousGameDayRanking,
get2minutesPenalties, get5minutesPenalties, get10minutesPenalties, get20minutesPenalties,
get25minutesPenalties, penaltyMinutes, penalties
```

### `TeamStatsAttendanceDTO`

```text
teamId, sortDesc, teamName, teamShortName, teamLogos, games, ranking, previousGameDayRanking,
attendants_away_total, attendants_home_total, away_games, home_games, attendants_away_avg,
attendants_home_avg, attendants_total, attendants_avg
```

### `TeamSeasonsDTO`

```text
id, nameAbbreviation, seasons
```

### `TeamGameDTO`

```text
away_goals, away_team, away_team_abbreviation, away_team_logos, current_period, date, fiha_id,
finished, finished_type, game_time, home_goals, home_team, home_team_abbreviation,
home_team_logos, resource_uri, season, start_time, started, ticket_shop_url,
ticket_shop_url_overridden, tournament_type, videosummary
```

### `VideoSummaryDTO`

```text
thumbnail_uri, video_url, category
```

### `TeamComparisonDTO`

```text
runkosarjaPoints, runkosarjaPointsRank, winPercentage, homeTeamWinPercentage,
awayTeamWinPercentage, lastSevenGames, gamesAgainstEachOther
```

### `WinsTiesLossesDTO`

```text
wins, ties, losses, overtimeWins, shootoutWins, lossPercentage, tiesPercentage,
overtimeWinsPercentage, shootoutPercentage, winPercentage
```

### `GameSummaryDTO`

```text
season, gameId, homeGoals, awayGoals, homeTeamId, awayTeamId, homeTeamName, awayTeamName,
homeTeamlogo, awayTeamlogo, gameStart, extraTime, shootouts
```

### `TeamPerformanceDTO`

```text
teamName, teamLogo, wins, ties, losses, voittoputki, games
```

### `TeamComparisonBeforeGameDTO`

```text
pointsAverage, pointsAverageRank, goalsScored, goalsScoredRank, goalsAgainst, goalsAgainstRank,
gf_gp, gf_gpRank, ga_gp, ga_gpRank, powerplayPercentage, powerplayPercentageRank,
penaltykillPercentage, penaltykillPercentageRank, faceoffPercentage, faceoffPercentageRank,
shotsPerGame, shotsPerGameRank, gf_GP, ga_GP
```

### `ValueRanking`

```text
value, ranking
```

### `StandingsItemDTO`

```text
internalId, teamId, teamName, teamLogos, ranking, liveRanking, games, liveGames, wins, liveWins,
overtimeWins, losses, liveLosses, ties, liveTies, overtimeLosses, points, livePoints, goals,
goalsAgainst, liveGoals, liveGoalsAgainst, powerPlayInstances, powerPlayTime, powerPlayGoals,
shortHandedInstances, shortHandedTime, shortHandedGoalsAgainst, twoMinutePenalties,
fiveMinutePenalties, tenMinutePenalties, twentyMinutePenalties, twentyFiveMinutePenalties,
distance, serie, totalPenalties, distancePerGame, pointsPerGame, livePointsPerGame,
powerPlayPercentage, shortHandedPercentage, penaltyMinutes, winPercentage
```

### `StandingsResponseDTO`

```text
items, playoffsLines, cacheUpdateDate
```

### `EvenStrengthShotDTO`

```text
shootingTeamId, leftTeam, rightTeam, gameTime, period, shotX, shotY, blockerId, shooterId,
eventType, ownTeamPlayersOnIce, otherTeamPlayersOnIce, xg, playerStartPositions, type
```

### `PowerplayShotDTO`

```text
shootingTeamId, leftTeam, rightTeam, gameTime, period, shotX, shotY, blockerId, shooterId,
eventType, ownTeamPlayersOnIce, otherTeamPlayersOnIce, xg, playerStartPositions, type
```

### `ShorthandedShotDTO`

```text
shootingTeamId, leftTeam, rightTeam, gameTime, period, shotX, shotY, blockerId, shooterId,
eventType, ownTeamPlayersOnIce, otherTeamPlayersOnIce, xg, playerStartPositions, type
```

### `ShotDTO`

```text
shootingTeamId, leftTeam, rightTeam, gameTime, period, shotX, shotY, blockerId, shooterId,
eventType, ownTeamPlayersOnIce, otherTeamPlayersOnIce, xg, playerStartPositions, type
```

### `ShotMapDTO`

```text
gameShootingMap
```

### `ShotPlayerPositionDTO`

```text
playerId, x, y
```

### `SerieDTO`

```text
season, serie, nbWeeks
```

### `PlayerAwardDTO`

```text
id, awardCategory, awardIssuer, awardName, awardPoint, playerId, teamId
```

### `PlayerDTO`

```text
id, teamId, teamName, line, countryOfBirth, placeOfBirth, dateOfBirth, nationality, firstName,
lastName, role, roleCode, handedness, height, weight, captain, rookie, alternateCaptain, jersey,
pictureUrl, injured, suspended, removed, awards, sponsors, extra_description, extra_strengths,
extra_rookie_picture
```

### `SponsorDTO`

```text
companyName, sponsorLinkUrl, sponsorImageUrl
```

### `PlayerPointTableItemDTO`

```text
teamId, playerId, firstName, lastName, games, playedGames, teamGames, goals, assists,
assistsPerGame, points, pointsPerGame, plusMinus, timeOnIce, timeOnIcePerGame,
timeOnIcePerChange, shots, shotsIntoGoal, shotPercentage, shotIntoGoalPercentage,
powerPlayGoals, shortHandedGoals, winningGoals, emptyNetGoals, goalsPerGame, plus, minus,
powerPlayTime, shortHandedTime, faceOffs, faceOffsWon, faceOffsLost, faceOffPercentage,
penaltyMinutes, twoMinutePenalties, fiveMinutePenalties, tenMinutePenalties,
twentyMinutePenalties, twentyFiveMinutePenalties, shutouts, goalsAgainst, goalsAgainstPerGame,
saves, savePercentage, goalkeeperWins, goalkeeperTies, goalkeeperLosses,
goalkeeperWinPercentage, distance, distancePerGame, wins, losses, ties, removed, rookie,
injured, suspended, reserveGoalie, isU20
```

### `SimplePlayerDTO`

```text
id, teamId, teamName, countryOfBirth, placeOfBirth, dateOfBirth, nationality, firstName,
lastName, role, roleCode, handedness, height, weight, rookie, jersey, injured, suspended,
removed, captain, alternateCaptain, pictureUrl
```

### `BirthLocality`

```text
country, name
```

### `Country`

```text
code, name
```

### `GameStats`

```text
season, games, playedGames, goals, assists, points, penaltyMinutes, plus, minus, plusMinus,
powerPlayGoals, shortHandedGoals, winningGoals, shots, shotsIntoGoal, shotPercentage,
shotIntoGoalPercentage, tournament, leagueName, teamName, endTime, teamShortName, timeOnIce,
savePercentage, goalsAgainstAverage, winPercentage, shutOut, faceoffsWon, faceoffsPercentage,
wins, losses, ties, gkWins, gkLosses, gkTies, saves, goalsAgainst, faceoffTotal
```

### `Stats`

```text
regular, playoffs, practice, playout, qualifications
```

### `Team`

```text
id, name, logoUrlDarkBg, logoUrlLightBg, logoUrlOriginalDarkBg, logoUrlOriginalLightBg,
canonicalTeamId, shotmapHomeLeftInOddPeriods, teamShortName, teamExternalId
```

### `WebPlayerDTO`

```text
activeSeasons, teamSeasons, teamList, birthLocality, dateOfBirth, fihaId, firstName, lastName,
handedness, height, isSuspended, isRemoved, nationality, weight, teams, historical
```

### `WebGameByGameDTO`

```text
gameStr, gameId, date, assists, blockedOrSavedShots, faceoffsTotal, faceoffsWon,
faceoffsPercentage, goals, minus, totalPoints, homeTeamName, awayTeamName, penaltyMinutes,
penaltykillAssists, penaltykillGoals, penaltykillPoints, plus, plusMinus, powerplayAssists,
powerplayGoals, powerplaySeconds, timeOnIce, saves, savePercentage, blockOrSavedShotsPercentage,
shots, shotsIntoGoal, shutOut, shotsSaved, shotsSavedBySkater, shotPercentage,
shotIntoGoalPercentage, goalsAgainst, goalkeeper, winningGoals, won, tied, lost
```

### `PlayerStatsAllDTO`

```text
stats, birth_locality, current_jersey, current_position, current_team, date_of_birth,
date_of_death, death_locality, fiha_id, full_name, handedness, height, image, image_cropped_big,
image_cropped_small, is_suspended, nationality, nickname, resource_uri, type, weight,
is_assist_captain, is_captain, is_injured, is_removed, person, rookie, team, games, playedGames,
alumniPoints
```

### `Player`

```text
id, countryOfBirth, dateOfBirth, firstName, lastName, hand, height, placeOfBirth, weight,
nationality, lastUpdate, eliteProspectsId, namesFixed
```

### `PlayerStatsDTO`

No top-level object properties documented; inspect the linked schema.

### `WebPlayerSimpleStatisticsDTO`

```text
playerId, teamId, teamName, teamShortName, role, firstName, lastName, nationality, tournament,
pictureUrl, previousTeamsForTournament, injured, jersey, lastSeason, goalkeeper, games,
playedGames, rookie, suspended, removed, timeOnIce, current, isU20, goldenHelmets, alumniPoints,
assists, shots, goals, minus, plus, plusMinus, penalties, points, powerplayGoals,
penaltykillGoals, winningGoals, emptyNetGoals, penaltyMinutes, shutOut, faceoffWon, wins,
losses, ties, blockedOrSavedShots, goalsAgainst, faceoffTotal, gkWins, gkLosses, gkTies,
shotPercentage, savePercentage, goalsAgainstAvg, winPercentage, u20, player, team
```

### `WebPlayerStatisticsDTO`

```text
playerId, teamId, teamName, teamShortName, role, firstName, lastName, nationality, tournament,
pictureUrl, previousTeamsForTournament, injured, jersey, lastSeason, goalkeeper, games,
playedGames, rookie, suspended, removed, timeOnIce, current, isU20, goldenHelmets, alumniPoints,
accumulatingPenalties, assists, blockedOrSavedShots, corsiFor, corsiAgainst, corsiDiffTotal,
corsiPercentageFor, corsiPercentageAgainst, pdo, distanceTravelled, distancePerMatch, distance1,
distanceTravelled1, distance2, distanceTravelled2, distance3, distanceTravelled3, distance4,
distanceTravelled4, faceoffsTotal, faceoffsWon, faceoffsLost, faceoffPercentage,
faceoffCenterTotal, faceoffCenterWon, faceoffCenterLost, faceoffCenterPercentage,
faceoffDefenceTotal, faceoffDefenceWon, faceoffDefenceLost, faceoffDefencePercentage,
faceoffOffenceTotal, faceoffOffenceWon, faceoffOffenceLost, faceoffOffencePercentage,
hardestShotVelocity, gkWins, gkLosses, gkTies, goals, goals5vs5, goalsAgainstAvg, minus, plus,
plusMinus, points, penalties2Minutes, penalties5Minutes, penalties10Minutes, penalties20Minutes,
penalties25Minutes, penaltyMinutes, powerplayAssists, powerplayGoals, powerplaySeconds,
powerplay2Seconds, powerplayPoints, penaltykillAssists, penaltykillGoals, penaltykillSeconds,
penaltykill2Seconds, penaltykillPoints, shots, shots5vs5, shotsIntoGoal, shotsSaved,
shotsSaved5vs5, shotsBlocked, shotsWideOrHigh, shotPercentage, shotPercentage5vs5, shutOut,
expectedGoals, timeOnIce1, timeOnIce2, timeOnIce3, timeOnIce4, timeOnIce1Avg, timeOnIce2Avg,
timeOnIce3Avg, timeOnIce4Avg, timeOnIceAvg, topSpeed, winningGoals, winningShotCompGoals,
winningShotCompMisses, winningShotCompShots, winningShotGoals, zoneStartsDz, zoneStartsOz,
zoneStartsDzPercentage, zoneStartsOzPercentage, goalsAgainst, goalsAgainst5vs5, savePercentage,
savePercentage5vs5, win, lost, tied, powerplay2Goals, penaltykill2Goals,
powerplayPointsPercentage, penaltykillPointsPercentage, goalsToEmptyGoal, shifts, countOnIceAvg,
winningShotGkShotsTaken, winningShotGkShotsSaved, winningShotGkShotsPassed,
winningShotCompSavePercentage, winningShotCompPercentage, winPercentage, fsTeamShots,
fsTeamGoals, fsTeamShotsAgainst, fsTeamGoalsAgainst, fsTeamShotPercentage, fsTeamSavePercentage,
successfulPasses, totalPasses, passPercentage, powerplaySuccessfulPasses, powerplayTotalPasses,
powerplayPassPercentage, powerplay1SuccessfulPasses, powerplay1TotalPasses,
powerplay1PassPercentage, powerplay2SuccessfulPasses, powerplay2TotalPasses,
powerplay2PassPercentage, evenStrengthSuccessfulPasses, evenStrengthTotalPasses,
evenStrengthPassPercentage, penaltyKillSuccessfulPasses, penaltyKillTotalPasses,
penaltyKillPassPercentage, penaltyKill1SuccessfulPasses, penaltyKill1TotalPasses,
penaltyKill1PassPercentage, penaltyKill2SuccessfulPasses, penaltyKill2TotalPasses,
penaltyKill2PassPercentage, u20, player, team
```

### `PlayerStatsBasicDTO`

```text
playerId, teamId, teamName, teamShortName, role, firstName, lastName, nationality, tournament,
pictureUrl, previousTeamsForTournament, injured, jersey, lastSeason, goalkeeper, games,
playedGames, rookie, suspended, removed, timeOnIce, current, isU20, goldenHelmets, alumniPoints,
goals, assists, points, plus, minus, plusMinus, penaltyMinutes, powerplayGoals,
penaltykillGoals, winningGoals, shots, shotsIntoGoal, expectedGoals, contestWon, contestLost,
goalsToEmptyGoal, contestWonPercentage, xge, timeOnIceAvg, shotPercentage, u20, player, team
```

### `GoalieStatsBasicDTO`

```text
playerId, teamId, teamName, teamShortName, role, firstName, lastName, nationality, tournament,
pictureUrl, previousTeamsForTournament, injured, jersey, lastSeason, goalkeeper, games,
playedGames, rookie, suspended, removed, timeOnIce, current, isU20, goldenHelmets, alumniPoints,
gkWins, gkLosses, gkTies, blockedOrSavedShots, goalsAgainst, shutOut, goals, assists, points,
penaltyMinutes, expectedGoalsAgainst, reserveGoalie, contestWon, contestLost, goalsAgainstAvg,
xgea, savePercentage, winPercentage, u20, player, team
```

### `PlayerStatsShotsDTO`

```text
playerId, teamId, teamName, teamShortName, role, firstName, lastName, nationality, tournament,
pictureUrl, previousTeamsForTournament, injured, jersey, lastSeason, goalkeeper, games,
playedGames, rookie, suspended, removed, timeOnIce, current, isU20, goldenHelmets, alumniPoints,
shots, shotsIntoGoal, goals, shotsSaved, shotsWideOrHigh, shotsBlocked, hardestShotVelocity,
shotIntoGoalPercentage, shotPercentage, u20, player, team
```

### `PlayerStatsPassesDTO`

```text
playerId, teamId, teamName, teamShortName, role, firstName, lastName, nationality, tournament,
pictureUrl, previousTeamsForTournament, injured, jersey, lastSeason, goalkeeper, games,
playedGames, rookie, suspended, removed, timeOnIce, current, isU20, goldenHelmets, alumniPoints,
successfulPasses, totalPasses, powerplaySuccessfulPasses, powerplayTotalPasses,
powerplay1SuccessfulPasses, powerplay1TotalPasses, powerplay2SuccessfulPasses,
powerplay2TotalPasses, evenStrengthSuccessfulPasses, evenStrengthTotalPasses,
penaltyKillSuccessfulPasses, penaltyKillTotalPasses, penaltyKill1SuccessfulPasses,
penaltyKill1TotalPasses, penaltyKill2SuccessfulPasses, penaltyKill2TotalPasses,
underPressurePasses, underHighPressurePasses, underPressureSuccessfulPasses,
underHighPressureSuccessfulPasses, passesUnderHighPressurePercentage, passesPercentage,
passesUnderPressurePercentage, u20, player, team
```

### `PlayerStatsFaceoffsDTO`

```text
playerId, teamId, teamName, teamShortName, role, firstName, lastName, nationality, tournament,
pictureUrl, previousTeamsForTournament, injured, jersey, lastSeason, goalkeeper, games,
playedGames, rookie, suspended, removed, timeOnIce, current, isU20, goldenHelmets, alumniPoints,
faceoffsTotal, faceoffsWon, faceoffsLost, faceoffOffenceTotal, faceoffOffenceWon,
faceoffOffenceLost, faceoffDefenceTotal, faceoffDefenceWon, faceoffDefenceLost,
faceoffCenterTotal, faceoffCenterWon, faceoffCenterLost, faceoffOffencePercentage,
faceoffDefencePercentage, faceoffCenterPercentage, faceoffPercentage, u20, player, team
```

### `PlayerStatsPenaltiesDTO`

```text
playerId, teamId, teamName, teamShortName, role, firstName, lastName, nationality, tournament,
pictureUrl, previousTeamsForTournament, injured, jersey, lastSeason, goalkeeper, games,
playedGames, rookie, suspended, removed, timeOnIce, current, isU20, goldenHelmets, alumniPoints,
penaltyMinutes, penalties2Minutes, penalties5Minutes, penalties10Minutes, penalties20Minutes,
penalties25Minutes, accumulatingPenalties, u20, player, team
```

### `PlayerStatsGoalsDTO`

```text
playerId, teamId, teamName, teamShortName, role, firstName, lastName, nationality, tournament,
pictureUrl, previousTeamsForTournament, injured, jersey, lastSeason, goalkeeper, games,
playedGames, rookie, suspended, removed, timeOnIce, current, isU20, goldenHelmets, alumniPoints,
goals, shots, shotsIntoGoal, powerplayGoals, powerplay2Goals, penaltykillGoals,
penaltykill2Goals, winningGoals, goalsToEmptyGoal, winningShotCompGoals, winningShotGoals,
shotPercentage, u20, player, team
```

### `PlayerStatsPPPKDTO`

```text
playerId, teamId, teamName, teamShortName, role, firstName, lastName, nationality, tournament,
pictureUrl, previousTeamsForTournament, injured, jersey, lastSeason, goalkeeper, games,
playedGames, rookie, suspended, removed, timeOnIce, current, isU20, goldenHelmets, alumniPoints,
points, powerplayGoals, powerplay2Goals, penaltykillGoals, penaltykill2Goals, powerplayAssists,
powerplayPoints, penaltykillAssists, penaltykillPoints, powerplayPointsPercentage,
penaltykillPointsPercentage, u20, player, team
```

### `PlayerStatsSkatingDTO`

```text
playerId, teamId, teamName, teamShortName, role, firstName, lastName, nationality, tournament,
pictureUrl, previousTeamsForTournament, injured, jersey, lastSeason, goalkeeper, games,
playedGames, rookie, suspended, removed, timeOnIce, current, isU20, goldenHelmets, alumniPoints,
distanceTravelled, distance1, distance2, distance3, distance4, topSpeed, distancePerMatch,
distanceTravelled1, distanceTravelled2, distanceTravelled3, distanceTravelled4, u20, player,
team
```

### `PlayerStatsTimeOnIceDTO`

```text
playerId, teamId, teamName, teamShortName, role, firstName, lastName, nationality, tournament,
pictureUrl, previousTeamsForTournament, injured, jersey, lastSeason, goalkeeper, games,
playedGames, rookie, suspended, removed, timeOnIce, current, isU20, goldenHelmets, alumniPoints,
shifts, powerplaySeconds, powerplay2Seconds, penaltykillSeconds, penaltykill2Seconds,
timeOnIce1, timeOnIce2, timeOnIce3, timeOnIce4, countOnIceAvg, timeOnIceAvg, timeOnIce1Avg,
timeOnIce2Avg, timeOnIce3Avg, timeOnIce4Avg, u20, player, team
```

### `PlayerStatsWinningShotCompDTO`

```text
playerId, teamId, teamName, teamShortName, role, firstName, lastName, nationality, tournament,
pictureUrl, previousTeamsForTournament, injured, jersey, lastSeason, goalkeeper, games,
playedGames, rookie, suspended, removed, timeOnIce, current, isU20, goldenHelmets, alumniPoints,
winningShotCompShots, winningShotCompGoals, winningShotCompMisses, winningShotGoals,
winningShotCompPercentage, u20, player, team
```

### `GoalieStatsWinningShotCompDTO`

```text
playerId, teamId, teamName, teamShortName, role, firstName, lastName, nationality, tournament,
pictureUrl, previousTeamsForTournament, injured, jersey, lastSeason, goalkeeper, games,
playedGames, rookie, suspended, removed, timeOnIce, current, isU20, goldenHelmets, alumniPoints,
winningShotGkShotsTaken, winningShotGkShotsSaved, winningShotGkShotsPassed, reserveGoalie,
winningShotCompSavePercentage, u20, player, team
```

### `PlayerStatsAdvancedDTO`

```text
playerId, teamId, teamName, teamShortName, role, firstName, lastName, nationality, tournament,
pictureUrl, previousTeamsForTournament, injured, jersey, lastSeason, goalkeeper, games,
playedGames, rookie, suspended, removed, timeOnIce, current, isU20, goldenHelmets, alumniPoints,
corsiFor, corsiAgainst, corsiDiffTotal, zoneStartsOz, zoneStartsDz, fsTeamShots,
fsTeamShotsAgainst, fsTeamGoals, fsTeamGoalsAgainst, corsiPercentageFor, zoneStartsDzPercentage,
zoneStartsOzPercentage, fsTeamShotPercentage, fsTeamSavePercentage, pdo, u20, player, team
```

### `GameMilestone`

```text
gameTitle, gameId, season
```

### `MilestoneCategory`

```text
milestone, players
```

### `MilestonesDTO`

```text
games, goals, assists, points
```

### `PlayerMilestone`

```text
awardGame, celebrationGame, games, assists, goals, playerId, points, firstName, lastName,
teamExternalId, teamId, teamName, pictureUrl, role, jersey
```

### `Game`

```text
awayGoals, awayTeamAbbreviation, date, fihaID, finished, finishedType, homeGoals,
homeTeamAbbreviation, season, tournamentType
```

### `GamePlayer`

```text
absenceReason, absent, inOpeningLineup, player
```

### `PlayerGameDTO`

```text
assists, blockedOrSavedShots, corsiAgainst, corsiAgainstClose, corsiDiff, corsiDiffClose,
corsiFor, corsiForClose, countOnIce, countOnIce1, countOnIce2, countOnIce3, faceoffCenterLost,
faceoffCenterTotal, faceoffCenterWon, faceoffDefenceLost, faceoffDefenceTotal,
faceoffDefenceWon, faceoffOffenceLost, faceoffOffenceTotal, faceoffOffenceWon,
faceoffPercentage, faceoffsLost, faceoffsTotal, faceoffsWon, fsshotsOnGoalAgainst,
fsshotsOnGoalFor, fsgoals, game, gamePlayer, goals, goalsToEmptyGoal, league, minusPoints,
penaltyMinutes, penaltykill2Goals, penaltykill2Seconds, penaltykillAssists, penaltykillGoals,
penaltykillPoints, penaltykillSeconds, person, plusMinusDiff, plusPoints, powerplay2Goals,
powerplay2Seconds, powerplayAssists, powerplayGoals, powerplayPoints, powerplaySeconds,
resourceURI, season, shotPercentage, shotsIntoGoal, shotsSaved, shotsSavedBySkater,
shotsWideOrHigh, team, timeOnIce, timeOnIce1, timeOnIce2, timeOnIce3, timeOnIce4, totalPoints,
totalShots, tournament, winningGoals, winningShotCompGoals, winningShotCompMisses,
winningShotCompShots, winningShotGoals, fsZoneStartsDz, fsZoneStartsOz, penalties2Minutes,
penalties5Minutes, penalties10Minutes, penalties20Minutes, penalties25Minutes
```

### `TeamId`

```text
internalId, nameTag, formattedNameTag, externalId
```

### `TeamPlayer`

```text
teamId, playerId
```

### `PlayerRoleDTO`

```text
teamId, playerId, roles
```

### `SuspensionDTO`

```text
id, startDate, playerId, lengthInGames, gamesSatOut, finished
```

### `PenaltyDto`

```text
id, eventID, logtime, gametime, period, penaltyBegintime, penaltyEndtime, penaltyMinutes,
penaltyFaultCode, penaltyFaultType, lField, playerJersey, isExternalReferee, minor, major,
misconduct, gameMisconduct, gameId, penaltyCodeId, playerId, refereeId, sufferPlayerId,
sufferJersey, season, teamId, resolution, suspension, lfield
```

### `SuspensionDto`

```text
id, startDate, lengthInGames, gamesSatOut, finished, playerId
```

### `IceRinkDTO`

```text
id, name, latitude, longitude, streetAddress, zip, city
```

### `GamblingEventDTO`

```text
homeTeamOdds, awayTeamOdds, tieOdds, url
```

### `GameDTO`

```text
id, season, start, end, homeTeam, awayTeam, winningShotCompetitionEvents, periods, started,
ended, finishedType, currentPeriod, gameTime, spectators, playOffPair, playOffPhase,
playOffReqWins, buyTicketsUrl, gamblingEvent, referees, videoURL, thumbURL, cacheUpdateDate,
provider, stale, serie, gameWeek, iceRink
```

### `GamePeriodDTO`

```text
index, homeTeamGoals, awayTeamGoals, category, startTime, endTime
```

### `GameReferee`

```text
firstName, jersey, lastName, officialID, roleAbbrv, roleName, secondaryID, tagA, tagB,
pictureUrl
```

### `GameTeamDTO`

```text
teamId, teamPlaceholder, teamName, goals, timeOut, goalEvents, penaltyEvents, goalKeeperEvents,
goalKeeperChanges, powerplayInstances, powerplayGoals, shortHandedInstances, shortHandedGoals,
expectedGoals, ranking, gameStartDateTime, logos
```

### `GamesDTO`

```text
games, previousGameDate, nextGameDate
```

### `GoalEventDTO`

```text
scorerPlayerId, scorerPlayer, logTime, winningGoal, gameTime, period, eventId, goalTypes,
assistantPlayerIds, assistantPlayers, plusPlayerIds, minusPlayerIds, homeTeamScore,
awayTeamScore, assistsSoFarInSeason, goalsSoFarInSeason, videoClipUrl, videoClipPlaylistUrl,
videoThumbnailUrl
```

### `GoalKeeperChangeDTO`

```text
previousGoalie, nextGoalie, time, period, eventId
```

### `GoalKeeperEventDTO`

```text
playerId, beginTime, emptyNet, endTime, eventId, logTime, gameTime, period
```

### `PenaltyEventDTO`

```text
playerId, suffererPlayerId, eventId, logTime, gameTime, period, penaltyBegintime,
penaltyEndtime, penaltyFaultName, penaltyFaultType, penaltyInfo, penaltyMinutes
```

### `WinningShotCompetitionItemDTO`

```text
shootingPlayerId, blockingPlayerId, shotNumber, shootingTeamId, blockingTeamId, goalScored,
winningGoal
```

### `GameDetailsDTO`

```text
game, awards, homeTeamPlayers, awayTeamPlayers
```

### `GamePlayerStatsDTO`

```text
playerId, topSpeed, hardestShot
```

### `GameStatsDTO`

```text
awayTeam, homeTeam, homeTeamGamePlayerStats, awayTeamGamePlayerStats, puckStats
```

### `PeriodDTO`

```text
points, period, assists, goals, plusminus, plus, minus, shots, penaltyminutes, timeofice,
powerplayGoals, shortHandedGoals, winningGoal, blockedShots, faceoffsTotal, faceoffsWon,
corsiFor, corsiAgainst, faceoffsCenterTotal, faceoffsCenterWon, faceoffsDefenceTotal,
faceoffsDefenceWon, faceoffsOffenceTotal, faceoffsOffenceWon, fsZoneStartsOz, fsZoneStartsDz,
powerplay2Goals, penaltykill2Goals, powerplayAssists, penaltykillAssists, goalsToEmptyGoal,
fsTeamShots, fsTeamGoals, fsTeamShotsAgainst, fsTeamGoalsAgainst
```

### `PeriodTeamStatsDTO`

```text
teamId, period, goals, shots, powerPlayInstances, powerPlayGoals, shortHandedInstances,
shortHandedGoalsAgainst, penaltyMinutes, faceOffWins, periodPlayerStats, goaliePeriodStats,
totalDistanceTravelled, twoMinutePenalties, fiveMinutePenalties, tenMinutePenalties,
twentyMinutePenalties
```

### `PuckStatsDTO`

```text
periodNumber, homeTeamControlDuration, awayTeamControlDuration, contestedControlDuration,
distance
```

### `SinglePeriodPlayerStatsDTO`

```text
jerseyId, playerId, period, distance, totalPasses, successfulPasses, playerPassesUnderPressure,
playerSuccessfulPassesUnderPressure, playerPassesUnderHighPressure,
playerSuccessfulPassesUnderHighPressure, expectedGoalsPlayer, expectedGoalsTeam,
expectedGoalsAgainst, expectedGoalsAgainstShotOnGoal
```

### `GamePlayersDTOv2`

```text
homeTeamPlayers, awayTeamPlayers
```

### `PlayerWithStatsDTO`

```text
playerDTO, allTimeStats, seasonStats, seasonStatsInTeam, vsTeamStats
```

### `PlayersWithStatsResponseDTO`

```text
homeTeamPlayers, awayTeamPlayers
```

### `PlayerToWatchDTO`

```text
playerId, playerName, playerJersey, role, value, category
```

### `PlayerComparisonDTO`

```text
playerId, value
```

### `GamePlayerPointTableItemDTO`

```text
playerId, jersey, role, firstName, lastName, teamId, goals, assists, timeOnIce, plus, minus,
powerplayGoals, penaltyKillGoals, winningGoals, shots, faceoffsWon, faceoffsLost, saves,
goalAgainst, penaltyMinutes, skatedDistance, topSpeed, hardestShot, shotPercentage,
faceoffPercentage, savePercentage, plusMinus, points
```

### `PastAndFutureGamesDTO`

```text
pastGamesBetweenTeams, futureGamesHomeTeam, futureGamesAwayTeam
```

### `GoalieComparisonDTO`

```text
record, gaa, savePercentage, so, player, playerId
```

### `TournamentDTO`

```text
season, season_name, tournament_type, tournament_type_name, serie_start_date, serie_end_date
```

### `ScheduleItemDTO`

```text
id, serie, season, homeTeamName, awayTeamName, homeTeamId, awayTeamId, homeTeamPlaceholder,
awayTeamPlaceholder, homeTeamGoals, awayTeamGoals, expectedHomeTeamGoals, expectedAwayTeamGoals,
gameTime, started, ended, homeTeamWinner, spectators, homeTeamRanking, awayTeamRanking,
playOffPair, playOffPhase, playOffReqWins, start, buyTicketsUrl, finishedType, iceRinkId,
homeTeam, iceRink
```

### `GameWeekDTO`

```text
currentGameWeek, maxGameWeek
```

### `AlumniRoundDTO`

```text
id, season, serie, date_1, player_1_id, date_2, player_2_id, date_3, player_3_id, player_1_stat,
player_2_stat, player_3_stat, choosers, team_1_id, team_2_id, team_3_id
```

