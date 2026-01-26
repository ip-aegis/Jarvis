"""
Apple Health Data Service.

Parses, stores, and retrieves health data from Apple Health exports
and the Health Auto Export iOS app.
"""

import hashlib
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Optional

import structlog
from sqlalchemy import Date, cast, desc, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal


def get_local_today() -> date:
    """Get today's date in the configured local timezone."""
    settings = get_settings()
    return datetime.now(settings.tz).date()


from app.models import (
    HealthBody,
    HealthDailySummary,
    HealthMetric,
    HealthSleep,
    HealthUpload,
    HealthWorkout,
)
from app.schemas.health import (
    DAILY_VALUES,
    BodyHistoryResponse,
    BodyMeasurement,
    DataCollectionStatus,
    DetailedNutritionDay,
    DetailedNutritionResponse,
    HealthDiagnosticsResponse,
    HealthSummaryCard,
    HealthSummaryResponse,
    HealthTrendsResponse,
    HealthUploadResponse,
    HeartRateDataPoint,
    HeartRateResponse,
    HeartRateSummary,
    MetricTypeInfo,
    MicronutrientData,
    MobilityDataPoint,
    MobilityResponse,
    NutritionDay,
    NutritionHistoryResponse,
    SleepHistoryResponse,
    SleepSession,
    SleepStage,
    StepsDataPoint,
    StepsHistoryResponse,
    TrendComparison,
    VitalsDataPoint,
    VitalsResponse,
    WorkoutDetail,
    WorkoutHistoryResponse,
    WorkoutSummary,
)

logger = structlog.get_logger()

# Unit conversion constants (metric to imperial)
KM_TO_MILES = 0.621371
KG_TO_LBS = 2.20462
LBS_TO_KG = 1 / KG_TO_LBS  # 0.453592
CM_TO_INCHES = 0.393701
KMH_TO_MPH = 0.621371
ML_TO_FLOZ = 0.033814


