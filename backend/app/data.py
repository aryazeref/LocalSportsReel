"""Offline fixture adapter. Every event here is synthetic, not a real result.

Later we will replace `load_moments()` with an adapter for the event API the
hackathon provides. Downstream functions do not need to know the data source.
"""
from .models import Moment, Fact

CITIES = {
    "Oulu": (65.0121, 25.4651),
    "Rovaniemi": (66.5039, 25.7294),
    "Tampere": (61.4978, 23.7610),
    "Helsinki": (60.1699, 24.9384),
}


def sample_moment(
    event_id: str, city: str, sport: str, league: str, team: str,
    athlete: str, title: str, moment_type: str, excitement: float,
    score: str, happened_at: str, extra_fact: str,
) -> Moment:
    lat, lon = CITIES[city]
    source_id = f"synthetic:{event_id}"
    return Moment(
        id=event_id, city=city, latitude=lat, longitude=lon,
        happened_at=happened_at, sport=sport, league=league,
        team=team, athlete=athlete, title=title,
        moment_type=moment_type, excitement=excitement, score=score,
        source_id=source_id, source_label="Synthetic hackathon fixture",
        demo=True, video_url=None, video_authorized=False,
        facts=[
            Fact(id=f"{event_id}-1", text=f"{athlete} was involved in a {moment_type} for {team}.", source_id=source_id),
            Fact(id=f"{event_id}-2", text=f"The reported match score in this scenario was {score}.", source_id=source_id),
            Fact(id=f"{event_id}-3", text=extra_fact, source_id=source_id),
        ],
    )


MOMENTS = [
    sample_moment("oulu-001", "Oulu", "Ice hockey", "Demo Northern League", "Oulu Comets",
        "Aino Virtanen", "Last-minute winner sends the arena buzzing", "goal", 0.97, "3–2",
        "2026-10-22T18:42:00+03:00", "The deciding goal came with under two minutes remaining."),
    sample_moment("oulu-002", "Oulu", "Football", "Demo Community Cup", "Oulu United",
        "Mika Lehtinen", "A breathtaking strike from distance", "long-range goal", 0.93, "2–1",
        "2026-10-21T17:15:00+03:00", "The shot was taken from outside the penalty area."),
    sample_moment("oulu-003", "Oulu", "Ice hockey", "Demo Northern League", "Oulu Comets",
        "Eero Niemi", "A game-saving stop when it mattered most", "save", 0.90, "3–2",
        "2026-10-22T18:33:00+03:00", "The save took place during the third period."),
    sample_moment("rov-001", "Rovaniemi", "Ice hockey", "Demo Arctic League", "Rovaniemi Foxes",
        "Jonna Laine", "A remarkable shorthanded breakaway", "breakaway goal", 0.91, "4–3",
        "2026-10-20T19:10:00+03:00", "The attacking team was playing with one fewer skater."),
    sample_moment("tam-001", "Tampere", "Basketball", "Demo City Series", "Tampere Sparks",
        "Sami Koskinen", "A buzzer-beater to remember", "buzzer-beater", 0.99, "78–77",
        "2026-10-22T20:04:00+03:00", "The basket was scored at the end of regulation."),
    sample_moment("hel-001", "Helsinki", "Football", "Demo Metro League", "Helsinki Waves",
        "Sara Nieminen", "A comeback completed in stoppage time", "goal", 0.95, "3–2",
        "2026-10-19T17:58:00+03:00", "The winning goal was scored in stoppage time."),
]


def load_moments() -> list[Moment]:
    """Return independent models, preventing a caller from mutating shared data."""
    return [m.model_copy(deep=True) for m in MOMENTS]
