"""Data model — §17. SQLModel tables; embeddings as blobs (D-01)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- watchlist ---------------------------------------------------------
class Account(SQLModel, table=True):
    __tablename__ = "account"
    id: Optional[int] = Field(default=None, primary_key=True)
    handle: str = Field(index=True, unique=True)
    display_name: str = ""
    tier: str = "B"                       # A|B|C poll cadence
    mode: str = "shadow"                  # shadow|assisted|auto (§4)
    shadow_started_at: Optional[datetime] = None
    shadow_drafts_count: int = 0
    shadow_reviewed_count: int = 0        # operator-reviewed shadow drafts (Y-03)
    poll_interval_s: Optional[int] = None
    high_water_post_id: str = ""          # I-03
    notes: str = ""
    active: bool = True
    consecutive_publish_failures: int = 0  # Y-06


class Post(SQLModel, table=True):
    __tablename__ = "post"
    id: Optional[int] = Field(default=None, primary_key=True)
    x_post_id: str = Field(index=True)
    author_handle: str = Field(index=True)
    text: str = ""
    created_at: Optional[datetime] = None
    url: str = ""
    kind: str = "post"                    # post|reply|quote|retweet
    metrics_json: str = "{}"
    is_own: bool = False
    media: bool = False
    lang: str = "en"
    parent_x_id: str = ""
    fetched_at: datetime = Field(default_factory=utcnow)
    raw_html_path: str = ""


class Draft(SQLModel, table=True):
    __tablename__ = "draft"
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str = "reply"                   # reply|post|thread
    parent_post_id: Optional[int] = Field(default=None, foreign_key="post.id")
    account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    candidates_json: str = "[]"
    critic_json: str = "[]"
    chosen_index: int = 0
    final_text: str = ""
    relevance: float = 0.0
    status: str = "queued"                # queued|shadow|approved|sent|dismissed|expired|no_angle
    mode_at_creation: str = "assisted"
    would_have_sent_at: Optional[datetime] = None
    shadow_verdict: Optional[str] = None  # retrospective would-approve (U-03)
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: Optional[datetime] = None


class Authorization(SQLModel, table=True):
    """ActionAuthorization — required typed param on every write (Y-01)."""
    __tablename__ = "authorization"
    id: Optional[int] = Field(default=None, primary_key=True)
    draft_id: int = Field(foreign_key="draft.id", index=True)
    issuer: str = "human"                 # human|policy
    mode: str = "assisted"
    reasons_json: str = "[]"
    issued_at: datetime = Field(default_factory=utcnow)
    expires_at: Optional[datetime] = None
    consumed_at: Optional[datetime] = None  # single-use


class Action(SQLModel, table=True):
    """The intent record (Q-02): written BEFORE execution, then updated."""
    __tablename__ = "action"
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str                             # read_user|read_post|publish|reply|thread|metrics|presence|canary|login_check|delete
    payload_json: str = "{}"
    idempotency_key: str = Field(index=True)
    authorization_id: Optional[int] = Field(default=None, foreign_key="authorization.id")
    issuer: str = ""                      # denormalised for audit (Q-04)
    target: str = ""
    priority: int = 5
    attempts: int = 0
    state: str = "pending"                # pending|running|done|failed|reconciled|abandoned
    created_at: datetime = Field(default_factory=utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    outcome: str = ""
    error: str = ""
    screenshot_path: str = ""
    x_post_id: str = ""


class QueuedPost(SQLModel, table=True):
    __tablename__ = "queued_post"
    id: Optional[int] = Field(default=None, primary_key=True)
    draft_id: Optional[int] = Field(default=None, foreign_key="draft.id")
    text: str = ""
    category: str = ""
    slot_id: Optional[int] = None
    scheduled_for: Optional[datetime] = None
    status: str = "queued"                # queued|sent|skipped
    evergreen: bool = False
    min_repeat_days: int = 45
    last_posted_at: Optional[datetime] = None
    order_index: int = 0


class ScheduleSlot(SQLModel, table=True):
    __tablename__ = "schedule_slot"
    id: Optional[int] = Field(default=None, primary_key=True)
    weekday: int = 0                      # 0=Mon
    hour: int = 9
    minute: int = 0
    category: str = ""
    active: bool = True


class StyleSample(SQLModel, table=True):
    __tablename__ = "style_sample"
    id: Optional[int] = Field(default=None, primary_key=True)
    text: str = ""
    created_at: Optional[datetime] = None
    metrics_json: str = "{}"
    embedding: Optional[bytes] = None     # blob, brute-force cosine (D-01)
    source: str = "archive"               # archive|edit|reply
    weight: float = 1.0                   # edits promoted higher (L-02)


class Feedback(SQLModel, table=True):
    __tablename__ = "feedback"
    id: Optional[int] = Field(default=None, primary_key=True)
    draft_id: Optional[int] = Field(default=None, foreign_key="draft.id")
    action: str = ""                      # approve|edit|dismiss|shadow_judge
    original_text: str = ""
    final_text: str = ""
    reason: str = ""
    prompt_json: str = "{}"               # for DPO/SFT export (L-03)
    chosen_text: str = ""
    rejected_json: str = "[]"
    created_at: datetime = Field(default_factory=utcnow)


class MetricSample(SQLModel, table=True):
    __tablename__ = "metric_sample"
    id: Optional[int] = Field(default=None, primary_key=True)
    x_post_id: str = Field(index=True)
    at: datetime = Field(default_factory=utcnow)
    likes: int = 0
    reposts: int = 0
    replies: int = 0
    views: int = 0


class SavedSearch(SQLModel, table=True):
    __tablename__ = "saved_search"
    id: Optional[int] = Field(default=None, primary_key=True)
    query: str = ""
    interval_s: int = 3600
    last_run_at: Optional[datetime] = None
    active: bool = True


class Person(SQLModel, table=True):
    __tablename__ = "person"
    handle: str = Field(primary_key=True)
    first_seen: datetime = Field(default_factory=utcnow)
    engagements: int = 0
    last_engaged_at: Optional[datetime] = None
    avg_reply_likes: float = 0.0
    notes: str = ""


class Setting(SQLModel, table=True):
    __tablename__ = "setting"
    key: str = Field(primary_key=True)
    value_json: str = "null"


class GovernorDay(SQLModel, table=True):
    __tablename__ = "governor_day"
    date: str = Field(primary_key=True)   # YYYY-MM-DD local
    replies_assisted: int = 0
    replies_auto: int = 0
    posts: int = 0
    threads: int = 0
    reads: int = 0                        # read budget (I-06)
    last_write_at: Optional[datetime] = None
    kill_switch: bool = False
    panic_at: Optional[datetime] = None
    quiet_drift_min: int = 0              # frozen daily drift (S-03)
    no_auto_today: bool = False           # weekly-shape rest day (S-04)


class Health(SQLModel, table=True):
    __tablename__ = "health"
    id: Optional[int] = Field(default=None, primary_key=True)
    at: datetime = Field(default_factory=utcnow)
    session_ok: bool = True
    canary_ok: bool = True
    worker_ok: bool = True
    latency_ms: int = 0
    note: str = ""


class Heartbeat(SQLModel, table=True):
    """Per-process heartbeat (O-02)."""
    __tablename__ = "heartbeat"
    process: str = Field(primary_key=True)  # api|worker|browser
    at: datetime = Field(default_factory=utcnow)


class DiscoveryItem(SQLModel, table=True):
    __tablename__ = "discovery_item"
    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: Optional[int] = Field(default=None, foreign_key="post.id")
    source: str = "search"                # search|presence
    query: str = ""
    relevance: float = 0.0
    status: str = "new"                   # new|promoted|dismissed
    created_at: datetime = Field(default_factory=utcnow)


class Notification(SQLModel, table=True):
    __tablename__ = "notification"
    id: Optional[int] = Field(default=None, primary_key=True)
    x_post_id: str = ""
    author_handle: str = ""
    text: str = ""
    kind: str = "mention"                 # mention|reply
    created_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=utcnow)


class IdeaNote(SQLModel, table=True):
    __tablename__ = "idea_note"
    id: Optional[int] = Field(default=None, primary_key=True)
    text: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    promoted: bool = False
