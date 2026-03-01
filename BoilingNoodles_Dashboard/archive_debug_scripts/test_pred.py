import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta
import holidays

def is_holiday_tw(dt, tw_holidays):
    if dt.weekday() >= 5: return True
    if dt in tw_holidays: return True
    return False

def is_cny_closed_day(dt, tw_holidays):
    name = tw_holidays.get(dt)
    if name and ("Chinese New Year's Eve" in name or "Chinese New Year" in name) and "observed" not in name:
        return True
    return False

tw_holidays = holidays.country_holidays('TW', years=[2026])
tw_holidays.update(holidays.country_holidays('TW', years=2027))

start_dt = date(2027, 2, 1)
end_dt = start_dt + relativedelta(months=1) - pd.Timedelta(days=1)
dates_in_month = pd.date_range(start_dt, end_dt).date

wd_count = 0
hol_count = 0
skip_count = 0

for d in dates_in_month:
    if is_cny_closed_day(d, tw_holidays):
        skip_count += 1
        continue
    elif is_holiday_tw(d, tw_holidays):
        hol_count += 1
    else:
        wd_count += 1

print(f"Weekdays: {wd_count}, Holidays: {hol_count}, Skipped: {skip_count}")
