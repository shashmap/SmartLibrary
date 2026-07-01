import os
import joblib
import numpy as np
from django.conf import settings
from django.utils import timezone
from library.models import Device, PredictionModel, PredictionHistory, Alert

class PredictionService:
    @staticmethod
    def get_latest_telemetry(device):
        """Fetches the latest aggregated telemetry parameters for a device."""
        latest_record = device.health_records.first()
        battery_log = device.battery_health_logs.first()
        sensor_log = device.sensor_health_logs.first()
        
        # Default or fallback values
        telemetry = {
            'device_age': float(device.age_months),
            'charging_cycles': int(battery_log.charging_cycles) if battery_log else int(device.age_months * 25),
            'battery_health': int(battery_log.health_pct) if battery_log else (latest_record.battery_health_pct if latest_record else 95),
            'cpu_temperature': float(latest_record.cpu_temp) if latest_record else 37.0,
            'battery_temperature': float(latest_record.battery_temp) if latest_record else 32.0,
            'charging_duration': float(device.charging_records.first().duration_minutes) if device.charging_records.exists() else 75.0,
            'charging_speed': float(device.charging_records.first().charging_speed_w) if device.charging_records.exists() else 25.0,
            'battery_drain_rate': float(battery_log.drain_rate_pct_per_hour) if battery_log else 6.0,
            'restart_frequency': int(device.restart_history.filter(restart_type='unexpected_restart').count()),
            'unexpected_shutdowns': int(device.restart_history.filter(restart_type='unexpected_shutdown').count()),
            'storage_usage': float(latest_record.storage_usage_pct) if latest_record else 45.0,
            'ram_usage': float(latest_record.ram_usage_pct) if latest_record else 50.0,
            'cpu_usage': float(latest_record.cpu_usage_pct) if latest_record else 25.0,
            'wifi_stability': 0.95,
            'bluetooth_stability': 0.98,
            'network_stability': 0.92,
            'camera_failure': 1 if device.cameratest_set.filter(result='fail').exists() else 0,
            'speaker_failure': 1 if device.speakertest_set.filter(result='fail').exists() else 0,
            'microphone_failure': 1 if device.microphonetest_set.filter(result='fail').exists() else 0,
            'charging_failure': 1 if device.chargingtest_set.filter(result='fail').exists() else 0,
            'touch_failure': 1 if device.touchtest_set.filter(result='fail').exists() else 0,
            'sensor_failure': 0,
            'physical_drop_history': int(device.device_activities.filter(action__icontains='drop').count()),
            'liquid_damage_history': 1 if device.device_activities.filter(action__icontains='liquid').exists() else 0,
            'repair_history': int(device.repairs.count())
        }
        
        # Check sensor failure
        if sensor_log:
            if not (sensor_log.accelerometer and sensor_log.gyroscope and sensor_log.proximity and sensor_log.compass and sensor_log.light_sensor and sensor_log.gps):
                telemetry['sensor_failure'] = 1
                
        # Wifi and Bluetooth stability from logs
        wifi_log = device.wifistatus_set.first()
        if wifi_log and wifi_log.status == 'Disconnected':
            telemetry['wifi_stability'] = 0.65
        bluetooth_log = device.bluetoothstatus_set.first()
        if bluetooth_log and bluetooth_log.status == 'Failed':
            telemetry['bluetooth_stability'] = 0.70
            
        return telemetry

    @classmethod
    def predict_device_failure(cls, device):
        """Runs the machine learning prediction or rule-based fallback to evaluate failure probability."""
        telemetry = cls.get_latest_telemetry(device)
        model_save_path = os.path.join(settings.BASE_DIR, 'media', 'trained_model.joblib')
        
        active_db_model = PredictionModel.objects.filter(is_active=True).first()
        
        if os.path.exists(model_save_path) and active_db_model:
            try:
                # Load active model payload
                payload = joblib.load(model_save_path)
                model = payload['model']
                scaler = payload['scaler']
                feature_cols = payload['feature_cols']
                
                # Assemble feature vector
                vector = [telemetry[col] for col in feature_cols]
                vector_scaled = scaler.transform([vector])
                
                # Predict probabilities
                # Classes: 0=Healthy, 1=Battery, 2=PMIC, 3=Motherboard, 4=Charging IC, 5=Display
                probs = model.predict_proba(vector_scaled)[0]
                
                failure_prob = float(1.0 - probs[0])
                bat_risk = float(probs[1])
                pmic_risk = float(probs[2])
                mboard_risk = float(probs[3])
                charging_ic_risk = float(probs[4])
                display_risk = float(probs[5])
                
                # Custom storage risk approximation based on storage usage
                storage_risk = min(0.99, float(telemetry['storage_usage'] / 100.0) * 0.4 + (0.5 if telemetry['storage_usage'] > 90 else 0.0))
                
                # Overall Health Score (0-100)
                health_score = int(np.clip(100 - (failure_prob * 100), 0, 100))
                confidence = float(np.max(probs))
                
                # Identify Primary Issue
                risks = {
                    'Battery Wear': bat_risk,
                    'PMIC (Power Management)': pmic_risk,
                    'Motherboard / Mainboard': mboard_risk,
                    'Charging IC / Port': charging_ic_risk,
                    'Display / Touch Screen': display_risk,
                }
                
                primary_issue = "None"
                if failure_prob > 0.15:
                    primary_issue = max(risks, key=risks.get)
                    
                # Determine Risk Level
                if health_score >= 90:
                    risk_level = 'low'
                elif health_score >= 75:
                    risk_level = 'medium'
                elif health_score >= 50:
                    risk_level = 'high'
                else:
                    risk_level = 'critical'
                    
                # Save to database
                history = PredictionHistory.objects.create(
                    device=device,
                    prediction_model=active_db_model,
                    health_score=health_score,
                    risk_level=risk_level,
                    failure_probability=failure_prob,
                    pmic_risk=pmic_risk,
                    battery_risk=bat_risk,
                    motherboard_risk=mboard_risk,
                    charging_ic_risk=charging_ic_risk,
                    display_risk=display_risk,
                    storage_risk=storage_risk,
                    confidence=confidence,
                    primary_issue=primary_issue
                )
                
                # Sync Device Status
                cls.update_device_status(device, risk_level)
                return history

            except Exception as e:
                # Fallback to rule engine if prediction fails
                return cls.fallback_rule_engine(device, telemetry, active_db_model)
        else:
            # Fallback to rule engine
            return cls.fallback_rule_engine(device, telemetry, None)

    @classmethod
    def fallback_rule_engine(cls, device, telemetry, active_db_model):
        """High-fidelity rule-based fallback predictions when ML models are not trained yet."""
        bat_risk = 0.05
        pmic_risk = 0.05
        mboard_risk = 0.05
        charging_ic_risk = 0.05
        display_risk = 0.05
        storage_risk = min(0.95, float(telemetry['storage_usage'] / 100.0) * 0.3)

        # Apply Rules
        if telemetry['battery_health'] < 80:
            bat_risk += 0.35 + (80 - telemetry['battery_health']) * 0.02
        if telemetry['charging_cycles'] > 500:
            bat_risk += 0.20
        if telemetry['battery_temperature'] > 42.0:
            bat_risk += 0.15
            pmic_risk += 0.15

        if telemetry['unexpected_shutdowns'] > 0:
            pmic_risk += 0.25 + telemetry['unexpected_shutdowns'] * 0.10
            mboard_risk += 0.15
        if telemetry['cpu_temperature'] > 60.0:
            pmic_risk += 0.15
            mboard_risk += 0.20

        if telemetry['restart_frequency'] > 1:
            mboard_risk += 0.30
        if telemetry['liquid_damage_history'] == 1:
            mboard_risk += 0.40
            pmic_risk += 0.30
        if telemetry['physical_drop_history'] > 2:
            display_risk += 0.25
            mboard_risk += 0.15

        if telemetry['charging_failure'] == 1:
            charging_ic_risk += 0.50
        if telemetry['charging_speed'] < 10.0:
            charging_ic_risk += 0.20

        if telemetry['touch_failure'] == 1:
            display_risk += 0.60
        if telemetry['camera_failure'] == 1 or telemetry['speaker_failure'] == 1 or telemetry['microphone_failure'] == 1:
            mboard_risk += 0.15

        # Clip risks
        bat_risk = min(0.99, bat_risk)
        pmic_risk = min(0.99, pmic_risk)
        mboard_risk = min(0.99, mboard_risk)
        charging_ic_risk = min(0.99, charging_ic_risk)
        display_risk = min(0.99, display_risk)

        # Overall failure probability
        failure_prob = float(max(bat_risk, pmic_risk, mboard_risk, charging_ic_risk, display_risk))
        health_score = int(100 - (failure_prob * 100))
        
        # Risk level
        if health_score >= 90:
            risk_level = 'low'
        elif health_score >= 75:
            risk_level = 'medium'
        elif health_score >= 50:
            risk_level = 'high'
        else:
            risk_level = 'critical'

        # Primary issue mapping
        risks = {
            'Battery Wear': bat_risk,
            'PMIC (Power Management)': pmic_risk,
            'Motherboard / Mainboard': mboard_risk,
            'Charging IC / Port': charging_ic_risk,
            'Display / Touch Screen': display_risk,
        }
        primary_issue = "None"
        if failure_prob > 0.15:
            primary_issue = max(risks, key=risks.get)

        history = PredictionHistory.objects.create(
            device=device,
            prediction_model=active_db_model,
            health_score=health_score,
            risk_level=risk_level,
            failure_probability=failure_prob,
            pmic_risk=pmic_risk,
            battery_risk=bat_risk,
            motherboard_risk=mboard_risk,
            charging_ic_risk=charging_ic_risk,
            display_risk=display_risk,
            storage_risk=storage_risk,
            confidence=0.85, # static confidence for fallback rule engine
            primary_issue=primary_issue
        )

        cls.update_device_status(device, risk_level)
        return history

    @staticmethod
    def update_device_status(device, risk_level):
        """Updates the device state in DB based on predicted risk level."""
        device.current_status = risk_level
        device.save()
