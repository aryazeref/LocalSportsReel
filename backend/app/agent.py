"""An intentionally small, inspectable agent pipeline.

Stage 1: discover nearby moments from data.
Stage 2: validate factual provenance and filter unauthorized video links.
Stage 3: rank relevant moments.
Stage 4: prepare a grounded story, optionally with an LLM.

An LLM never determines the actual match result; it only rephrases supplied
facts. Any LLM output remains a draft requiring a human editor.
"""
import math
import os
from datetime import datetime, timezone
from .data import CITIES, load_moments
from .models import Moment, FeedMoment, FeedResponse, Story, DraftText

# This function calculates the great-circle distance between two points on the Earth using the Haversine formula. The coordinates are provided in decimal degrees, and the result is returned in kilometers.
# This is used to filter sports moments based on their proximity to a specified city within a given radius.
def haversine_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    """Great-circle distance on Earth; coordinates are in decimal degrees."""
    r = 6371.0
    latitude_difference = math.radians(b_lat - a_lat)
    longitude_difference = math.radians(b_lon - a_lon)
    a = (math.sin(latitude_difference / 2) ** 2
         + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat))
         * math.sin(longitude_difference / 2) ** 2)
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))

# This function is used to validate the correctness and integrity of a sports moment object. It checks for the presence of a source ID and factual evidence, ensures that all evidence matches the event's source, and verifies that any associated video is authorized for display. If any of these checks fail, it raises a ValueError to prevent the moment from being processed further.
def verify_moment(m: Moment) -> None:
    """Fail closed if the object lacks traceable evidence or safe media rights.

This checks the integrity of evidence references, not the independent truth of
external sports feeds. Production ingestion needs extra reconciliation against
trusted league sources before a real event can be marked verified.
"""
    if not m.source_id or not m.facts:
        raise ValueError("Missing source attribution or factual evidence")
    if any(not f.text.strip() or f.source_id != m.source_id for f in m.facts):
        raise ValueError("Evidence did not match the event's source")
    if m.video_url and not m.video_authorized:
        raise ValueError("Video cannot be shown without authorization")


def build_feed(city: str, radius_km: int = 50, sport: str = "All") -> FeedResponse:
    """Discover -> verify -> rank. No AI call or API key needed."""
    if city not in CITIES:
        raise ValueError("Unsupported city")
    if not 5 <= radius_km <= 500:
        raise ValueError("Radius must be between 5 and 500 km")

    user_lat, user_lon = CITIES[city]
    now = datetime.now(timezone.utc)
    feed = []
    for moment in load_moments():
        if sport != "All" and moment.sport != sport:
            continue
        distance = haversine_km(user_lat, user_lon, moment.latitude, moment.longitude)
        if distance > radius_km:
            continue
        verify_moment(moment)
        hours = max(0, (now - datetime.fromisoformat(moment.happened_at)).total_seconds() / 3600)
        freshness = math.exp(-hours / (24 * 14))
        proximity = 1 - min(1, distance / radius_km)
        # Interpretable ranking: moments + location + recency, not black-box hype.
        score = 0.55 * moment.excitement + 0.25 * proximity + 0.20 * freshness
        feed.append(FeedMoment(**moment.model_dump(), distance_km=round(distance, 1),
                               relevance_score=round(score, 4)))

    feed.sort(key=lambda m: (-m.relevance_score, m.id))
    return FeedResponse(selected_city=city, radius_km=radius_km,
                        total=len(feed), demo_data=True, moments=feed)


def find_moment(moment_id: str) -> Moment:
    for moment in load_moments():
        if moment.id == moment_id:
            verify_moment(moment)
            return moment
    raise LookupError("No such moment")


def template_story(moment: Moment) -> Story:
    """Safe offline baseline: only explicit fields and approved source facts."""
    # These are synthetic facts, so the whole output must visibly remain a demo.
    narration = (
        f"In our fictional {moment.league} scenario in {moment.city}, "
        f"{moment.athlete} delivered a {moment.moment_type} for {moment.team}. "
        f"{moment.facts[2].text} The scenario's final score was {moment.score}. "
        "Discover more local sporting moments in your area."
    )
    return Story(moment_id=moment.id, headline=moment.title, narration=narration,
                 evidence=moment.facts, mode="template", publication_status="demo_only",
                 disclaimer="Synthetic demonstration: no real match result or footage is represented.")


def create_story(moment_id: str) -> Story:
    """Optional LLM drafting with schema and provenance checks.

Set OPENAI_API_KEY in your backend environment to use the LLM. When unset,
return the deterministic version. Never silently invent an official report.
"""
    moment = find_moment(moment_id)
    if not os.environ.get("OPENAI_API_KEY"):
        return template_story(moment)

    from openai import OpenAI  # Import only if configured; offline demo stays light.
    client = OpenAI()
    try:
        response = client.responses.parse(
            model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
            instructions=(
                "You are a sports newsroom DRAFT writer. Use only supplied facts. "
                "Do not invent details, quotes, skill judgments, video descriptions, "
                "statistics, or future outcomes. The data is synthetic. Keep it "
                "clearly labeled fictional. Write a punchy headline and a short "
                "two-sentence narration. Cite the fact IDs you relied on."
            ),
            input=(f"Synthetic sports moment: {moment.model_dump_json()}"),
            text_format=DraftText,
        )
        draft = response.output_parsed
        if draft is None or not draft.used_fact_ids:
            raise ValueError("Model provided no grounded facts")
        allowed_ids = {f.id for f in moment.facts}
        if not set(draft.used_fact_ids).issubset(allowed_ids):
            raise ValueError("Model referenced unrecognized facts")
        if not draft.headline.strip() or not draft.narration.strip():
            raise ValueError("Model generated empty text")
        # A correct schema and evidence IDs do NOT establish semantic truth.
        return Story(moment_id=moment.id, headline=draft.headline,
                     narration=draft.narration,
                     evidence=[f for f in moment.facts if f.id in draft.used_fact_ids],
                     mode="llm_draft", publication_status="review_required",
                     disclaimer="AI-generated draft from synthetic data. Human review required.")
    except Exception:
        # A failed AI service must not prevent users from seeing a grounded story.
        return template_story(moment)
