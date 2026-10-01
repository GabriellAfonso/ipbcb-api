"""Custom Prometheus metrics for IPBCB business events.

All metrics use the `ipbcb_` namespace prefix. Import counters directly
in service methods and call `.labels(...).inc()` to record events.

>>> from core.metrics import LOGIN_COUNTER
>>> LOGIN_COUNTER.labels(result="success", login_type="credentials").inc()
"""

from prometheus_client import Counter

LOGIN_COUNTER = Counter(
    "ipbcb_login_total",
    "Total login attempts",
    ["result", "login_type"],
)

SCHEDULE_GENERATED_COUNTER = Counter(
    "ipbcb_schedule_generated_total",
    "Total schedule previews generated",
)

SCHEDULE_SAVED_COUNTER = Counter(
    "ipbcb_schedule_saved_total",
    "Total schedules saved",
)

SONG_PLAYS_REGISTERED_COUNTER = Counter(
    "ipbcb_song_plays_registered_total",
    "Total song play registrations",
)

CHORD_CHART_VIEWS_COUNTER = Counter(
    "ipbcb_chord_chart_views_total",
    "Total chord chart list views",
)

LYRICS_VIEWS_COUNTER = Counter(
    "ipbcb_lyrics_views_total",
    "Total lyrics list views",
)

# Server process only: the reminder container is not scraped, its logs are the record there
# (specs/017-sunday-setlist-push R-15).
PUSH_MESSAGES_COUNTER = Counter(
    "ipbcb_push_messages_total",
    "Push messages handed to the provider, by message type and per-device outcome",
    ["type", "outcome"],
)
