from datetime import datetime, timezone, timedelta


EST_OFFSET = timedelta(hours=-5)

PEAK_SLOTS = [8, 12, 17]


def get_current_est_hour() -> int:
    """Current EST hour return karta hai."""
    now_utc = datetime.now(timezone.utc)
    now_est = now_utc + EST_OFFSET
    return now_est.hour


def get_next_peak_slot(current_hour: int = None) -> int:
    """Next peak traffic slot return karta hai EST me."""
    if current_hour is None:
        current_hour = get_current_est_hour()

    for slot in PEAK_SLOTS:
        if slot > current_hour:
            return slot

    return PEAK_SLOTS[0]


def should_dispatch_immediately(virality_score: int, topic_type_hint: str = "") -> bool:
    """
    Breaking news ya ultra-high virality content ke liye immediate dispatch decide karta hai.
    """
    breaking_keywords = ["breaking", "just in", "alert", "crash", "urgent", "live", "now"]
    is_breaking = any(kw in topic_type_hint.lower() for kw in breaking_keywords)

    if is_breaking:
        return True
    if virality_score >= 9:
        return True
    return False


def get_est_time_info() -> dict:
    """Current EST time details return karta hai."""
    now_utc = datetime.now(timezone.utc)
    now_est = now_utc + EST_OFFSET
    return {
        "utc_time": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "est_time": now_est.strftime("%Y-%m-%d %H:%M:%S EST"),
        "current_hour_est": now_est.hour,
        "next_peak_slot": get_next_peak_slot(now_est.hour),
        "peak_slots": PEAK_SLOTS
    }
