import re
from datetime import datetime, date, timedelta

DAY_CODE_SEQUENCE = ['M', 'T', 'W', 'Th', 'F', 'S', 'Su']
TIME_RANGE_PATTERN = re.compile(r'(\d{1,2}:\d{2}\s*(?:[AaPp][Mm])?)\s*-\s*(\d{1,2}:\d{2}\s*(?:[AaPp][Mm])?)')


def get_day_code_for_date(target_date=None):
    target = target_date or datetime.now().date()
    idx = target.weekday()
    return DAY_CODE_SEQUENCE[idx] if 0 <= idx < len(DAY_CODE_SEQUENCE) else None


def _parse_time_token(value):
    text = (value or '').strip()
    if not text:
        return None
    upper_text = text.upper()
    if upper_text.endswith(('AM', 'PM')) and ' ' not in upper_text[-3:]:
        upper_text = upper_text[:-2].strip() + ' ' + upper_text[-2:]
    for fmt in ('%I:%M %p', '%H:%M'):
        try:
            return datetime.strptime(upper_text, fmt).time()
        except ValueError:
            continue
    return None


def _split_schedule_days(days_text):
    cleaned = re.sub(r'[^A-Za-z]', '', (days_text or '').strip())
    if not cleaned:
        return DAY_CODE_SEQUENCE[:]
    tokens = []
    idx = 0
    while idx < len(cleaned):
        two_char = cleaned[idx:idx + 2]
        if two_char.lower() in {'th', 'su'}:
            tokens.append(two_char.title())
            idx += 2
        else:
            tokens.append(cleaned[idx].upper())
            idx += 1
    normalized = []
    for token in tokens:
        if token in DAY_CODE_SEQUENCE:
            normalized.append(token)
        elif token.upper() in {'M', 'T', 'W', 'F', 'S'}:
            normalized.append(token.upper())
    return normalized or DAY_CODE_SEQUENCE[:]


def _split_day_and_time(chunk):
    chunk = (chunk or '').strip()
    if not chunk:
        return '', ''
    idx = 0
    while idx < len(chunk) and chunk[idx].isalpha():
        idx += 1
    days_part = chunk[:idx].strip()
    time_part = chunk[idx:].strip()
    return days_part, time_part or chunk


def parse_schedule_slots(schedule_string):
    slots = []
    if not schedule_string:
        return slots

    for raw_slot in schedule_string.split(','):
        chunk = raw_slot.strip()
        if not chunk:
            continue
        days_part, time_part = _split_day_and_time(chunk)
        match = TIME_RANGE_PATTERN.search(time_part)
        if not match:
            continue
        start_token, end_token = match.groups()
        start_time = _parse_time_token(start_token)
        end_time = _parse_time_token(end_token)
        if not start_time or not end_time:
            continue
        days = _split_schedule_days(days_part)
        start_dt = datetime.combine(date.today(), start_time)
        end_dt = datetime.combine(date.today(), end_time)
        is_overnight = False
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)
            is_overnight = True
        duration_minutes = max(1, (end_dt - start_dt).total_seconds() / 60)
        slots.append({
            'days': days,
            'start_time': start_time,
            'end_time': end_time,
            'duration_minutes': duration_minutes,
            'is_overnight': is_overnight,
            'label': chunk,
        })
    return slots


def resolve_schedule_window(schedule_string, target_date=None):
    target_date = target_date or datetime.now().date()
    slots = parse_schedule_slots(schedule_string)
    if not slots:
        return None
    day_code = get_day_code_for_date(target_date)
    selected = None
    if day_code:
        for slot in slots:
            if day_code in slot['days']:
                selected = slot
                break
    if selected is None:
        selected = slots[0]
    start_dt = datetime.combine(target_date, selected['start_time'])
    end_dt = datetime.combine(target_date, selected['end_time'])
    if selected.get('is_overnight') or end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return {
        'start_datetime': start_dt,
        'end_datetime': end_dt,
        'duration_minutes': selected['duration_minutes'],
        'days': selected['days'],
        'label': selected['label'],
    }
