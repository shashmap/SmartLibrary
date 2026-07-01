from library.models import Alert, Notification

class NotificationService:
    @staticmethod
    def process_telemetry_alerts(device, telemetry):
        """Analyzes a telemetry payload and creates Alerts/Notifications for severe conditions."""
        notifications = []
        alerts = []
        
        # 1. CPU Temp check
        if telemetry.get('cpu_temperature', 0) > 60.0:
            severity = 'critical' if telemetry['cpu_temperature'] > 70.0 else 'warning'
            alerts.append(Alert(
                device=device,
                severity=severity,
                title="Critical CPU Overheating",
                message=f"Processor temperature is dangerously high ({telemetry['cpu_temperature']:.1f}°C). Reduce workload immediately."
            ))
            notifications.append(Notification(
                user=device.owner,
                title="High CPU Temp Warning",
                message=f"Your device CPU temperature reached {telemetry['cpu_temperature']:.1f}°C. Cool down the device.",
                notification_type="warning"
            ))

        # 2. Battery Temp check
        if telemetry.get('battery_temperature', 0) > 43.0:
            alerts.append(Alert(
                device=device,
                severity='critical' if telemetry['battery_temperature'] > 48.0 else 'warning',
                title="High Battery Temperature",
                message=f"Battery temperature is {telemetry['battery_temperature']:.1f}°C. Stop charging or gaming."
            ))
            notifications.append(Notification(
                user=device.owner,
                title="Battery Overheating Warning",
                message=f"Battery reached {telemetry['battery_temperature']:.1f}°C. Disconnect charger.",
                notification_type="warning"
            ))

        # 3. Battery Health check
        if telemetry.get('battery_health', 100) < 80:
            alerts.append(Alert(
                device=device,
                severity='warning',
                title="Battery Health Below 80%",
                message=f"Battery capacity is degraded ({telemetry['battery_health']}%). Consider replacing the battery."
            ))
            notifications.append(Notification(
                user=device.owner,
                title="Battery Replacement Suggested",
                message=f"Your battery health has dropped to {telemetry['battery_health']}%. Run self-diagnostics to verify details.",
                notification_type="recommendation"
            ))

        # 4. Slow Charging check
        if telemetry.get('charging_speed', 0) < 5.0 and telemetry.get('charging_failure', 0) == 1:
            alerts.append(Alert(
                device=device,
                severity='warning',
                title="Extremely Slow Charging",
                message=f"Charging rate is very slow ({telemetry['charging_speed']:.1f} W). Verify cable connection or charging IC."
            ))

        # 5. Unexpected Restarts check
        if telemetry.get('restart_frequency', 0) > 3 or telemetry.get('unexpected_shutdowns', 0) > 2:
            alerts.append(Alert(
                device=device,
                severity='critical',
                title="Frequent Unexpected Restarts",
                message=f"System restarted unexpected {telemetry['restart_frequency']} times and shutdown {telemetry['unexpected_shutdowns']} times recently."
            ))
            notifications.append(Notification(
                user=device.owner,
                title="Motherboard Hardware Alert",
                message="Frequent spontaneous reboots detected. Backup files immediately and check motherboard health.",
                notification_type="warning"
            ))

        # 6. Test Failures check
        if telemetry.get('microphone_failure', 0) == 1:
            alerts.append(Alert(
                device=device,
                severity='warning',
                title="Microphone Failure Detected",
                message="Audio inputs failed self-diagnostic testing."
            ))
        if telemetry.get('speaker_failure', 0) == 1:
            alerts.append(Alert(
                device=device,
                severity='warning',
                title="Speaker Failure Detected",
                message="Audio outputs failed self-diagnostic testing."
            ))

        # Bulk create
        if alerts:
            Alert.objects.bulk_create(alerts)
        if notifications:
            Notification.objects.bulk_create(notifications)

        return alerts
