import json
import re

DEFAULT_ROOM_NUMBERS = ['309', '310', '311']
ROOM_NUMBER_PATTERN = re.compile(r'^[A-Za-z0-9\s-]{1,20}$')
MAX_ROOM_COUNT = 12
MAX_SERIALIZED_LENGTH = 95


def _to_iterable(raw_value):
    """Convert assorted raw values into a list of candidate strings."""
    if raw_value is None:
        return []
    if isinstance(raw_value, (list, tuple, set)):
        return list(raw_value)
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return parsed
        except ValueError:
            pass
        return stripped.split(',')
    return [raw_value]


def load_room_numbers(raw_value, fallback=None, strict=False):
    """Return a cleaned list of room numbers from raw input.

    When strict=True, invalid tokens raise ValueError; otherwise they are skipped.
    """

    fallback = list(fallback) if fallback else []
    candidates = _to_iterable(raw_value)
    cleaned = []
    seen = set()

    for item in candidates:
        candidate = str(item).strip()
        if not candidate:
            continue
        if not ROOM_NUMBER_PATTERN.fullmatch(candidate):
            if strict:
                raise ValueError('Room numbers may contain letters, numbers, spaces, or hyphens (max 20 characters).')
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(candidate)

    if not cleaned:
        return fallback.copy()
    if len(cleaned) > MAX_ROOM_COUNT:
        raise ValueError(f'A maximum of {MAX_ROOM_COUNT} room numbers may be stored.')
    return cleaned


def normalize_room_numbers_payload(raw_value):
    """Validate room numbers input and return (list, serialized_string)."""

    rooms = load_room_numbers(raw_value, fallback=[], strict=True)
    if not rooms:
        raise ValueError('Please provide at least one valid room number.')
    serialized = ','.join(rooms)
    if len(serialized) > MAX_SERIALIZED_LENGTH:
        raise ValueError('Room list is too long. Remove a few entries and try again.')
    return rooms, serialized or ''
