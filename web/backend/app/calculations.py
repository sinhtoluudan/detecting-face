"""Pure attendance arithmetic: VN dates, overnight shifts and actual break overlap."""
from datetime import date, datetime, time, timedelta, timezone
from .config import TZ

def parse_dt(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value

def bounds(day, shift):
    day = date.fromisoformat(day) if isinstance(day, str) else day
    start = datetime.combine(day, time.fromisoformat(shift['start']), TZ)
    end = datetime.combine(day, time.fromisoformat(shift['end']), TZ)
    if end <= start:
        end += timedelta(days=1)
    breaks = None
    if shift.get('break_start'):
        bs = datetime.combine(day, time.fromisoformat(shift['break_start']), TZ)
        if bs < start:
            bs += timedelta(days=1)
        be = datetime.combine(day, time.fromisoformat(shift['break_end']), TZ)
        if be <= bs:
            be += timedelta(days=1)
        breaks = (bs, be)
    return start, end, breaks

def overlap(a, b, c, d):
    return max(0, (min(b, d)-max(a, c)).total_seconds()/60)

def worked_minutes(a, b, start, end, breaks):
    if not a or not b:
        return 0
    left, right = max(a, start), min(b, end)
    if right <= left:
        return 0
    minutes = (right-left).total_seconds()/60
    if breaks:
        minutes -= overlap(left, right, *breaks)
    return max(0, minutes)

def calculate(assignment, attendance, approved, now):
    start, end, breaks = bounds(assignment['date'], assignment['shift'])
    planned = worked_minutes(start, end, start, end, breaks)
    a, b = parse_dt((attendance or {}).get('check_in')), parse_dt((attendance or {}).get('check_out'))
    worked = worked_minutes(a, b, start, end, breaks)
    leaves = [r for r in approved if r['type']=='leave']
    paid_leave = min(max(0, planned-worked), sum(r.get('leave_hours',8)*60 for r in leaves if r.get('paid')))
    leave = min(max(0, planned-worked), sum(r.get('leave_hours',8)*60 for r in leaves))
    grace = assignment['shift'].get('grace_minutes', 5)
    late = max(0, int((a-start).total_seconds()/60)) if a else 0
    late = late if late > grace else 0
    early = max(0, int((end-b).total_seconds()/60)) if b else 0
    overtime = 0
    if a and b:
        for r in approved:
            if r['type'] == 'overtime':
                rs, re = parse_dt(r['check_in']), parse_dt(r['check_out'])
                lo, hi = max(a,rs), min(b,re)
                if hi > lo:
                    overtime += max(0, (hi-lo).total_seconds()/60-overlap(lo,hi,start,end))
    if a and not b and (attendance or {}).get('single_scan'):
        status = 'late' if late else 'present'
    elif a and not b:
        status = 'missing_out' if now > end else 'working'
    elif a and b:
        status = 'late' if late else ('early' if early else 'present')
    elif leave >= planned:
        status = 'leave'
    elif now >= end:
        status = 'absent'
    else:
        status = 'scheduled'
    # Partial leave cannot prove at which time the person was excused; flag for HR.
    needs_review = bool((leaves and (late or early)) or status == 'missing_out')
    return {'status': status, 'planned_minutes': round(planned), 'worked_minutes': round(worked),
        'paid_leave_minutes': round(paid_leave), 'leave_minutes': round(leave),
        'credited_minutes': round(min(planned, worked+paid_leave)),
        'late_minutes': late, 'early_minutes': early, 'overtime_minutes': round(overtime),
        'needs_review': needs_review, 'check_in': a, 'check_out': b}
