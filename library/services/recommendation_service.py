from library.models import Recommendation, PredictionHistory

class RecommendationService:
    @staticmethod
    def generate_recommendations(device, prediction_history):
        """Analyzes a prediction history run and inserts recommendations in the database."""
        # Deactivate old recommendations for this device
        Recommendation.objects.filter(device=device, is_active=True).update(is_active=False)
        
        recs = []

        # 1. Motherboard Risk Recommendation
        if prediction_history.motherboard_risk > 0.40:
            recs.append(Recommendation(
                device=device,
                title="Critical Motherboard Degradation Warning",
                action_steps="- **Backup Data Immediately**: Your motherboard shows high instability due to thermal stresses or component wear. Connect to cloud or PC and save photos, contacts, and tokens.\n- **Visit Authorized Service Center**: Have a technician inspect the solder joints and main processor stability.\n- **Avoid Heavy Loads**: Do not play graphics-intensive games or run benchmarks.",
                priority='high'
            ))

        # 2. PMIC Risk Recommendation
        if prediction_history.pmic_risk > 0.40:
            recs.append(Recommendation(
                device=device,
                title="PMIC (Power Management) Thermal Guidance",
                action_steps="- **Avoid Charging While Gaming**: This puts dual thermal stress on the PMIC chip and battery.\n- **Use Original Chargers**: Third-party chargers with unstable voltage can damage the power delivery chip.\n- **Cool Down**: If the phone feels hot, unplug the charger and let it rest in a cool place.",
                priority='high'
            ))

        # 3. Battery Risk Recommendation
        if prediction_history.battery_risk > 0.40:
            priority = 'high' if prediction_history.battery_risk > 0.70 else 'medium'
            recs.append(Recommendation(
                device=device,
                title="Battery Replacement Recommendation",
                action_steps=f"- **Replace Battery Soon**: The current capacity or degradation index indicates it is worn out.\n- **Avoid Extreme Charges**: Try to keep charging between 20% and 80% to prolong remaining lifespan.\n- **Keep Temperature Low**: High heat accelerated degradation. Avoid dashboard phone mounts in direct sunlight.",
                priority=priority
            ))

        # 4. Charging IC Risk Recommendation
        if prediction_history.charging_ic_risk > 0.40:
            recs.append(Recommendation(
                device=device,
                title="Charging Port & Charging IC Maintenance",
                action_steps="- **Inspect Charging Port**: Clean any pocket lint or debris carefully with a wooden toothpick.\n- **Use Standard Cables**: Avoid cheap, frayed, or bent charging cables.\n- **Check Voltage Sags**: Use a different power socket or adapter to rule out input power fluctuations.",
                priority='medium'
            ))

        # 5. Display Risk Recommendation
        if prediction_history.display_risk > 0.40:
            recs.append(Recommendation(
                device=device,
                title="Display & Digitizer Calibration check",
                action_steps="- **Remove Screen Protector**: Sometimes unresponsive touch is caused by a thick, air-bubbled, or cracked glass protector.\n- **Inspect Screen Glass**: If cracked, moisture ingress can destroy the display grid. Consider a replacement.",
                priority='medium'
            ))

        # 6. Storage Risk Recommendation
        if prediction_history.storage_risk > 0.80:
            recs.append(Recommendation(
                device=device,
                title="Storage Clean Up Required",
                action_steps="- **Free Up Storage**: Your phone has less than 15% storage space. Full storage slows down SQLite databases and can cause system bootloops.\n- **Clear Cache Files**: Go to system settings and clear temporary caches.\n- **Transfer Data**: Move large videos and photos to cloud storage.",
                priority='medium'
            ))

        # Default recommendation if device is healthy
        if not recs:
            recs.append(Recommendation(
                device=device,
                title="Healthy Device Status maintained",
                action_steps="- **Continue Monitoring**: Run diagnostic self-tests monthly.\n- **Firmware Updates**: Keep your device updated with the manufacturer's security patches.\n- **Safe Workloads**: Keep heavy gaming sessions under 45 minutes to prevent long thermal saturation.",
                priority='low'
            ))

        # Bulk create recommendations in DB
        Recommendation.objects.bulk_create(recs)
        return recs
