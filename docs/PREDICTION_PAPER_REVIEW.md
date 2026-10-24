# Paper review and Liiga adaptation

Reviewed: 2026-10-24. Status: research and implementation specification, not an
implemented, trained, or validated hockey prediction model.

## Reference and scope

Daniel Berrar, Philippe Lopes, and Werner Dubitzky (2024), **A data- and
knowledge-driven framework for developing machine learning models to predict
soccer match outcomes**, *Machine Learning* 113, 8165–8204.
[DOI: 10.1007/s10994-024-06625-9](https://doi.org/10.1007/s10994-024-06625-9).

Source reviewed: the user's 40-page JSON extraction of the paper. Page references
below use PDF page numbers, followed where useful by journal page numbers.
The extraction loses some mathematical typesetting; do not treat the parsed
formulas as executable specifications without checking their rendering.

The article states CC BY 4.0 licensing (PDF p. 38). This document attributes and
summarizes the research and marks proposed hockey-specific changes as our own.
The article says author code is available upon request; we have not obtained or
executed it and are not claiming to reproduce its implementation exactly.

## Assessment

Adopt the paper's interpretable feature-engineering approach as a **candidate
baseline**. Test it against league-prior and Elo baselines before adding richer
features. It is a soccer forecasting study, not evidence of hockey accuracy,
a league-impact simulator, or an LLM prediction method.

The useful hypothesis is that carefully constructed history features and
relatively simple learners can be competitive. Neither six features, kNN,
long history windows, nor concatenating seasons is guaranteed to work best
for Liiga.

## What the paper actually proposes

### Team histories and competition context

The authors process each league separately, concatenate its seasons in
chronological order, and call this a **super league**. Each team's pre-match
history may cross season boundaries and even periods in which that team was
absent from the division (PDF pp.14–16 / journal pp.8178–8180).

Feature generation is competition-specific. The resulting datasets can then
be used for league-specific training or combined into a meta-league dataset.
This is not the same as pooling all sports or competitions indiscriminately.

The paper recognizes roster/coaching changes, gaps, new teams, and sparse
history as limitations. Its cross-season concatenation does not solve them.

### The six-feature representation

The main **total** feature vector describes the home team first, then the away
team. Table 7 and section 5.5 (PDF pp.17–19 / journal pp.8181–8183) specify:

| Feature | Meaning |
|---|---|
| Home goals scored | Average goals scored in the home club's recent n matches, across both venues |
| Home goals conceded | Average goals conceded in those matches |
| Home normalized rank | Recent-form league-success context, normalized from first = 1 to last = 0 |
| Away goals scored | Equivalent recent scoring average for the away club |
| Away goals conceded | Equivalent recent conceding average for the away club |
| Away normalized rank | Equivalent recent-form league-success context for the away club |

Goal features use ordinary means. The home/away ordering of the two team
profiles permits an implicit home-advantage effect even in the six-feature set.

**Rank needs an explicit implementation definition.** Table 6 illustrates a
league table constructed from each club's last n results, while surrounding
prose calls the feature an average normalized rank. It is not safe to replace
it with today's current standings when producing historical training rows.
The normalization consistent with its stated endpoints and examples is
`(N - rank) / (N - 1)`, where N is the relevant table's team count. The extraction
omits the denominator of equation 5, but its N = 20 example agrees: rank 2 becomes
approximately 0.95 and rank 3 approximately 0.89.

For our adaptation, explicitly define a pre-match recent-form table, the active
team cohort, partial-history treatment, points rules, tie handling, and N <= 1
fallback. Mark these choices as our specification rather than asserting exact
author-code reproduction. An all-time list of clubs must not introduce teams
unknown at the prediction cutoff.

The authors discuss strength of opposition but do **not** provide a direct
Elo-style opponent weighting for each historic goal. Their rank feature provides
context; describing the entire method as fully opponent-adjusted would overstate it.

### The 18-feature alternative

The **homeaway** representation includes the six total features, plus the same
three quantities from each club's own home history and own away history:

```text
2 clubs x 3 quantities x 3 contexts(total/home/away) = 18 features
```

This means both teams' home and away histories, not only the home club at home
and away club away. The separate windows may contain different matches from
the last n total matches. The paper conceptually uses n/2 for each venue window;
its actual n=9..100 sweep includes odd n without an explicit rounding rule.
An even-numbered initial grid avoids that ambiguity in our implementation.

### Recency is learned, not assumed

The study searches n=9..100, using Pearson-correlation and kNN-based procedures
(PDF pp.20–21,26–27). Some selected windows span more than one season.
This motivates testing several history lengths instead of assuming five games
is optimal. It does not justify copying an English soccer league's chosen n
into Liiga.

Their later exhaustive kNN search jointly evaluates k=3..350 and 92 recency
windows per league, reportedly taking about two weeks across 44 leagues on an
i7/64 GB machine. We should use a modest grid and chronological folds first.

They exclude training fixtures where either team has fewer than six prior
matches, removing 10,366 of 302,691 records (3.43%). They acknowledge that some
remaining teams still have less history than the selected window.

### Learners

The paper evaluates k-nearest neighbors, small neural networks, ordinal forests,
and naive Bayes, plus reference/baseline models. The DeepFoot name is a team/model
prefix, not a requirement to build a large deep network (PDF pp.21–34).

kNN asks which historical pre-match feature profiles resemble the upcoming
fixture, then derives predictions from those neighbors. For forecasting, the
neighbor pool itself must contain only earlier matches, not future rows whose
feature vectors happen to have been calculated correctly.

## Evidence and limitations

Training data: 302,691 soccer matches from 51 leagues in 34 countries. After
schedule changes, the final future evaluation covered 714 matches from 43 leagues
(PDF pp.6–8). These counts are not Liiga sample sizes; league-specific models
use their corresponding competition histories rather than all 302,691 rows.

Selected results (Tables 13–14, PDF pp.32–33):

| Model | Score RMSE | Result RPS |
|---|---:|---:|
| kNN2, completed after deadline | 1.6227 | 0.2122 |
| Original kNN | 1.6339 | 0.2117 |
| ANN, completed after deadline | 1.6479 | 0.2113 |
| Simple Baseline-N | 1.6653 | 0.2234 |
| Bookmaker benchmark | 1.7433 | 0.2063 |

Lower is better for both metrics. RMSE and RPS are not percentages of correct
winner picks. kNN2 has the best reported score error; bookmaker probabilities
have the best result RPS. More features/complexity did not guarantee improvement.

The authors organized the challenge and explicitly participated out of
competition. Several strongest reported variants were completed after the
deadline. Do not present these as a contemporaneous winning submission or
proof of betting profitability; the paper says the latter was not established.

The score RMSE uses the sum of both teams' squared errors per match before
averaging and taking the square root. It differs by scale from averaging over
2n separate team-score errors. RPS uses ordered home win/draw/away win categories;
for prediction (0.6, 0.3, 0.1) and an observed draw, its example gives 0.185.

The paper explicitly acknowledges possible temporal information leakage from
random splits/CV (PDF p.16 / journal p.8180). kNN uses LOOCV; ANN uses repeated
random 85/15 splits; forests use a random holdout. A genuinely future final
prediction set is useful evidence, but does not remove this tuning/validation
limitation, and post-deadline variants need additional qualification.

We should use chronological evaluation, fitted preprocessing only on training
folds, untouched final testing, and probability calibration diagnostics. No
published soccer number should be advertised as our expected hockey accuracy.

## What changes for hockey

| Soccer paper | Liiga adaptation |
|---|---|
| Final home win / draw / away win | Regulation home win/tie/away win, followed by extra-time resolution, or a direct four-outcome model |
| Soccer 3–1–0 points | Verified season-specific regulation/extra-time 3–2–1–0 points |
| Final score used for score learning | Regulation scores from NORMAL periods; do not count the artificial shootout-winning goal as a regulation goal |
| Soccer rank/form table | Explicit historical Liiga form table and verified points/tie-break semantics |
| Seasons simply concatenated, including gaps | Compare carryover, seasonal decay, and resets; handle returning/new clubs and changing rosters |
| Selected soccer history windows | Tune modest Liiga-specific windows using historical folds |
| Soccer ordinal score classes/tail filtering | Reassess distribution/ordering; do not discard rare hockey scores automatically |
| Pure match-history features | Add xG/shots/rest/special teams/announced goalie inputs as separately measured extensions |

We have inspected 131 completed current-season Liiga results. That is enough to
exercise a pipeline, not evidence of robust predictive performance. Use multiple
validated historical seasons and report the number of usable regulation-tie
and extra-time outcomes too.

## Proposed first implementation

This sequence is our implementation proposal, not a claimed result of the paper.

1. **Retain outcomes correctly.** Extend the current adapter to retain season,
   competition, regulation goals, final goals/winner, finishedType, periods,
   and trustworthy cutoff/source metadata. Existing normalization currently
   discards several required fields; see [data inventory](PREDICTION_DATA.md).
2. **Build training rows in time order.** Construct each row before processing
   that match's result. Avoid matches with uncertain completion timing as inputs
   to overlapping/same-day predictions, or use a conservative date cutoff.
3. **Define the six features precisely.** Calculate lagged scoring/conceding and
   the specified recent-form table rank. Use explicit low-history priors and
   sample counts; do not silently equate unknown strength with zero strength.
4. **Benchmark.** Compare league-prior probabilities and Elo with a paper-inspired
   kNN and a regularized logistic model. Use a modest even-window/neighbor grid;
   validate a training-only scaler because rank and goal means have different scales.
5. **Evaluate chronologically.** Use earlier seasons for training and later blocks
   for validation, with inner chronological tuning and a final untouched test
   season/block. No later rows may enter a kNN neighbor pool or feature scaler.
6. **Measure probability quality.** Log loss, Brier score, calibration and accuracy
   for final/four-way outcomes; RPS for regulation home/tie/away where the order
   is meaningful. Score RMSE is an additional, distinct task.
7. **Test additions.** Compare 18 features and then add rolling xG, shots, rest,
   special teams and announced-goalie features. Retain them only if the historical
   evaluation supports improvement. These additions are not the paper's six inputs.
8. **Integrate the selected model.** Serve forecasts with cutoff time, version,
   data coverage and model status. Show final-win and regulation probabilities
   distinctly. Do not replace missing trained outputs with fabricated percentages.

A useful initial outcome decomposition is:

```text
pH = P(home regulation win)
pD = P(regulation tie)
pA = P(away regulation win)
q  = P(home wins extra time/shootout | regulation tie)

P(home final win) = pH + pD*q
P(away final win) = pA + pD*(1-q)

Four points-relevant outcomes:
  home regulation win = pH
  home extra-time win = pD*q
  away extra-time win = pD*(1-q)
  away regulation win = pA
```

Estimate q from earlier hockey data and evaluate/calibrate it; do not assume
0.5 without measuring a baseline. A direct four-class model is an alternative
to compare. A point prediction such as 3–2 is not a score distribution.

## League-impact extension: our addition

The paper does not implement league-impact forecasting. Its league-rank feature
should not be confused with a season simulation.

For our product, combine calibrated match probabilities with official current
standings, remaining fixtures, season-specific points/tie-break rules and score
simulations where necessary. Run baseline Monte Carlo simulations, then compare
with scenarios forcing each outcome of the selected fixture.

Possible outputs: expected points/rank changes, qualification probabilities,
regular-season first-place probability, and changes for every rival. Ultimate
championship probability additionally needs playoff bracket/rules simulation.

The current API's numerical playoff boundaries do not fully specify their
meaning or the season's rules. Exact qualification/title claims remain blocked
until those rules are verified and encoded. Parameter/model uncertainty should
not be mistaken for certainty just because many simulations were run.

Gemini can explain the calculated probabilities, relevant inputs and scenario
differences. It should not invent missing data, numerical probabilities or rules.

## Acceptance criteria before describing predictions as working

- Each training feature is reproducibly as-of its cutoff; no future result enters
  features, preprocessing, tuning or neighbors.
- Training/evaluation datasets are identified by season/game IDs and data versions.
- Regulation ties and extra-time/shootout outcomes map to correct labels/points.
- Cold starts and unavailable lineup/xG data have explicit handling.
- A held-out chronological evaluation reports baseline comparisons and calibration.
- Probabilities are finite, within [0, 1], sum to 1, and final/conditional outputs agree.
- Simulation reproduces current standings under the verified rule set and handles
  tied points, postponed/cancelled games, and completed versus remaining fixtures.
- UI explanations use model outputs and state data/model limitations honestly.

No prediction code, trained model, hockey accuracy, or league simulation has
been validated by this literature review.