def celsius_to_fahrenheit(c: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return (c * 9 / 5) + 32


# Mapping from Health Auto Export metric names to internal names
METRIC_NAME_MAP = {
    "step_count": "steps",
    "stepCount": "steps",
    "heart_rate": "heart_rate",
    "heartRate": "heart_rate",
    "resting_heart_rate": "resting_heart_rate",
    "restingHeartRate": "resting_heart_rate",
    "heart_rate_variability": "heart_rate_variability",
    "heartRateVariability": "heart_rate_variability",
    "active_energy_burned": "active_energy",
    "activeEnergyBurned": "active_energy",
    "basal_energy_burned": "basal_energy",
    "basalEnergyBurned": "basal_energy",
    "distance_walking_running": "distance",
    "distanceWalkingRunning": "distance",
    "flights_climbed": "flights_climbed",
    "flightsClimbed": "flights_climbed",
    "oxygen_saturation": "blood_oxygen",
    "oxygenSaturation": "blood_oxygen",
    # Body measurements
    "body_mass": "weight",
    "bodyMass": "weight",
    "weight_body_mass": "weight",
    "weightBodyMass": "weight",
    "body_fat_percentage": "body_fat",
    "bodyFatPercentage": "body_fat",
    "body_mass_index": "bmi",
    "bodyMassIndex": "bmi",
    # Nutrition - Macros
    "dietary_energy_consumed": "dietary_energy",
    "dietaryEnergyConsumed": "dietary_energy",
    "dietary_energy": "dietary_energy",
    "dietaryEnergy": "dietary_energy",
    "dietary_protein": "protein",
    "dietaryProtein": "protein",
    "protein": "protein",
    "dietary_carbohydrates": "carbohydrates",
    "dietaryCarbohydrates": "carbohydrates",
    "carbohydrates": "carbohydrates",
    "dietary_fat": "total_fat",
    "dietaryFat": "total_fat",
    "dietary_fat_total": "total_fat",
    "dietaryFatTotal": "total_fat",
    "total_fat": "total_fat",
    "water": "water",
    "dietary_water": "water",
    "dietaryWater": "water",
    "dietary_fiber": "fiber",
    "dietaryFiber": "fiber",
    "dietary_sugar": "sugar",
    "dietarySugar": "sugar",
    # Nutrition - Vitamins
    "dietary_vitamin_a": "vitamin_a",
    "dietaryVitaminA": "vitamin_a",
    "dietary_vitamin_c": "vitamin_c",
    "dietaryVitaminC": "vitamin_c",
    "dietary_vitamin_d": "vitamin_d",
    "dietaryVitaminD": "vitamin_d",
    "dietary_vitamin_e": "vitamin_e",
    "dietaryVitaminE": "vitamin_e",
    "dietary_vitamin_k": "vitamin_k",
    "dietaryVitaminK": "vitamin_k",
    "dietary_vitamin_b6": "vitamin_b6",
    "dietaryVitaminB6": "vitamin_b6",
    "dietary_vitamin_b12": "vitamin_b12",
    "dietaryVitaminB12": "vitamin_b12",
    "dietary_thiamin": "thiamin",
    "dietaryThiamin": "thiamin",
    "dietary_riboflavin": "riboflavin",
    "dietaryRiboflavin": "riboflavin",
    "dietary_niacin": "niacin",
    "dietaryNiacin": "niacin",
    "dietary_folate": "folate",
    "dietaryFolate": "folate",
    "dietary_pantothenic_acid": "pantothenic_acid",
    "dietaryPantothenicAcid": "pantothenic_acid",
    "dietary_biotin": "biotin",
    "dietaryBiotin": "biotin",
    # Nutrition - Minerals
    "dietary_calcium": "calcium",
    "dietaryCalcium": "calcium",
    "dietary_iron": "iron",
    "dietaryIron": "iron",
    "dietary_magnesium": "magnesium",
    "dietaryMagnesium": "magnesium",
    "dietary_phosphorus": "phosphorus",
    "dietaryPhosphorus": "phosphorus",
    "dietary_potassium": "potassium",
    "dietaryPotassium": "potassium",
    "dietary_sodium": "sodium",
    "dietarySodium": "sodium",
    "dietary_zinc": "zinc",
    "dietaryZinc": "zinc",
    "dietary_copper": "copper",
    "dietaryCopper": "copper",
    "dietary_manganese": "manganese",
    "dietaryManganese": "manganese",
    "dietary_selenium": "selenium",
    "dietarySelenium": "selenium",
    "dietary_chromium": "chromium",
    "dietaryChromium": "chromium",
    "dietary_molybdenum": "molybdenum",
    "dietaryMolybdenum": "molybdenum",
    "dietary_iodine": "iodine",
    "dietaryIodine": "iodine",
    # Nutrition - Other
    "dietary_cholesterol": "cholesterol",
    "dietaryCholesterol": "cholesterol",
    "dietary_fat_saturated": "saturated_fat",
    "dietaryFatSaturated": "saturated_fat",
    "dietary_fat_monounsaturated": "monounsaturated_fat",
    "dietaryFatMonounsaturated": "monounsaturated_fat",
    "dietary_fat_polyunsaturated": "polyunsaturated_fat",
    "dietaryFatPolyunsaturated": "polyunsaturated_fat",
    "dietary_caffeine": "caffeine",
    "dietaryCaffeine": "caffeine",
    # Activity
    "apple_exercise_time": "exercise_time",
    "appleExerciseTime": "exercise_time",
    "apple_stand_hour": "stand_hours",
    "appleStandHour": "stand_hours",
    "respiratory_rate": "respiratory_rate",
    "respiratoryRate": "respiratory_rate",
    # Mobility
    "walking_speed": "walking_speed",
    "walkingSpeed": "walking_speed",
    "walking_step_length": "step_length",
    "walkingStepLength": "step_length",
    "vo2_max": "vo2_max",
    "vo2Max": "vo2_max",
    "walking_double_support_percentage": "walking_double_support",
    "walkingDoubleSupportPercentage": "walking_double_support",
    "walking_asymmetry_percentage": "walking_asymmetry",
    "walkingAsymmetryPercentage": "walking_asymmetry",
    "stair_ascent_speed": "stair_speed_up",
    "stairAscentSpeed": "stair_speed_up",
    "stair_descent_speed": "stair_speed_down",
    "stairDescentSpeed": "stair_speed_down",
    # Environment
    "time_in_daylight": "daylight_exposure",
    "timeInDaylight": "daylight_exposure",
    "environmental_audio_exposure": "env_audio_exposure",
    "environmentalAudioExposure": "env_audio_exposure",
    "headphone_audio_exposure": "headphone_audio_exposure",
    "headphoneAudioExposure": "headphone_audio_exposure",
}

# Sleep stage mapping
SLEEP_STAGE_MAP = {
    "inBed": "in_bed",
    "asleep": "asleep",
    "asleepCore": "core",
    "asleepDeep": "deep",
    "asleepREM": "rem",
    "awake": "awake",
}


class HealthService:
    """Service for managing Apple Health data."""

    def __init__(self, db: Session = None):
        self._db = db

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    # =========================================================================
    # Data Ingestion
    # =========================================================================

    def _update_heartbeat(self, upload: HealthUpload, records_processed: int) -> None:
        """Update upload heartbeat and progress to indicate active processing."""
        upload.last_heartbeat = datetime.utcnow()
        upload.records_processed = records_processed
        self.db.commit()

    def process_webhook_payload(self, payload: dict[str, Any]) -> HealthUploadResponse:
        """
        Process incoming webhook payload from Health Auto Export app.

        Args:
            payload: JSON payload from the app

        Returns:
            HealthUploadResponse with processing results
        """
        start_time = datetime.utcnow()
        upload_id = str(uuid.uuid4())

        # Create upload record
        upload = HealthUpload(
            upload_id=uuid.UUID(upload_id),
            source="webhook",
            status="processing",
            started_at=start_time,
            last_heartbeat=start_time,  # Initial heartbeat
            created_at=start_time,
        )
        self.db.add(upload)
        self.db.commit()

        # Heartbeat update interval (every 1000 records or 30 seconds)
        HEARTBEAT_RECORD_INTERVAL = 1000
        last_heartbeat_records = 0

        try:
            records_processed = 0
            records_inserted = 0
            records_duplicate = 0
            data_dates: list[datetime] = []

            data = payload.get("data", {})

            # Process metrics
            metrics = data.get("metrics", [])
            for metric in metrics:
                metric_name = metric.get("name", "")
                metric_data = metric.get("data", [])
                metric_units = metric.get("units", "")

                for item in metric_data:
                    records_processed += 1
                    result = self._process_metric(metric_name, item, metric_units)
                    if result == "inserted":
                        records_inserted += 1
                        if "date" in item:
                            data_dates.append(self._parse_date(item["date"]))
                    elif result == "duplicate":
                        records_duplicate += 1

                    # Periodic heartbeat update
                    if records_processed - last_heartbeat_records >= HEARTBEAT_RECORD_INTERVAL:
                        self._update_heartbeat(upload, records_processed)
                        last_heartbeat_records = records_processed

            # Process workouts
            workouts = data.get("workouts", [])
            for workout in workouts:
                records_processed += 1
                result = self._process_workout(workout)
                if result == "inserted":
                    records_inserted += 1
                    if "start" in workout:
                        data_dates.append(self._parse_date(workout["start"]))
                elif result == "duplicate":
                    records_duplicate += 1

                # Periodic heartbeat update
                if records_processed - last_heartbeat_records >= HEARTBEAT_RECORD_INTERVAL:
                    self._update_heartbeat(upload, records_processed)
                    last_heartbeat_records = records_processed

            # Process sleep
            sleep_data = data.get("sleepAnalysis", [])
            for sleep in sleep_data:
                records_processed += 1
                result = self._process_sleep(sleep)
                if result == "inserted":
                    records_inserted += 1
                    if "startDate" in sleep:
                        data_dates.append(self._parse_date(sleep["startDate"]))
                elif result == "duplicate":
                    records_duplicate += 1

                # Periodic heartbeat update
                if records_processed - last_heartbeat_records >= HEARTBEAT_RECORD_INTERVAL:
                    self._update_heartbeat(upload, records_processed)
                    last_heartbeat_records = records_processed

            # Update upload record
            upload.status = "completed"
            upload.completed_at = datetime.utcnow()
            upload.records_processed = records_processed
            upload.records_inserted = records_inserted
            upload.records_duplicate = records_duplicate

            if data_dates:
                upload.data_start_date = min(data_dates)
                upload.data_end_date = max(data_dates)

            self.db.commit()

            # Update daily summaries for affected dates
            if data_dates:
                unique_dates = set(d.date() for d in data_dates if d)
                for summary_date in unique_dates:
                    self._update_daily_summary(summary_date)

            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            logger.info(
                "health_webhook_processed",
                upload_id=upload_id,
                records_processed=records_processed,
                records_inserted=records_inserted,
                records_duplicate=records_duplicate,
                processing_time_ms=processing_time,
            )

            return HealthUploadResponse(
                upload_id=upload_id,
                status="completed",
                records_processed=records_processed,
                records_inserted=records_inserted,
                records_duplicate=records_duplicate,
                data_start_date=upload.data_start_date,
                data_end_date=upload.data_end_date,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            upload.status = "failed"
            upload.error_message = str(e)
            upload.completed_at = datetime.utcnow()
            self.db.commit()

            logger.error("health_webhook_failed", upload_id=upload_id, error=str(e))
            raise

    def _process_metric(self, metric_name: str, data: dict, units: str) -> str:
        """Process a single metric data point."""
        # Normalize metric name
        normalized_name = METRIC_NAME_MAP.get(metric_name, metric_name)

        # Parse date
        date_str = data.get("date", data.get("startDate"))
        if not date_str:
            return "skipped"

        timestamp = self._parse_date(date_str)
        if not timestamp:
            return "skipped"

        # Get value
        value = data.get("qty", data.get("value", data.get("avg")))
        if value is None:
            return "skipped"

        try:
            value = float(value)
        except (ValueError, TypeError):
            return "skipped"

        # Get source info
        source_name = data.get("source", data.get("sourceName"))
        device = data.get("device", data.get("deviceName"))

        # Get date range for aggregated metrics
        start_date = None
        end_date = None
        if "startDate" in data and "endDate" in data:
            start_date = self._parse_date(data["startDate"])
            end_date = self._parse_date(data["endDate"])

        # Create hash for deduplication
        hash_input = f"{normalized_name}:{timestamp.isoformat()}:{value}:{source_name or ''}"
        record_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        # Check for duplicate
        existing = (
            self.db.query(HealthMetric).filter(HealthMetric.record_hash == record_hash).first()
        )
        if existing:
            return "duplicate"

        # Handle body measurements separately
        if normalized_name in ("weight", "body_fat", "bmi"):
            return self._process_body_metric(
                normalized_name, timestamp, value, units, source_name, device
            )

        # Create metric record
        metric = HealthMetric(
            timestamp=timestamp,
            metric_type=normalized_name,
            source_name=source_name,
            device=device,
            value=value,
            unit=units,
            start_date=start_date,
            end_date=end_date,
            record_hash=record_hash,
            created_at=datetime.utcnow(),
        )
        self.db.add(metric)
        self.db.commit()

        return "inserted"

    def _process_body_metric(
        self,
        metric_type: str,
        timestamp: datetime,
        value: float,
        units: str,
        source_name: Optional[str],
        device: Optional[str],
    ) -> str:
        """Process body measurement metrics into the body table.

        Weight is always stored in kilograms for consistency.
        If the input is in pounds, it is converted to kilograms.
        """
        # Normalize weight to kilograms if provided in pounds
        normalized_value = value
        if metric_type == "weight":
            units_lower = (units or "").lower().strip()
            # Check for pound units (Apple Health uses "lb" or "lbs")
            if units_lower in ("lb", "lbs", "pound", "pounds"):
                normalized_value = value * LBS_TO_KG
                logger.debug(
                    "weight_converted_to_kg",
                    original_value=value,
                    original_unit=units,
                    converted_value=normalized_value,
                )

        # Create hash for deduplication (use normalized value)
        hash_input = f"body:{timestamp.isoformat()}:{metric_type}:{normalized_value:.4f}"
        record_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        existing = self.db.query(HealthBody).filter(HealthBody.record_hash == record_hash).first()
        if existing:
            return "duplicate"

        # Try to find existing measurement at same timestamp
        body = self.db.query(HealthBody).filter(HealthBody.timestamp == timestamp).first()

        if body:
            # Update existing record
            if metric_type == "weight":
                body.weight = normalized_value
            elif metric_type == "body_fat":
                body.body_fat_percentage = value
            elif metric_type == "bmi":
                body.body_mass_index = value
            body.record_hash = record_hash
        else:
            # Create new record
            body = HealthBody(
                measurement_id=uuid.uuid4(),
                timestamp=timestamp,
                source_name=source_name,
                device=device,
                record_hash=record_hash,
                created_at=datetime.utcnow(),
            )
            if metric_type == "weight":
                body.weight = normalized_value
            elif metric_type == "body_fat":
                body.body_fat_percentage = value
            elif metric_type == "bmi":
                body.body_mass_index = value
            self.db.add(body)

        self.db.commit()
        return "inserted"

    def _process_workout(self, workout: dict) -> str:
        """Process a workout record."""
        workout_type = workout.get("name", workout.get("workoutActivityType", "Unknown"))

        start_str = workout.get("start", workout.get("startDate"))
        end_str = workout.get("end", workout.get("endDate"))

        if not start_str or not end_str:
            return "skipped"

        start_date = self._parse_date(start_str)
        end_date = self._parse_date(end_str)

        if not start_date or not end_date:
            return "skipped"

        duration = workout.get("duration", (end_date - start_date).total_seconds())

        # Create hash for deduplication
        hash_input = f"workout:{start_date.isoformat()}:{workout_type}:{duration}"
        record_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        existing = (
            self.db.query(HealthWorkout).filter(HealthWorkout.record_hash == record_hash).first()
        )
        if existing:
            return "duplicate"

        # Extract metrics
        energy = workout.get("activeEnergy", {})
        distance = workout.get("distance", {})
        heart_rate = workout.get("heartRateData", [])

        avg_hr = None
        max_hr = None
        min_hr = None
        if heart_rate:
            hr_values = [
                h.get("qty", h.get("value")) for h in heart_rate if h.get("qty") or h.get("value")
            ]
            if hr_values:
                hr_values = [float(v) for v in hr_values if v]
                if hr_values:
                    avg_hr = sum(hr_values) / len(hr_values)
                    max_hr = max(hr_values)
                    min_hr = min(hr_values)

        workout_record = HealthWorkout(
            workout_id=uuid.uuid4(),
            workout_type=workout_type,
            start_date=start_date,
            end_date=end_date,
            duration_seconds=duration,
            source_name=workout.get("source", workout.get("sourceName")),
            device=workout.get("device"),
            total_energy_burned=energy.get("qty", energy.get("value")),
            total_distance=distance.get("qty", distance.get("value")),
            average_heart_rate=avg_hr,
            max_heart_rate=max_hr,
            min_heart_rate=min_hr,
            indoor=workout.get("indoor"),
            route_data=workout.get("route"),
            extra_data=workout.get("metadata"),
            record_hash=record_hash,
            created_at=datetime.utcnow(),
        )
        self.db.add(workout_record)
        self.db.commit()

        return "inserted"

    def _process_sleep(self, sleep: dict) -> str:
        """Process a sleep record."""
        start_str = sleep.get("startDate", sleep.get("start"))
        end_str = sleep.get("endDate", sleep.get("end"))

        if not start_str or not end_str:
            return "skipped"

        start_date = self._parse_date(start_str)
        end_date = self._parse_date(end_str)

        if not start_date or not end_date:
            return "skipped"

        # Get sleep stage/value
        stage = sleep.get("value", sleep.get("sleepValue", "asleep"))
        stage = SLEEP_STAGE_MAP.get(stage, stage)

        duration = (end_date - start_date).total_seconds()

        # Create hash for deduplication
        hash_input = f"sleep:{start_date.isoformat()}:{end_date.isoformat()}:{stage}"
        record_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        existing = self.db.query(HealthSleep).filter(HealthSleep.record_hash == record_hash).first()
        if existing:
            return "duplicate"

        sleep_record = HealthSleep(
            sleep_id=uuid.uuid4(),
            start_date=start_date,
            end_date=end_date,
            source_name=sleep.get("source", sleep.get("sourceName")),
            device=sleep.get("device"),
            sleep_stage=stage,
            duration_seconds=duration,
            record_hash=record_hash,
            created_at=datetime.utcnow(),
        )
        self.db.add(sleep_record)
        self.db.commit()

        return "inserted"

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date string formats."""
        if not date_str:
            return None

        formats = [
            "%Y-%m-%d %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # Convert to UTC if timezone aware
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)
                return dt
            except ValueError:
                continue

        logger.warning("health_date_parse_failed", date_str=date_str)
        return None

    # =========================================================================
    # Daily Summary Aggregation
    # =========================================================================

    def _update_daily_summary(self, summary_date: date) -> None:
        """Update or create daily summary for a given date."""
        day_start = datetime.combine(summary_date, datetime.min.time())
        day_end = day_start + timedelta(days=1)

        # Aggregate steps
        steps_result = (
            self.db.query(func.sum(HealthMetric.value))
            .filter(
                HealthMetric.metric_type == "steps",
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
            .scalar()
        )

        # Aggregate distance (supports both "distance" and "walking_running_distance" metric types)
        distance_result = (
            self.db.query(func.sum(HealthMetric.value))
            .filter(
                HealthMetric.metric_type.in_(["distance", "walking_running_distance"]),
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
            .scalar()
        )

        # Aggregate flights climbed
        flights_result = (
            self.db.query(func.sum(HealthMetric.value))
            .filter(
                HealthMetric.metric_type == "flights_climbed",
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
            .scalar()
        )

        # Active energy
        active_energy = (
            self.db.query(func.sum(HealthMetric.value))
            .filter(
                HealthMetric.metric_type == "active_energy",
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
            .scalar()
        )

        # Basal energy
        basal_energy = (
            self.db.query(func.sum(HealthMetric.value))
            .filter(
                HealthMetric.metric_type == "basal_energy",
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
            .scalar()
        )

        # Exercise minutes
        exercise_mins = (
            self.db.query(func.sum(HealthMetric.value))
            .filter(
                HealthMetric.metric_type == "exercise_time",
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
            .scalar()
        )

        # Stand hours
        stand_hrs = (
            self.db.query(func.count(HealthMetric.id))
            .filter(
                HealthMetric.metric_type == "stand_hours",
                HealthMetric.value >= 1,
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
            .scalar()
        )

        # Heart rate stats
        hr_stats = (
            self.db.query(
                func.avg(HealthMetric.value).label("avg"),
                func.max(HealthMetric.value).label("max"),
                func.min(HealthMetric.value).label("min"),
            )
            .filter(
                HealthMetric.metric_type == "heart_rate",
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
            .first()
        )

        # Resting heart rate
        resting_hr = (
            self.db.query(func.avg(HealthMetric.value))
            .filter(
                HealthMetric.metric_type == "resting_heart_rate",
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
            .scalar()
        )

        # HRV
        hrv = (
            self.db.query(func.avg(HealthMetric.value))
            .filter(
                HealthMetric.metric_type == "heart_rate_variability",
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
            .scalar()
        )

        # Sleep (previous night - check sleep ending on this date)
        sleep_prev_night = day_start - timedelta(hours=12)
        sleep_stats = (
            self.db.query(
                HealthSleep.sleep_stage,
                func.sum(HealthSleep.duration_seconds).label("duration"),
            )
            .filter(
                HealthSleep.start_date >= sleep_prev_night,
                HealthSleep.start_date < day_start + timedelta(hours=12),
            )
            .group_by(HealthSleep.sleep_stage)
            .all()
        )

        total_sleep = 0
        time_in_bed = 0
        rem_sleep = 0
        core_sleep = 0
        deep_sleep = 0
        awake_time = 0

        for stage_stat in sleep_stats:
            duration_mins = int((stage_stat.duration or 0) / 60)
            if stage_stat.sleep_stage == "in_bed":
                time_in_bed = duration_mins
            elif stage_stat.sleep_stage == "rem":
                rem_sleep = duration_mins
                total_sleep += duration_mins
            elif stage_stat.sleep_stage == "core":
                core_sleep = duration_mins
                total_sleep += duration_mins
            elif stage_stat.sleep_stage == "deep":
                deep_sleep = duration_mins
                total_sleep += duration_mins
            elif stage_stat.sleep_stage == "asleep":
                # Generic asleep (not broken into stages)
                total_sleep += duration_mins
            elif stage_stat.sleep_stage == "awake":
                awake_time = duration_mins

        # Body measurement (latest for the day)
        body = (
            self.db.query(HealthBody)
            .filter(
                HealthBody.timestamp >= day_start,
                HealthBody.timestamp < day_end,
            )
            .order_by(desc(HealthBody.timestamp))
            .first()
        )

        # Blood oxygen
        blood_oxygen_stats = (
            self.db.query(
                func.avg(HealthMetric.value).label("avg"),
                func.min(HealthMetric.value).label("min"),
            )
            .filter(
                HealthMetric.metric_type == "blood_oxygen",
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
            .first()
        )

        # Nutrition
        calories = (
            self.db.query(func.sum(HealthMetric.value))
            .filter(
                HealthMetric.metric_type == "dietary_energy",
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
            .scalar()
        )
        protein = (
            self.db.query(func.sum(HealthMetric.value))
            .filter(
                HealthMetric.metric_type == "protein",
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
            .scalar()
        )
        carbs = (
            self.db.query(func.sum(HealthMetric.value))
            .filter(
                HealthMetric.metric_type == "carbohydrates",
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
            .scalar()
        )
        fat = (
            self.db.query(func.sum(HealthMetric.value))
            .filter(
                HealthMetric.metric_type == "total_fat",
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
            .scalar()
        )
        water = (
            self.db.query(func.sum(HealthMetric.value))
            .filter(
                HealthMetric.metric_type == "water",
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
            .scalar()
        )

        # Workouts
        workout_stats = (
            self.db.query(
                func.count(HealthWorkout.id).label("count"),
                func.sum(HealthWorkout.duration_seconds).label("duration"),
                func.sum(HealthWorkout.total_energy_burned).label("calories"),
                func.sum(HealthWorkout.total_distance).label("distance"),
            )
            .filter(
                HealthWorkout.start_date >= day_start,
                HealthWorkout.start_date < day_end,
            )
            .first()
        )

        # Combine metric distance with workout distance
        workout_distance = workout_stats.distance if workout_stats and workout_stats.distance else 0
        metric_distance = distance_result if distance_result else 0
        total_distance = (
            metric_distance + workout_distance if (metric_distance or workout_distance) else None
        )

        # Upsert daily summary
        stmt = insert(HealthDailySummary).values(
            date=summary_date,
            total_steps=int(steps_result) if steps_result else None,
            total_distance=total_distance,
            total_flights_climbed=int(flights_result) if flights_result else None,
            active_energy_burned=active_energy,
            basal_energy_burned=basal_energy,
            exercise_minutes=int(exercise_mins) if exercise_mins else None,
            stand_hours=stand_hrs,
            resting_heart_rate=resting_hr,
            avg_heart_rate=hr_stats.avg if hr_stats else None,
            max_heart_rate=hr_stats.max if hr_stats else None,
            min_heart_rate=hr_stats.min if hr_stats else None,
            heart_rate_variability=hrv,
            total_sleep_minutes=total_sleep if total_sleep > 0 else None,
            time_in_bed_minutes=time_in_bed if time_in_bed > 0 else None,
            rem_sleep_minutes=rem_sleep if rem_sleep > 0 else None,
            core_sleep_minutes=core_sleep if core_sleep > 0 else None,
            deep_sleep_minutes=deep_sleep if deep_sleep > 0 else None,
            awake_minutes=awake_time if awake_time > 0 else None,
            weight=body.weight if body else None,
            body_fat_percentage=body.body_fat_percentage if body else None,
            blood_oxygen_avg=blood_oxygen_stats.avg if blood_oxygen_stats else None,
            blood_oxygen_min=blood_oxygen_stats.min if blood_oxygen_stats else None,
            calories_consumed=calories,
            protein_grams=protein,
            carbs_grams=carbs,
            fat_grams=fat,
            water_ml=water,
            workout_count=workout_stats.count if workout_stats else 0,
            total_workout_minutes=int((workout_stats.duration or 0) / 60)
            if workout_stats
            else None,
            workout_calories=workout_stats.calories if workout_stats else None,
            updated_at=datetime.utcnow(),
        )

        # Handle upsert
        stmt = stmt.on_conflict_do_update(
            index_elements=["date"],
            set_={
                "total_steps": stmt.excluded.total_steps,
                "total_distance": stmt.excluded.total_distance,
                "total_flights_climbed": stmt.excluded.total_flights_climbed,
                "active_energy_burned": stmt.excluded.active_energy_burned,
                "basal_energy_burned": stmt.excluded.basal_energy_burned,
                "exercise_minutes": stmt.excluded.exercise_minutes,
                "stand_hours": stmt.excluded.stand_hours,
                "resting_heart_rate": stmt.excluded.resting_heart_rate,
                "avg_heart_rate": stmt.excluded.avg_heart_rate,
                "max_heart_rate": stmt.excluded.max_heart_rate,
                "min_heart_rate": stmt.excluded.min_heart_rate,
                "heart_rate_variability": stmt.excluded.heart_rate_variability,
                "total_sleep_minutes": stmt.excluded.total_sleep_minutes,
                "time_in_bed_minutes": stmt.excluded.time_in_bed_minutes,
                "rem_sleep_minutes": stmt.excluded.rem_sleep_minutes,
                "core_sleep_minutes": stmt.excluded.core_sleep_minutes,
                "deep_sleep_minutes": stmt.excluded.deep_sleep_minutes,
                "awake_minutes": stmt.excluded.awake_minutes,
                "weight": stmt.excluded.weight,
                "body_fat_percentage": stmt.excluded.body_fat_percentage,
                "blood_oxygen_avg": stmt.excluded.blood_oxygen_avg,
                "blood_oxygen_min": stmt.excluded.blood_oxygen_min,
                "calories_consumed": stmt.excluded.calories_consumed,
                "protein_grams": stmt.excluded.protein_grams,
                "carbs_grams": stmt.excluded.carbs_grams,
                "fat_grams": stmt.excluded.fat_grams,
                "water_ml": stmt.excluded.water_ml,
                "workout_count": stmt.excluded.workout_count,
                "total_workout_minutes": stmt.excluded.total_workout_minutes,
                "workout_calories": stmt.excluded.workout_calories,
                "updated_at": stmt.excluded.updated_at,
            },
        )

        self.db.execute(stmt)
        self.db.commit()

    # =========================================================================
    # Data Retrieval - Summary
    # =========================================================================

    def get_sync_status(self) -> dict[str, Any]:
        """Get the current sync status."""
        # Get last completed upload
        last_upload = (
            self.db.query(HealthUpload)
            .filter(HealthUpload.status == "completed")
            .order_by(desc(HealthUpload.completed_at))
            .first()
        )

        # Get counts
        metrics_count = self.db.query(func.count(HealthMetric.id)).scalar()
        workouts_count = self.db.query(func.count(HealthWorkout.id)).scalar()
        sleep_count = self.db.query(func.count(HealthSleep.id)).scalar()
        body_count = self.db.query(func.count(HealthBody.id)).scalar()

        # Get data range
        date_range = self.db.query(
            func.min(HealthMetric.timestamp).label("min"),
            func.max(HealthMetric.timestamp).label("max"),
        ).first()

        # Get pending/processing/failed upload counts
        pending = (
            self.db.query(func.count(HealthUpload.id))
            .filter(HealthUpload.status == "pending")
            .scalar()
        )
        processing = (
            self.db.query(func.count(HealthUpload.id))
            .filter(HealthUpload.status == "processing")
            .scalar()
        )
        failed = (
            self.db.query(func.count(HealthUpload.id))
            .filter(HealthUpload.status == "failed")
            .scalar()
        )

        # Get currently processing uploads
        active_uploads = (
            self.db.query(HealthUpload)
            .filter(HealthUpload.status == "processing")
            .order_by(desc(HealthUpload.started_at))
            .all()
        )

        # Get recent uploads (last 10, any status)
        recent_uploads = (
            self.db.query(HealthUpload).order_by(desc(HealthUpload.started_at)).limit(10).all()
        )

        def upload_to_dict(upload: HealthUpload) -> dict:
            return {
                "upload_id": str(upload.upload_id),
                "status": upload.status,
                "source": upload.source or "webhook",
                "started_at": upload.started_at.isoformat() if upload.started_at else None,
                "completed_at": upload.completed_at.isoformat() if upload.completed_at else None,
                "records_processed": upload.records_processed or 0,
                "records_inserted": upload.records_inserted or 0,
                "records_duplicate": upload.records_duplicate or 0,
                "data_start_date": upload.data_start_date.isoformat()
                if upload.data_start_date
                else None,
                "data_end_date": upload.data_end_date.isoformat() if upload.data_end_date else None,
                "error_message": upload.error_message,
            }

        return {
            "last_sync": last_upload.completed_at.isoformat()
            if last_upload and last_upload.completed_at
            else None,
            "last_upload_id": str(last_upload.upload_id) if last_upload else None,
            "total_metrics": metrics_count or 0,
            "total_workouts": workouts_count or 0,
            "total_sleep_records": sleep_count or 0,
            "total_body_measurements": body_count or 0,
            "data_range_start": date_range.min.isoformat()
            if date_range and date_range.min
            else None,
            "data_range_end": date_range.max.isoformat() if date_range and date_range.max else None,
            "uploads_pending": pending or 0,
            "uploads_processing": processing or 0,
            "uploads_failed": failed or 0,
            "active_uploads": [upload_to_dict(u) for u in active_uploads],
            "recent_uploads": [upload_to_dict(u) for u in recent_uploads],
        }

    def get_upload_status(self, upload_id: str) -> Optional[dict[str, Any]]:
        """
        Get the status of a specific upload by ID.

        Used for polling upload status when WebSocket is unavailable.
        Returns None if upload not found.
        """
        upload = self.db.query(HealthUpload).filter(HealthUpload.upload_id == upload_id).first()

        if not upload:
            return None

        return {
            "upload_id": str(upload.upload_id),
            "status": upload.status,
            "source": upload.source or "webhook",
            "started_at": upload.started_at.isoformat() if upload.started_at else None,
            "completed_at": upload.completed_at.isoformat() if upload.completed_at else None,
            "records_processed": upload.records_processed or 0,
            "records_inserted": upload.records_inserted or 0,
            "records_duplicate": upload.records_duplicate or 0,
            "data_start_date": upload.data_start_date.isoformat()
            if upload.data_start_date
            else None,
            "data_end_date": upload.data_end_date.isoformat() if upload.data_end_date else None,
            "error_message": upload.error_message,
            "processing_time_ms": (
                int((upload.completed_at - upload.started_at).total_seconds() * 1000)
                if upload.completed_at and upload.started_at
                else None
            ),
        }

    def get_summary(self, target_date: Optional[date] = None) -> HealthSummaryResponse:
        """Get health summary for dashboard cards."""
        if target_date is None:
            target_date = get_local_today()

        # Get daily summary
        summary = (
            self.db.query(HealthDailySummary).filter(HealthDailySummary.date == target_date).first()
        )

        # Get previous day for comparison
        prev_summary = (
            self.db.query(HealthDailySummary)
            .filter(HealthDailySummary.date == target_date - timedelta(days=1))
            .first()
        )

        # Get most recent VO2 Max (typically not daily, more sporadic)
        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = day_start + timedelta(days=1)

        vo2_max_record = (
            self.db.query(HealthMetric)
            .filter(
                HealthMetric.metric_type == "vo2_max",
                HealthMetric.timestamp < day_end,
            )
            .order_by(desc(HealthMetric.timestamp))
            .first()
        )

        # Get most recent respiratory rate
        respiratory_record = (
            self.db.query(HealthMetric)
            .filter(
                HealthMetric.metric_type == "respiratory_rate",
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
            .order_by(desc(HealthMetric.timestamp))
            .first()
        )

        cards = []

        # Steps card
        if summary and summary.total_steps:
            change = None
            direction = None
            if prev_summary and prev_summary.total_steps:
                change = (
                    (summary.total_steps - prev_summary.total_steps) / prev_summary.total_steps
                ) * 100
                direction = "up" if change > 0 else "down" if change < 0 else "neutral"
            cards.append(
                HealthSummaryCard(
                    title="Steps",
                    value=f"{summary.total_steps:,}",
                    change=round(change, 1) if change else None,
                    change_direction=direction,
                    icon="footprints",
                )
            )

        # Heart rate card
        if summary and summary.resting_heart_rate:
            cards.append(
                HealthSummaryCard(
                    title="Resting HR",
                    value=str(int(summary.resting_heart_rate)),
                    unit="bpm",
                    icon="heart",
                )
            )

        # Sleep card
        if summary and summary.total_sleep_minutes:
            hours = summary.total_sleep_minutes // 60
            mins = summary.total_sleep_minutes % 60
            cards.append(
                HealthSummaryCard(
                    title="Sleep",
                    value=f"{hours}h {mins}m",
                    icon="moon",
                )
            )

        # Active calories card
        if summary and summary.active_energy_burned:
            cards.append(
                HealthSummaryCard(
                    title="Active Calories",
                    value=f"{int(summary.active_energy_burned):,}",
                    unit="kcal",
                    icon="flame",
                )
            )

        # Distance card (convert km to miles for imperial)
        if summary and summary.total_distance:
            distance_miles = summary.total_distance * KM_TO_MILES
            cards.append(
                HealthSummaryCard(
                    title="Distance",
                    value=f"{distance_miles:.1f}",
                    unit="mi",
                    icon="map-pin",
                )
            )

        # Convert units to imperial
        distance_miles = (
            (summary.total_distance * KM_TO_MILES) if summary and summary.total_distance else None
        )
        weight_lbs = (summary.weight * KG_TO_LBS) if summary and summary.weight else None

        return HealthSummaryResponse(
            date=target_date,
            period="today",
            cards=cards,
            steps=summary.total_steps if summary else None,
            steps_goal=10000,
            active_calories=summary.active_energy_burned if summary else None,
            exercise_minutes=summary.exercise_minutes if summary else None,
            stand_hours=summary.stand_hours if summary else None,
            distance_km=distance_miles,  # Now returns miles
            resting_heart_rate=summary.resting_heart_rate if summary else None,
            avg_heart_rate=summary.avg_heart_rate if summary else None,
            sleep_hours=(summary.total_sleep_minutes / 60)
            if summary and summary.total_sleep_minutes
            else None,
            weight_kg=weight_lbs,  # Now returns lbs
            # Vitals
            blood_oxygen_avg=summary.blood_oxygen_avg if summary else None,
            vo2_max=vo2_max_record.value if vo2_max_record else None,
            respiratory_rate=respiratory_record.value if respiratory_record else None,
            hrv_avg=summary.heart_rate_variability if summary else None,
        )

    # =========================================================================
    # Data Retrieval - Steps
    # =========================================================================

    def get_steps_history(self, days: int = 7) -> StepsHistoryResponse:
        """Get steps history for charts."""
        end_date = get_local_today()
        start_date = end_date - timedelta(days=days - 1)

        summaries = (
            self.db.query(HealthDailySummary)
            .filter(
                HealthDailySummary.date >= start_date,
                HealthDailySummary.date <= end_date,
            )
            .order_by(HealthDailySummary.date)
            .all()
        )

        data = []
        total_steps = 0
        best_day = None
        goal_met_days = 0
        steps_goal = 10000

        for s in summaries:
            steps = s.total_steps or 0
            total_steps += steps

            # Convert km to miles for imperial units
            distance_miles = (s.total_distance * KM_TO_MILES) if s.total_distance else None
            point = StepsDataPoint(
                date=s.date,
                steps=steps,
                distance_meters=distance_miles,  # Returns miles (field name kept for API compat)
                flights_climbed=s.total_flights_climbed,
            )
            data.append(point)

            if steps >= steps_goal:
                goal_met_days += 1

            if best_day is None or steps > (best_day.steps or 0):
                best_day = point

        avg_daily = total_steps / len(summaries) if summaries else 0

        return StepsHistoryResponse(
            period=f"{days}d",
            data=data,
            total_steps=total_steps,
            avg_daily_steps=round(avg_daily, 0),
            best_day=best_day,
            goal_met_days=goal_met_days,
            steps_goal=steps_goal,
        )

    # =========================================================================
    # Data Retrieval - Heart Rate
    # =========================================================================

    def get_heart_rate_data(self, days: int = 7) -> HeartRateResponse:
        """Get heart rate data for charts."""
        end_date = get_local_today()
        start_date = end_date - timedelta(days=days - 1)
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

        # Get raw heart rate data points
        raw_data = (
            self.db.query(HealthMetric)
            .filter(
                HealthMetric.metric_type == "heart_rate",
                HealthMetric.timestamp >= start_dt,
                HealthMetric.timestamp < end_dt,
            )
            .order_by(HealthMetric.timestamp)
            .limit(1000)  # Limit for performance
            .all()
        )

        data = [
            HeartRateDataPoint(
                timestamp=m.timestamp,
                bpm=m.value,
                context=m.extra_data.get("context") if m.extra_data else None,
            )
            for m in raw_data
        ]

        # Get daily summaries
        summaries = (
            self.db.query(HealthDailySummary)
            .filter(
                HealthDailySummary.date >= start_date,
                HealthDailySummary.date <= end_date,
            )
            .order_by(HealthDailySummary.date)
            .all()
        )

        daily_summary = [
            HeartRateSummary(
                date=s.date,
                resting_hr=s.resting_heart_rate,
                avg_hr=s.avg_heart_rate,
                max_hr=s.max_heart_rate,
                min_hr=s.min_heart_rate,
                hrv_avg=s.heart_rate_variability,
            )
            for s in summaries
        ]

        # Current resting HR (most recent)
        current_resting = None
        if summaries:
            for s in reversed(summaries):
                if s.resting_heart_rate:
                    current_resting = s.resting_heart_rate
                    break

        # Average resting HR
        resting_values = [s.resting_heart_rate for s in summaries if s.resting_heart_rate]
        avg_resting = sum(resting_values) / len(resting_values) if resting_values else None

        return HeartRateResponse(
            period=f"{days}d",
            data=data,
            daily_summary=daily_summary,
            current_resting_hr=current_resting,
            avg_resting_hr=avg_resting,
            hrv_trend=None,  # TODO: Calculate trend
        )

    # =========================================================================
    # Data Retrieval - Sleep
    # =========================================================================

    def get_sleep_history(self, days: int = 7) -> SleepHistoryResponse:
        """Get sleep history for charts."""
        end_date = get_local_today()
        start_date = end_date - timedelta(days=days)

        summaries = (
            self.db.query(HealthDailySummary)
            .filter(
                HealthDailySummary.date >= start_date,
                HealthDailySummary.date <= end_date,
            )
            .order_by(HealthDailySummary.date)
            .all()
        )

        data = []
        total_sleep = 0
        total_in_bed = 0
        goal_met_days = 0
        sleep_goal_hours = 8.0

        for s in summaries:
            if not s.total_sleep_minutes:
                continue

            stages = []
            total_stage_mins = 0

            if s.awake_minutes:
                stages.append(SleepStage(stage="awake", minutes=s.awake_minutes, percentage=0))
                total_stage_mins += s.awake_minutes
            if s.rem_sleep_minutes:
                stages.append(SleepStage(stage="rem", minutes=s.rem_sleep_minutes, percentage=0))
                total_stage_mins += s.rem_sleep_minutes
            if s.core_sleep_minutes:
                stages.append(SleepStage(stage="core", minutes=s.core_sleep_minutes, percentage=0))
                total_stage_mins += s.core_sleep_minutes
            if s.deep_sleep_minutes:
                stages.append(SleepStage(stage="deep", minutes=s.deep_sleep_minutes, percentage=0))
                total_stage_mins += s.deep_sleep_minutes

            # Calculate percentages
            for stage in stages:
                stage.percentage = round(
                    (stage.minutes / total_stage_mins * 100) if total_stage_mins > 0 else 0, 1
                )

            # Get sleep times from raw sleep records
            prev_night_start = datetime.combine(
                s.date - timedelta(days=1), datetime.min.time()
            ) + timedelta(hours=18)
            prev_night_end = datetime.combine(s.date, datetime.min.time()) + timedelta(hours=12)

            sleep_records = (
                self.db.query(HealthSleep)
                .filter(
                    HealthSleep.start_date >= prev_night_start,
                    HealthSleep.start_date < prev_night_end,
                )
                .order_by(HealthSleep.start_date)
                .all()
            )

            start_time = sleep_records[0].start_date if sleep_records else None
            end_time = sleep_records[-1].end_date if sleep_records else None

            efficiency = None
            if s.time_in_bed_minutes and s.total_sleep_minutes:
                efficiency = round((s.total_sleep_minutes / s.time_in_bed_minutes) * 100, 1)

            session = SleepSession(
                date=s.date,
                start_time=start_time
                or datetime.combine(s.date - timedelta(days=1), datetime.min.time())
                + timedelta(hours=22),
                end_time=end_time
                or datetime.combine(s.date, datetime.min.time()) + timedelta(hours=6),
                total_minutes=s.total_sleep_minutes,
                time_in_bed_minutes=s.time_in_bed_minutes or s.total_sleep_minutes,
                sleep_efficiency=efficiency,
                stages=stages,
                avg_heart_rate=None,  # TODO: Get from sleep records
                respiratory_rate=None,
            )
            data.append(session)

            total_sleep += s.total_sleep_minutes
            total_in_bed += s.time_in_bed_minutes or s.total_sleep_minutes

            if s.total_sleep_minutes >= (sleep_goal_hours * 60):
                goal_met_days += 1

        count = len(data) if data else 1
        avg_sleep = total_sleep / count / 60
        avg_in_bed = total_in_bed / count / 60
        avg_efficiency = (total_sleep / total_in_bed * 100) if total_in_bed > 0 else None

        return SleepHistoryResponse(
            period=f"{days}d",
            data=data,
            avg_sleep_hours=round(avg_sleep, 1),
            avg_time_in_bed_hours=round(avg_in_bed, 1),
            avg_sleep_efficiency=round(avg_efficiency, 1) if avg_efficiency else None,
            sleep_goal_hours=sleep_goal_hours,
            goal_met_days=goal_met_days,
        )

    # =========================================================================
    # Data Retrieval - Workouts
    # =========================================================================

    def get_workout_history(self, days: int = 30) -> WorkoutHistoryResponse:
        """Get workout history."""
        end_date = get_local_today()
        start_date = end_date - timedelta(days=days)
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

        workouts = (
            self.db.query(HealthWorkout)
            .filter(
                HealthWorkout.start_date >= start_dt,
                HealthWorkout.start_date < end_dt,
            )
            .order_by(desc(HealthWorkout.start_date))
            .all()
        )

        data = []
        total_duration = 0
        total_calories = 0
        total_distance = 0
        by_type: dict[str, int] = {}

        for w in workouts:
            duration_mins = (w.duration_seconds or 0) / 60
            total_duration += duration_mins
            total_calories += w.total_energy_burned or 0
            total_distance += w.total_distance or 0

            workout_type = w.workout_type
            by_type[workout_type] = by_type.get(workout_type, 0) + 1

            # Convert to miles for imperial
            workout_miles = (w.total_distance * KM_TO_MILES) if w.total_distance else None
            data.append(
                WorkoutSummary(
                    workout_id=str(w.workout_id),
                    workout_type=workout_type,
                    date=w.start_date,
                    duration_minutes=round(duration_mins, 1),
                    calories_burned=w.total_energy_burned,
                    distance_meters=workout_miles,  # Returns miles
                    avg_heart_rate=w.average_heart_rate,
                    max_heart_rate=w.max_heart_rate,
                    indoor=w.indoor,
                )
            )

        weeks = days / 7
        avg_per_week = len(workouts) / weeks if weeks > 0 else 0

        # Convert total distance to miles
        total_distance_miles = total_distance * KM_TO_MILES

        return WorkoutHistoryResponse(
            period=f"{days}d",
            workouts=data,
            total_workouts=len(workouts),
            total_duration_minutes=round(total_duration, 1),
            total_calories_burned=round(total_calories, 1),
            total_distance_meters=round(total_distance_miles, 1),  # Returns miles
            workouts_by_type=by_type,
            avg_workouts_per_week=round(avg_per_week, 1),
        )

    def get_workout_detail(self, workout_id: str) -> Optional[WorkoutDetail]:
        """Get detailed workout information."""
        workout = (
            self.db.query(HealthWorkout)
            .filter(HealthWorkout.workout_id == uuid.UUID(workout_id))
            .first()
        )

        if not workout:
            return None

        duration_mins = (workout.duration_seconds or 0) / 60

        # Convert to imperial units
        distance_miles = (workout.total_distance * KM_TO_MILES) if workout.total_distance else None
        temp_f = (
            celsius_to_fahrenheit(workout.weather_temperature)
            if workout.weather_temperature
            else None
        )

        return WorkoutDetail(
            workout_id=str(workout.workout_id),
            workout_type=workout.workout_type,
            date=workout.start_date,
            duration_minutes=round(duration_mins, 1),
            calories_burned=workout.total_energy_burned,
            distance_meters=distance_miles,  # Returns miles
            avg_heart_rate=workout.average_heart_rate,
            max_heart_rate=workout.max_heart_rate,
            min_heart_rate=workout.min_heart_rate,
            indoor=workout.indoor,
            splits=workout.splits,
            route_available=workout.route_data is not None,
            weather_temp_celsius=temp_f,  # Returns Fahrenheit
            metadata=workout.extra_data,
        )

    # =========================================================================
    # Data Retrieval - Body
    # =========================================================================

    def get_body_history(self, days: int = 90) -> BodyHistoryResponse:
        """Get body measurement history."""
        end_date = get_local_today()
        start_date = end_date - timedelta(days=days)
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

        measurements = (
            self.db.query(HealthBody)
            .filter(
                HealthBody.timestamp >= start_dt,
                HealthBody.timestamp < end_dt,
            )
            .order_by(HealthBody.timestamp)
            .all()
        )

        data = [
            BodyMeasurement(
                timestamp=m.timestamp,
                weight_kg=(m.weight * KG_TO_LBS) if m.weight else None,  # Returns lbs
                body_fat_percentage=m.body_fat_percentage,
                bmi=m.body_mass_index,
                lean_body_mass_kg=(m.lean_body_mass * KG_TO_LBS)
                if m.lean_body_mass
                else None,  # Returns lbs
            )
            for m in measurements
        ]

        # Current values (most recent)
        current_weight = None
        current_bmi = None
        current_body_fat = None
        weight_change = None
        weight_trend = None

        if measurements:
            latest = measurements[-1]
            current_weight = latest.weight
            current_bmi = latest.body_mass_index
            current_body_fat = latest.body_fat_percentage

            # Find first weight measurement
            weight_measurements = [m for m in measurements if m.weight]
            if len(weight_measurements) >= 2:
                first_weight = weight_measurements[0].weight
                last_weight = weight_measurements[-1].weight
                if first_weight and last_weight:
                    weight_change = last_weight - first_weight
                    if abs(weight_change) < 0.5:
                        weight_trend = "stable"
                    elif weight_change > 0:
                        weight_trend = "gaining"
                    else:
                        weight_trend = "losing"

        # Convert to lbs for imperial
        current_weight_lbs = (current_weight * KG_TO_LBS) if current_weight else None
        weight_change_lbs = (weight_change * KG_TO_LBS) if weight_change else None

        return BodyHistoryResponse(
            period=f"{days}d",
            measurements=data,
            current_weight_kg=current_weight_lbs,  # Returns lbs
            weight_change_kg=round(weight_change_lbs, 1)
            if weight_change_lbs
            else None,  # Returns lbs
            weight_trend=weight_trend,
            current_bmi=current_bmi,
            current_body_fat=current_body_fat,
        )

    # =========================================================================
    # Data Retrieval - Nutrition
    # =========================================================================

    def get_nutrition_history(self, days: int = 7) -> NutritionHistoryResponse:
        """Get nutrition history."""
        end_date = get_local_today()
        start_date = end_date - timedelta(days=days - 1)

        summaries = (
            self.db.query(HealthDailySummary)
            .filter(
                HealthDailySummary.date >= start_date,
                HealthDailySummary.date <= end_date,
            )
            .order_by(HealthDailySummary.date)
            .all()
        )

        data = []
        total_calories = 0
        total_protein = 0
        days_with_data = 0

        for s in summaries:
            if s.calories_consumed or s.protein_grams:
                days_with_data += 1
                total_calories += s.calories_consumed or 0
                total_protein += s.protein_grams or 0

            data.append(
                NutritionDay(
                    date=s.date,
                    calories=s.calories_consumed,
                    protein_grams=s.protein_grams,
                    carbs_grams=s.carbs_grams,
                    fat_grams=s.fat_grams,
                    water_ml=(s.water_ml * ML_TO_FLOZ) if s.water_ml else None,  # Returns fl oz
                )
            )

        avg_calories = total_calories / days_with_data if days_with_data > 0 else None
        avg_protein = total_protein / days_with_data if days_with_data > 0 else None

        return NutritionHistoryResponse(
            period=f"{days}d",
            data=data,
            avg_daily_calories=round(avg_calories, 0) if avg_calories else None,
            avg_daily_protein=round(avg_protein, 0) if avg_protein else None,
            calorie_goal=2000,  # TODO: Make configurable
        )

    def get_detailed_nutrition(self, days: int = 7) -> DetailedNutritionResponse:
        """Get detailed nutrition with micronutrients."""
        end_date = get_local_today()
        start_date = end_date - timedelta(days=days - 1)
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

        # Micronutrient metric types to query
        micronutrient_types = [
            "vitamin_a",
            "vitamin_c",
            "vitamin_d",
            "vitamin_e",
            "vitamin_k",
            "vitamin_b6",
            "vitamin_b12",
            "thiamin",
            "riboflavin",
            "niacin",
            "folate",
            "pantothenic_acid",
            "biotin",
            "calcium",
            "iron",
            "magnesium",
            "phosphorus",
            "potassium",
            "sodium",
            "zinc",
            "copper",
            "manganese",
            "selenium",
            "chromium",
            "molybdenum",
            "iodine",
            "cholesterol",
            "saturated_fat",
            "monounsaturated_fat",
            "polyunsaturated_fat",
            "caffeine",
            "fiber",
            "sugar",
        ]

        # Query all micronutrient data for the period, grouped by date and type
        raw_data = (
            self.db.query(
                cast(HealthMetric.timestamp, Date).label("date"),
                HealthMetric.metric_type,
                func.sum(HealthMetric.value).label("total"),
            )
            .filter(
                HealthMetric.metric_type.in_(micronutrient_types),
                HealthMetric.timestamp >= start_dt,
                HealthMetric.timestamp < end_dt,
            )
            .group_by(
                cast(HealthMetric.timestamp, Date),
                HealthMetric.metric_type,
            )
            .all()
        )

        # Build a dict: {date: {metric_type: value}}
        daily_data: dict[date, dict[str, float]] = {}
        for row in raw_data:
            if row.date not in daily_data:
                daily_data[row.date] = {}
            daily_data[row.date][row.metric_type] = row.total

        # Get basic nutrition from daily summaries
        summaries = (
            self.db.query(HealthDailySummary)
            .filter(
                HealthDailySummary.date >= start_date,
                HealthDailySummary.date <= end_date,
            )
            .order_by(HealthDailySummary.date)
            .all()
        )

        # Build response data
        data = []
        totals: dict[str, float] = {}
        days_with_data = 0

        for s in summaries:
            micro = daily_data.get(s.date, {})

            micronutrients = MicronutrientData(
                vitamin_a_mcg=micro.get("vitamin_a"),
                vitamin_c_mg=micro.get("vitamin_c"),
                vitamin_d_mcg=micro.get("vitamin_d"),
                vitamin_e_mg=micro.get("vitamin_e"),
                vitamin_k_mcg=micro.get("vitamin_k"),
                vitamin_b6_mg=micro.get("vitamin_b6"),
                vitamin_b12_mcg=micro.get("vitamin_b12"),
                thiamin_mg=micro.get("thiamin"),
                riboflavin_mg=micro.get("riboflavin"),
                niacin_mg=micro.get("niacin"),
                folate_mcg=micro.get("folate"),
                pantothenic_acid_mg=micro.get("pantothenic_acid"),
                biotin_mcg=micro.get("biotin"),
                calcium_mg=micro.get("calcium"),
                iron_mg=micro.get("iron"),
                magnesium_mg=micro.get("magnesium"),
                phosphorus_mg=micro.get("phosphorus"),
                potassium_mg=micro.get("potassium"),
                sodium_mg=micro.get("sodium"),
                zinc_mg=micro.get("zinc"),
                copper_mg=micro.get("copper"),
                manganese_mg=micro.get("manganese"),
                selenium_mcg=micro.get("selenium"),
                chromium_mcg=micro.get("chromium"),
                molybdenum_mcg=micro.get("molybdenum"),
                iodine_mcg=micro.get("iodine"),
                cholesterol_mg=micro.get("cholesterol"),
                saturated_fat_grams=micro.get("saturated_fat"),
                monounsaturated_fat_grams=micro.get("monounsaturated_fat"),
                polyunsaturated_fat_grams=micro.get("polyunsaturated_fat"),
                caffeine_mg=micro.get("caffeine"),
            )

            # Track totals for averaging
            if micro:
                days_with_data += 1
                for key, value in micro.items():
                    if value:
                        totals[key] = totals.get(key, 0) + value

            data.append(
                DetailedNutritionDay(
                    date=s.date,
                    calories=s.calories_consumed,
                    protein_grams=s.protein_grams,
                    carbs_grams=s.carbs_grams,
                    fat_grams=s.fat_grams,
                    fiber_grams=micro.get("fiber"),
                    sugar_grams=micro.get("sugar"),
                    water_ml=(s.water_ml * ML_TO_FLOZ) if s.water_ml else None,  # Returns fl oz
                    micronutrients=micronutrients,
                )
            )

        # Calculate averages
        avg_count = days_with_data if days_with_data > 0 else 1
        avg_micronutrients = MicronutrientData(
            vitamin_a_mcg=totals.get("vitamin_a", 0) / avg_count if "vitamin_a" in totals else None,
            vitamin_c_mg=totals.get("vitamin_c", 0) / avg_count if "vitamin_c" in totals else None,
            vitamin_d_mcg=totals.get("vitamin_d", 0) / avg_count if "vitamin_d" in totals else None,
            vitamin_e_mg=totals.get("vitamin_e", 0) / avg_count if "vitamin_e" in totals else None,
            vitamin_k_mcg=totals.get("vitamin_k", 0) / avg_count if "vitamin_k" in totals else None,
            vitamin_b6_mg=totals.get("vitamin_b6", 0) / avg_count
            if "vitamin_b6" in totals
            else None,
            vitamin_b12_mcg=totals.get("vitamin_b12", 0) / avg_count
            if "vitamin_b12" in totals
            else None,
            thiamin_mg=totals.get("thiamin", 0) / avg_count if "thiamin" in totals else None,
            riboflavin_mg=totals.get("riboflavin", 0) / avg_count
            if "riboflavin" in totals
            else None,
            niacin_mg=totals.get("niacin", 0) / avg_count if "niacin" in totals else None,
            folate_mcg=totals.get("folate", 0) / avg_count if "folate" in totals else None,
            pantothenic_acid_mg=totals.get("pantothenic_acid", 0) / avg_count
            if "pantothenic_acid" in totals
            else None,
            biotin_mcg=totals.get("biotin", 0) / avg_count if "biotin" in totals else None,
            calcium_mg=totals.get("calcium", 0) / avg_count if "calcium" in totals else None,
            iron_mg=totals.get("iron", 0) / avg_count if "iron" in totals else None,
            magnesium_mg=totals.get("magnesium", 0) / avg_count if "magnesium" in totals else None,
            phosphorus_mg=totals.get("phosphorus", 0) / avg_count
            if "phosphorus" in totals
            else None,
            potassium_mg=totals.get("potassium", 0) / avg_count if "potassium" in totals else None,
            sodium_mg=totals.get("sodium", 0) / avg_count if "sodium" in totals else None,
            zinc_mg=totals.get("zinc", 0) / avg_count if "zinc" in totals else None,
            copper_mg=totals.get("copper", 0) / avg_count if "copper" in totals else None,
            manganese_mg=totals.get("manganese", 0) / avg_count if "manganese" in totals else None,
            selenium_mcg=totals.get("selenium", 0) / avg_count if "selenium" in totals else None,
            chromium_mcg=totals.get("chromium", 0) / avg_count if "chromium" in totals else None,
            molybdenum_mcg=totals.get("molybdenum", 0) / avg_count
            if "molybdenum" in totals
            else None,
            iodine_mcg=totals.get("iodine", 0) / avg_count if "iodine" in totals else None,
            cholesterol_mg=totals.get("cholesterol", 0) / avg_count
            if "cholesterol" in totals
            else None,
            saturated_fat_grams=totals.get("saturated_fat", 0) / avg_count
            if "saturated_fat" in totals
            else None,
            monounsaturated_fat_grams=totals.get("monounsaturated_fat", 0) / avg_count
            if "monounsaturated_fat" in totals
            else None,
            polyunsaturated_fat_grams=totals.get("polyunsaturated_fat", 0) / avg_count
            if "polyunsaturated_fat" in totals
            else None,
            caffeine_mg=totals.get("caffeine", 0) / avg_count if "caffeine" in totals else None,
        )

        return DetailedNutritionResponse(
            period=f"{days}d",
            data=data,
            daily_values=DAILY_VALUES,
            avg_daily_micronutrients=avg_micronutrients,
        )

    # =========================================================================
    # Data Retrieval - Vitals
    # =========================================================================

    def get_vitals_data(self, days: int = 7) -> VitalsResponse:
        """Get vitals data (SpO2, respiratory rate, VO2 max)."""
        end_date = get_local_today()
        start_date = end_date - timedelta(days=days - 1)
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

        # Get daily summaries for blood oxygen
        summaries = (
            self.db.query(HealthDailySummary)
            .filter(
                HealthDailySummary.date >= start_date,
                HealthDailySummary.date <= end_date,
            )
            .order_by(HealthDailySummary.date)
            .all()
        )

        # Get VO2 max records (usually sporadic, not daily)
        vo2_records = (
            self.db.query(
                cast(HealthMetric.timestamp, Date).label("date"),
                func.max(HealthMetric.value).label("vo2_max"),
            )
            .filter(
                HealthMetric.metric_type == "vo2_max",
                HealthMetric.timestamp >= start_dt,
                HealthMetric.timestamp < end_dt,
            )
            .group_by(cast(HealthMetric.timestamp, Date))
            .all()
        )
        vo2_by_date = {r.date: r.vo2_max for r in vo2_records}

        # Get respiratory rate records
        resp_records = (
            self.db.query(
                cast(HealthMetric.timestamp, Date).label("date"),
                func.avg(HealthMetric.value).label("respiratory_rate"),
            )
            .filter(
                HealthMetric.metric_type == "respiratory_rate",
                HealthMetric.timestamp >= start_dt,
                HealthMetric.timestamp < end_dt,
            )
            .group_by(cast(HealthMetric.timestamp, Date))
            .all()
        )
        resp_by_date = {r.date: r.respiratory_rate for r in resp_records}

        # Get body temperature records
        temp_records = (
            self.db.query(
                cast(HealthMetric.timestamp, Date).label("date"),
                func.avg(HealthMetric.value).label("body_temperature"),
            )
            .filter(
                HealthMetric.metric_type == "body_temperature",
                HealthMetric.timestamp >= start_dt,
                HealthMetric.timestamp < end_dt,
            )
            .group_by(cast(HealthMetric.timestamp, Date))
            .all()
        )
        temp_by_date = {r.date: r.body_temperature for r in temp_records}

        # Build response data
        data = []
        total_spo2 = 0
        min_spo2 = None
        count_spo2 = 0
        total_resp = 0
        count_resp = 0

        for s in summaries:
            spo2_avg = s.blood_oxygen_avg
            spo2_min = s.blood_oxygen_min
            vo2 = vo2_by_date.get(s.date)
            resp = resp_by_date.get(s.date)
            temp = temp_by_date.get(s.date)

            if spo2_avg:
                total_spo2 += spo2_avg
                count_spo2 += 1
                if min_spo2 is None or (spo2_min and spo2_min < min_spo2):
                    min_spo2 = spo2_min

            if resp:
                total_resp += resp
                count_resp += 1

            data.append(
                VitalsDataPoint(
                    date=s.date,
                    blood_oxygen_avg=spo2_avg,
                    blood_oxygen_min=spo2_min,
                    respiratory_rate=resp,
                    vo2_max=vo2,
                    body_temperature=temp,
                )
            )

        # Current values (most recent)
        current_spo2 = None
        current_vo2 = None
        for d in reversed(data):
            if current_spo2 is None and d.blood_oxygen_avg:
                current_spo2 = d.blood_oxygen_avg
            if current_vo2 is None and d.vo2_max:
                current_vo2 = d.vo2_max
            if current_spo2 and current_vo2:
                break

        # VO2 max trend (compare first half to second half)
        vo2_values = [d.vo2_max for d in data if d.vo2_max]
        vo2_trend = None
        if len(vo2_values) >= 2:
            mid = len(vo2_values) // 2
            first_half = sum(vo2_values[:mid]) / mid
            second_half = sum(vo2_values[mid:]) / (len(vo2_values) - mid)
            diff = second_half - first_half
            if abs(diff) < 0.5:
                vo2_trend = "stable"
            elif diff > 0:
                vo2_trend = "improving"
            else:
                vo2_trend = "declining"

        return VitalsResponse(
            period=f"{days}d",
            data=data,
            current_spo2=current_spo2,
            avg_spo2=total_spo2 / count_spo2 if count_spo2 > 0 else None,
            min_spo2=min_spo2,
            current_vo2_max=current_vo2,
            vo2_max_trend=vo2_trend,
            avg_respiratory_rate=total_resp / count_resp if count_resp > 0 else None,
        )

    # =========================================================================
    # Data Retrieval - Mobility
    # =========================================================================

    def get_mobility_data(self, days: int = 30) -> MobilityResponse:
        """Get mobility metrics (walking speed, step length, asymmetry)."""
        end_date = get_local_today()
        start_date = end_date - timedelta(days=days - 1)
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

        mobility_types = [
            "walking_speed",
            "step_length",
            "walking_asymmetry",
            "walking_double_support",
            "stair_speed_up",
            "stair_speed_down",
        ]

        # Query all mobility metrics grouped by date
        raw_data = (
            self.db.query(
                cast(HealthMetric.timestamp, Date).label("date"),
                HealthMetric.metric_type,
                func.avg(HealthMetric.value).label("avg_value"),
            )
            .filter(
                HealthMetric.metric_type.in_(mobility_types),
                HealthMetric.timestamp >= start_dt,
                HealthMetric.timestamp < end_dt,
            )
            .group_by(
                cast(HealthMetric.timestamp, Date),
                HealthMetric.metric_type,
            )
            .all()
        )

        # Build daily data dict
        daily_data: dict[date, dict[str, float]] = {}
        for row in raw_data:
            if row.date not in daily_data:
                daily_data[row.date] = {}
            daily_data[row.date][row.metric_type] = row.avg_value

        # Generate response for each date
        data = []
        total_speed = 0
        total_length = 0
        total_asymmetry = 0
        count_speed = 0
        count_length = 0
        count_asymmetry = 0

        current = start_date
        while current <= end_date:
            metrics = daily_data.get(current, {})

            speed = metrics.get("walking_speed")
            step_len = metrics.get("step_length")
            asymmetry = metrics.get("walking_asymmetry")
            double_support = metrics.get("walking_double_support")
            stair_up = metrics.get("stair_speed_up")
            stair_down = metrics.get("stair_speed_down")

            # Convert speed to km/h (Apple stores as m/s)
            # Convert to imperial units (mph and inches)
            speed_mph = (speed * 3.6 * KMH_TO_MPH) if speed else None  # m/s -> km/h -> mph
            step_len_inches = (
                (step_len * 100 * CM_TO_INCHES) if step_len else None
            )  # m -> cm -> inches

            if speed_mph:
                total_speed += speed_mph
                count_speed += 1
            if step_len_inches:
                total_length += step_len_inches
                count_length += 1
            if asymmetry:
                total_asymmetry += asymmetry
                count_asymmetry += 1

            if metrics:  # Only add if there's data
                data.append(
                    MobilityDataPoint(
                        date=current,
                        walking_speed_kmh=speed_mph,  # Returns mph
                        step_length_cm=step_len_inches,  # Returns inches
                        walking_asymmetry_pct=asymmetry,
                        double_support_pct=double_support,
                        stair_speed_up=stair_up,
                        stair_speed_down=stair_down,
                    )
                )

            current += timedelta(days=1)

        # Calculate averages
        avg_speed = total_speed / count_speed if count_speed > 0 else None
        avg_length = total_length / count_length if count_length > 0 else None
        avg_asymmetry = total_asymmetry / count_asymmetry if count_asymmetry > 0 else None

        # Determine asymmetry status
        asymmetry_status = None
        if avg_asymmetry is not None:
            if avg_asymmetry < 10:
                asymmetry_status = "normal"
            elif avg_asymmetry < 20:
                asymmetry_status = "elevated"
            else:
                asymmetry_status = "concerning"

        return MobilityResponse(
            period=f"{days}d",
            data=data,
            avg_walking_speed_kmh=round(avg_speed, 2) if avg_speed else None,
            avg_step_length_cm=round(avg_length, 1) if avg_length else None,
            avg_asymmetry_pct=round(avg_asymmetry, 1) if avg_asymmetry else None,
            asymmetry_status=asymmetry_status,
        )

    # =========================================================================
    # Data Retrieval - Trends
    # =========================================================================

    def get_trends(self, days: int = 7) -> HealthTrendsResponse:
        """Get health trends with period comparison."""
        end_date = get_local_today()
        current_start = end_date - timedelta(days=days - 1)
        previous_start = current_start - timedelta(days=days)
        previous_end = current_start - timedelta(days=1)

        # Get current period averages
        current = (
            self.db.query(
                func.avg(HealthDailySummary.total_steps).label("steps"),
                func.avg(HealthDailySummary.resting_heart_rate).label("resting_hr"),
                func.avg(HealthDailySummary.total_sleep_minutes).label("sleep_mins"),
                func.avg(HealthDailySummary.active_energy_burned).label("active_cal"),
            )
            .filter(
                HealthDailySummary.date >= current_start,
                HealthDailySummary.date <= end_date,
            )
            .first()
        )

        # Get previous period averages
        previous = (
            self.db.query(
                func.avg(HealthDailySummary.total_steps).label("steps"),
                func.avg(HealthDailySummary.resting_heart_rate).label("resting_hr"),
                func.avg(HealthDailySummary.total_sleep_minutes).label("sleep_mins"),
                func.avg(HealthDailySummary.active_energy_burned).label("active_cal"),
            )
            .filter(
                HealthDailySummary.date >= previous_start,
                HealthDailySummary.date <= previous_end,
            )
            .first()
        )

        trends = []

        def add_trend(
            metric: str,
            current_val: Optional[float],
            previous_val: Optional[float],
            higher_is_better: bool = True,
        ):
            if current_val is None or previous_val is None or previous_val == 0:
                return
            change_abs = current_val - previous_val
            change_pct = (change_abs / previous_val) * 100

            if abs(change_pct) < 2:
                trend = "stable"
            elif (change_pct > 0 and higher_is_better) or (change_pct < 0 and not higher_is_better):
                trend = "improving"
            else:
                trend = "declining"

            trends.append(
                TrendComparison(
                    metric=metric,
                    current_value=round(current_val, 1),
                    previous_value=round(previous_val, 1),
                    change_absolute=round(change_abs, 1),
                    change_percentage=round(change_pct, 1),
                    trend=trend,
                )
            )

        if current and previous:
            add_trend("steps", current.steps, previous.steps, higher_is_better=True)
            add_trend(
                "resting_heart_rate",
                current.resting_hr,
                previous.resting_hr,
                higher_is_better=False,
            )
            add_trend(
                "sleep_minutes", current.sleep_mins, previous.sleep_mins, higher_is_better=True
            )
            add_trend(
                "active_calories", current.active_cal, previous.active_cal, higher_is_better=True
            )

        return HealthTrendsResponse(
            period=f"{days}d",
            comparison_period=f"previous_{days}d",
            trends=trends,
            insights=[],  # TODO: Add AI-generated insights
        )

    # =========================================================================
    # Diagnostics
    # =========================================================================

    def get_diagnostics(self) -> HealthDiagnosticsResponse:
        """Get diagnostic info about health data collection."""
        # Get total counts
        total_metrics = self.db.query(func.count(HealthMetric.id)).scalar() or 0
        total_workouts = self.db.query(func.count(HealthWorkout.id)).scalar() or 0
        total_sleep = self.db.query(func.count(HealthSleep.id)).scalar() or 0
        total_body = self.db.query(func.count(HealthBody.id)).scalar() or 0

        # Get data range
        date_range = self.db.query(
            func.min(HealthMetric.timestamp).label("min"),
            func.max(HealthMetric.timestamp).label("max"),
        ).first()

        # Get metric types with counts and date ranges
        metric_types_raw = (
            self.db.query(
                HealthMetric.metric_type,
                func.count(HealthMetric.id).label("count"),
                func.min(HealthMetric.timestamp).label("first"),
                func.max(HealthMetric.timestamp).label("last"),
            )
            .group_by(HealthMetric.metric_type)
            .order_by(desc(func.count(HealthMetric.id)))
            .all()
        )

        metric_types = [
            MetricTypeInfo(
                metric_type=m.metric_type,
                record_count=m.count,
                first_date=m.first,
                last_date=m.last,
            )
            for m in metric_types_raw
        ]

        # Check collection status by category
        available_types = {m.metric_type for m in metric_types_raw}

        collection_status = []
        warnings = []

        # Activity
        activity_types = {
            "steps",
            "distance",
            "flights_climbed",
            "active_energy",
            "exercise_time",
            "stand_hours",
        }
        activity_present = activity_types & available_types
        activity_count = sum(m.count for m in metric_types_raw if m.metric_type in activity_types)
        collection_status.append(
            DataCollectionStatus(
                category="Activity",
                has_data=len(activity_present) > 0,
                metric_types=list(activity_present),
                total_records=activity_count,
                warning=None if activity_present else "No activity data collected",
            )
        )
        if not activity_present:
            warnings.append("No activity data - check Health Auto Export configuration")

        # Heart
        heart_types = {"heart_rate", "resting_heart_rate", "heart_rate_variability"}
        heart_present = heart_types & available_types
        heart_count = sum(m.count for m in metric_types_raw if m.metric_type in heart_types)
        collection_status.append(
            DataCollectionStatus(
                category="Heart",
                has_data=len(heart_present) > 0,
                metric_types=list(heart_present),
                total_records=heart_count,
                warning=None if heart_present else "No heart rate data collected",
            )
        )

        # Vitals
        vitals_types = {"blood_oxygen", "respiratory_rate", "vo2_max", "body_temperature"}
        vitals_present = vitals_types & available_types
        vitals_count = sum(m.count for m in metric_types_raw if m.metric_type in vitals_types)
        collection_status.append(
            DataCollectionStatus(
                category="Vitals",
                has_data=len(vitals_present) > 0,
                metric_types=list(vitals_present),
                total_records=vitals_count,
                warning=None
                if vitals_present
                else "No vitals data - SpO2 and VO2 Max may need Apple Watch",
            )
        )

        # Mobility
        mobility_types = {
            "walking_speed",
            "step_length",
            "walking_asymmetry",
            "walking_double_support",
        }
        mobility_present = mobility_types & available_types
        mobility_count = sum(m.count for m in metric_types_raw if m.metric_type in mobility_types)
        collection_status.append(
            DataCollectionStatus(
                category="Mobility",
                has_data=len(mobility_present) > 0,
                metric_types=list(mobility_present),
                total_records=mobility_count,
            )
        )

        # Nutrition
        nutrition_types = {
            "dietary_energy",
            "protein",
            "carbohydrates",
            "total_fat",
            "water",
            "vitamin_a",
            "vitamin_c",
            "vitamin_d",
            "calcium",
            "iron",
        }
        nutrition_present = nutrition_types & available_types
        nutrition_count = sum(m.count for m in metric_types_raw if m.metric_type in nutrition_types)
        collection_status.append(
            DataCollectionStatus(
                category="Nutrition",
                has_data=len(nutrition_present) > 0,
                metric_types=list(nutrition_present),
                total_records=nutrition_count,
            )
        )

        # Check for missing data
        if total_workouts == 0:
            warnings.append("No workout data - enable Workouts export in Health Auto Export app")
        if total_sleep == 0:
            warnings.append("No sleep data - enable Sleep export in Health Auto Export app")

        return HealthDiagnosticsResponse(
            total_metrics=total_metrics,
            total_workouts=total_workouts,
            total_sleep_records=total_sleep,
            total_body_measurements=total_body,
            data_range_start=date_range.min if date_range else None,
            data_range_end=date_range.max if date_range else None,
            metric_types=metric_types,
            collection_status=collection_status,
            missing_data_warnings=warnings,
        )


# Singleton instance
_health_service: Optional[HealthService] = None


def get_health_service() -> HealthService:
    """Get or create the singleton health service."""
    global _health_service
    if _health_service is None:
        _health_service = HealthService()
    return _health_service
