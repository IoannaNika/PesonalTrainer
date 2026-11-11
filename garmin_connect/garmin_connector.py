from garminconnect import Garmin
import argparse
import getpass
import json
from datetime import datetime, timedelta

def build_workout(garmin): 
    # TODO: Implement the logic to build a workout based on the user's current condition and historical data
    raise NotImplementedError

def connect_to_garmin(email, password):
    garmin = Garmin(email, password)
    try:
        garmin.login()
        print("Connected to Garmin Connect successfully!")
        return garmin
    except Exception as e:  
        print(f"Failed to connect to Garmin Connect: {e}")
        return None

def get_current_date():
    # format: YYYY-MM-DD
    return datetime.now().strftime("%Y-%m-%d")

def get_best_activity_records(garmin):
    # TODO: Implement the logic to fetch best activity records for the user
    raise NotImplementedError

def get_historical_workout_data_past_month(garmin):
    # TODO: Implement the logic to fetch historical workout data for the user between start_date and end_date
    raise NotImplementedError


def _safe_call(func, *args, **kwargs):
    """Call a Garmin API method, returning None instead of crashing if the data is unavailable."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"Warning: {getattr(func, '__name__', func)} failed: {e}")
        return None


def _mean(values):
    values = [v for v in values if v is not None and v >= 0]  # Garmin uses -1/-2 for "no data"
    return round(sum(values) / len(values), 1) if values else None


def _shift_date(date, days):
    return (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")


def get_user_current_condition(garmin, date):
    week_start = _shift_date(date, 6)    # 7 days including today
    month_start = _shift_date(date, 29)  # 30 days including today

    # --- Daily summary for today: stress so far, body battery (and resting HR fallback) ---
    summary = _safe_call(garmin.get_user_summary, date) or {}
    stress_level_today = summary.get("averageStressLevel")  # partial day if run before evening
    body_battery = summary.get("bodyBatteryMostRecentValue")

    # --- Stress averages over the past week / month (one call covers both) ---
    month_summaries = _safe_call(garmin.get_daily_summaries, month_start, date) or {}
    month_days = month_summaries.get("data", []) if isinstance(month_summaries, dict) else []
    # v2 daily summaries nest stress as {"stress": {"avgLevel": ...}}
    def _day_stress(d):
        return (d.get("stress") or {}).get("avgLevel")
    stress_level_last_month = _mean([_day_stress(d) for d in month_days])
    stress_level_last_week = _mean(
        [_day_stress(d) for d in month_days if d.get("calendarDate", "") >= week_start]
    )

    # --- Resting HR vs. the previous 7 days (a few bpm above baseline = fatigue/illness) ---
    rhr_rows = _safe_call(garmin.get_rhr_daily, _shift_date(date, 7), date) or []
    rhr_by_day = {r.get("calendarDate"): r.get("value") for r in rhr_rows}
    resting_hr_today = rhr_by_day.get(date) or summary.get("restingHeartRate")
    resting_hr_7d_avg = _mean([v for d, v in rhr_by_day.items() if d != date])
    resting_hr_vs_baseline = (
        round(resting_hr_today - resting_hr_7d_avg, 1)
        if resting_hr_today is not None and resting_hr_7d_avg is not None else None
    )

    # --- HRV: last night vs. 7-day average and personal baseline range ---
    hrv = _safe_call(garmin.get_hrv_data, date) or {}
    hrv_summary = hrv.get("hrvSummary") or {}
    hrv_baseline = hrv_summary.get("baseline") or {}
    hrv_last_night = hrv_summary.get("lastNightAvg")
    hrv_weekly_avg = hrv_summary.get("weeklyAvg")
    hrv_data = {
        "last_night_avg": hrv_last_night,
        "weekly_avg": hrv_weekly_avg,
        "last_night_vs_weekly": (
            round(hrv_last_night - hrv_weekly_avg, 1)
            if hrv_last_night is not None and hrv_weekly_avg is not None else None
        ),
        "baseline_balanced_low": hrv_baseline.get("balancedLow"),
        "baseline_balanced_upper": hrv_baseline.get("balancedUpper"),
        "status": hrv_summary.get("status"),  # e.g. BALANCED / UNBALANCED / LOW
    } if hrv_summary else None

    # --- Garmin Training Readiness: list of snapshots, use the latest one ---
    readiness_list = _safe_call(garmin.get_training_readiness, date) or []
    if isinstance(readiness_list, dict):
        readiness_list = [readiness_list]
    readiness = max(readiness_list, key=lambda r: r.get("timestamp") or "") if readiness_list else {}
    recovery_min = readiness.get("recoveryTime")
    if readiness.get("recoveryTimeChangePhrase") == "REACHED_ZERO":
        recovery_min = 0  # fully recovered; Garmin keeps the stale number otherwise
    training_readiness = {
        "score": readiness.get("score"),  # 0-100
        "level": readiness.get("level"),
        "feedback": readiness.get("feedbackShort"),
        "recovery_time_hours": round(recovery_min / 60, 1) if recovery_min is not None else None,
        "factors": {  # per-factor rating in %, higher = better (low ones explain a low score)
            "sleep": readiness.get("sleepScoreFactorPercent"),
            "recovery_time": readiness.get("recoveryTimeFactorPercent"),
            "acute_chronic_load": readiness.get("acwrFactorPercent"),
            "hrv": readiness.get("hrvFactorPercent"),
            "stress_history": readiness.get("stressHistoryFactorPercent"),
        },
    } if readiness else None

    # --- Sleep ---
    sleep = _safe_call(garmin.get_sleep_data, date) or {}
    sleep_dto = sleep.get("dailySleepDTO") or {}
    sleep_score_today = (
        (sleep_dto.get("sleepScores") or {}).get("overall", {}).get("value")
    )
    sleep_seconds = sleep_dto.get("sleepTimeSeconds")
    sleep_duration_hours = round(sleep_seconds / 3600, 2) if sleep_seconds else None
    sleep_week = _safe_call(garmin.get_sleep_daily, week_start, date) or []
    sleep_score_last_week = _mean(
        [(row.get("values") or {}).get("sleepScore") for row in sleep_week]
    )

    # --- VO2 max (latest known value as of date) ---
    max_metrics = _safe_call(garmin.get_max_metrics_latest, date) or {}
    generic = max_metrics.get("generic") or {}
    current_vo2max = generic.get("vo2MaxPreciseValue") or generic.get("vo2MaxValue")

    # --- Weight: most recent weigh-in in the last year (Garmin stores grams) ---
    body = _safe_call(garmin.get_body_composition, _shift_date(date, 364), date) or {}
    weigh_ins = [w for w in body.get("dateWeightList") or [] if w.get("weight")]
    current_weight = None
    if weigh_ins:
        latest = max(weigh_ins, key=lambda w: w.get("date") or 0)
        current_weight = round(latest["weight"] / 1000, 1)  # kg

    # --- Most recent workout ---
    last_activity = _safe_call(garmin.get_last_activity) or {}
    most_recent_workout_date = last_activity.get("startTimeLocal")
    most_recent_workout_type = (last_activity.get("activityType") or {}).get("typeKey")
    most_recent_workout_intensity = {
        "aerobic_training_effect": last_activity.get("aerobicTrainingEffect"),
        "anaerobic_training_effect": last_activity.get("anaerobicTrainingEffect"),
        "training_effect_label": last_activity.get("trainingEffectLabel"),
        # training effect is only reported for some activity types (e.g. not strength)
        "moderate_intensity_minutes": last_activity.get("moderateIntensityMinutes"),
        "vigorous_intensity_minutes": last_activity.get("vigorousIntensityMinutes"),
        "hr_time_in_zones_min": {
            f"zone_{i}": round(last_activity[f"hrTimeInZone_{i}"] / 60, 1)
            for i in range(1, 6) if last_activity.get(f"hrTimeInZone_{i}") is not None
        },
        "body_battery_change": last_activity.get("differenceBodyBattery"),
        "total_sets": last_activity.get("totalSets"),
        "average_hr": last_activity.get("averageHR"),
        "max_hr": last_activity.get("maxHR"),
        "duration_min": round(last_activity["duration"] / 60, 1) if last_activity.get("duration") else None,
    } if last_activity else None

    json_data = {
        "stress_level_today": stress_level_today,
        "stress_level_last_week": stress_level_last_week,
        "stress_level_last_month": stress_level_last_month,
        "body_battery": body_battery,
        "resting_hr_today": resting_hr_today,
        "resting_hr_7d_avg": resting_hr_7d_avg,
        "resting_hr_vs_baseline": resting_hr_vs_baseline,
        "hrv": hrv_data,
        "training_readiness": training_readiness,
        "sleep_score_today": sleep_score_today,
        "sleep_duration_hours": sleep_duration_hours,
        "sleep_score_last_week": sleep_score_last_week,
        "current_vo2max": current_vo2max,
        "current_weight": current_weight,
        "most_recent_workout_date": most_recent_workout_date,
        "most_recent_workout_type": most_recent_workout_type,
        "most_recent_workout_intensity": most_recent_workout_intensity
    }

    return json_data


def main():
    parser = argparse.ArgumentParser(description="Connect to Garmin Connect")
    parser.add_argument("--email", required=True, help="Garmin Connect email")
    parser.add_argument('--prompt-password', action='store_true', help="Prompt securely for the password")
    args = parser.parse_args()

    password = None
    if args.prompt_password:
        password = getpass.getpass("Enter password: ")
    else:
        raise ValueError("No password provided.")

    garmin = connect_to_garmin(args.email, password)
    if garmin is None:
        return

    current_date = get_current_date()
    condition = get_user_current_condition(garmin, current_date)
    print(json.dumps(condition, indent=2))

if __name__ == "__main__":
    main()
