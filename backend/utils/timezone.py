"""
Timezone utility for Philippine Standard Time (PST/Asia/Manila)
All datetime operations should use functions from this module to ensure
consistent timezone handling across the application.
"""
from datetime import datetime
import pytz

# Philippine Standard Time timezone (UTC+8)
PST = pytz.timezone('Asia/Manila')

def get_pst_now():
    """
    Get current datetime in Philippine Standard Time (PST/Asia/Manila).
    
    Returns:
        datetime: Current datetime with PST timezone awareness
    """
    return datetime.now(PST)

def get_pst_utcnow():
    """
    Get current UTC datetime and convert to PST.
    This is useful for database operations that expect UTC but need PST.
    
    Returns:
        datetime: Current datetime in PST timezone
    """
    utc_now = datetime.utcnow()
    utc_tz = pytz.UTC
    utc_now = utc_tz.localize(utc_now)
    return utc_now.astimezone(PST)

def to_pst(dt):
    """
    Convert a datetime to Philippine Standard Time.
    If datetime is naive (no timezone), assumes it's UTC.
    
    Args:
        dt: datetime object (naive or timezone-aware)
    
    Returns:
        datetime: datetime in PST timezone
    """
    if dt is None:
        return None
    
    if dt.tzinfo is None:
        # Assume naive datetime is UTC
        utc_tz = pytz.UTC
        dt = utc_tz.localize(dt)
    
    return dt.astimezone(PST)

def pst_now_naive():
    """
    Get current PST datetime as naive (no timezone info).
    Useful for database columns that don't support timezone-aware datetimes.
    
    Returns:
        datetime: Current datetime in PST, but naive (no timezone info)
    """
    return get_pst_now().replace(tzinfo=None)

