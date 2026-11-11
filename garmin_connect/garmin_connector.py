from garminconnect import Garmin
import argparse
import getpass
import json
from datetime import datetime, timedelta

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

    # --- Daily summary for today: stress, HR min/max, body battery ---
    summary = _safe_call(garmin.get_user_summary, date) or {}
    stress_level_today = summary.get("averageStressLevel")
    heart_rate_min_daily = summary.get("minHeartRate")
    heart_rate_max_daily = summary.get("maxHeartRate")
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

    # --- Mean heart rate: Garmin has no daily mean, so average the samples ---
    heart_rates = _safe_call(garmin.get_heart_rates, date) or {}
    hr_samples = heart_rates.get("heartRateValues") or []
    heart_rate_mean_daily = _mean([s[1] for s in hr_samples if len(s) > 1])

    # --- Sleep ---
    sleep = _safe_call(garmin.get_sleep_data, date) or {}
    sleep_score_today = (
        sleep.get("dailySleepDTO", {}).get("sleepScores", {}).get("overall", {}).get("value")
    )
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
        "heart_rate_min_daily": heart_rate_min_daily,
        "heart_rate_max_daily": heart_rate_max_daily,
        "heart_rate_mean_daily": heart_rate_mean_daily,
        "sleep_score_today": sleep_score_today,
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
