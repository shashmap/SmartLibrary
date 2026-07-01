import os
import random
import csv
import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from library.models import SyntheticDataset

class Command(BaseCommand):
    help = "Generates a realistic synthetic dataset of 500,000+ smartphone health records for ML training"

    def handle(self, *args, **options):
        self.stdout.write("Starting synthetic dataset generation...")

        # Setup directory
        media_dir = os.path.join(settings.BASE_DIR, 'media')
        if not os.path.exists(media_dir):
            os.makedirs(media_dir)
        
        file_path = os.path.join(media_dir, 'synthetic_dataset.csv')

        num_records = 505000  # Over 500,000 records
        
        brands = [
            "Samsung", "Google Pixel", "OnePlus", "Xiaomi", "Realme", 
            "Vivo", "Oppo", "Nothing", "Motorola", "Nokia", 
            "Honor", "Infinix", "Tecno", "Lava", "Asus", "Sony"
        ]
        
        models_by_brand = {
            "Samsung": ["Galaxy S23", "Galaxy S22", "Galaxy A54", "Galaxy A34", "Galaxy Flip 5"],
            "Google Pixel": ["Pixel 7 Pro", "Pixel 7", "Pixel 6a", "Pixel 8 Pro", "Pixel 7a"],
            "OnePlus": ["OnePlus 11", "OnePlus 10T", "OnePlus Nord 3", "OnePlus 11R"],
            "Xiaomi": ["Redmi Note 12", "Xiaomi 13 Pro", "Poco F5", "Redmi 12C"],
            "Realme": ["Realme 11 Pro", "Realme C55", "Realme GT Neo 5"],
            "Vivo": ["Vivo V27", "Vivo Y36", "Vivo X90 Pro"],
            "Oppo": ["Reno 10 Pro", "Oppo A78", "Find X6 Pro"],
            "Nothing": ["Phone (1)", "Phone (2)"],
            "Motorola": ["Edge 40", "G84", "Razr 40 Ultra"],
            "Nokia": ["Nokia G22", "Nokia X30", "Nokia C32"],
            "Honor": ["Honor 90", "Honor Magic 5 Pro"],
            "Infinix": ["Zero 30", "Hot 30i", "Note 30 Pro"],
            "Tecno": ["Camon 20", "Pova 5 Pro"],
            "Lava": ["Agni 2", "Yuva 2 Pro"],
            "Asus": ["Zenfone 10", "ROG Phone 7"],
            "Sony": ["Xperia 1 V", "Xperia 5 V"]
        }

        # Generate vectors using numpy
        np.random.seed(42)
        
        self.stdout.write("Generating features...")
        
        # 1. Base device parameters
        brand_indices = np.random.randint(0, len(brands), size=num_records)
        brand_array = np.array(brands)[brand_indices]
        
        # Map models based on brand index
        # To make it vectorized, we can generate a random index for the models
        model_array = []
        for b in brand_array:
            model_array.append(random.choice(models_by_brand[b]))
        model_array = np.array(model_array)
        
        device_age = np.random.uniform(1.0, 48.0, size=num_records) # 1 to 48 months
        charging_cycles = (device_age * np.random.uniform(15, 35, size=num_records)).astype(int) # ~15-35 cycles per month
        
        # 2. Battery telemetry
        battery_health = 100 - (charging_cycles * np.random.uniform(0.02, 0.05, size=num_records))
        # Add random degradation factor
        battery_health -= np.random.exponential(scale=2.0, size=num_records)
        battery_health = np.clip(battery_health, 40, 100).astype(int)
        
        cpu_temp = np.random.normal(loc=36.0, scale=4.0, size=num_records)
        battery_temp = np.random.normal(loc=32.0, scale=3.0, size=num_records)
        
        # 3. Charging & Usage telemetry
        charging_duration = np.random.uniform(30.0, 150.0, size=num_records) # minutes
        charging_speed = np.random.uniform(10.0, 120.0, size=num_records) # Watts
        battery_drain = np.random.uniform(3.0, 15.0, size=num_records) + (100 - battery_health) * 0.15 # % per hour
        
        # 4. Failures & Stability indicators
        restart_freq = np.random.poisson(lam=0.5, size=num_records) # average 0.5 per month
        unexpected_shutdowns = np.random.poisson(lam=0.2, size=num_records)
        
        storage_usage = np.random.uniform(10.0, 95.0, size=num_records)
        ram_usage = np.random.uniform(20.0, 90.0, size=num_records)
        cpu_usage = np.random.uniform(10.0, 85.0, size=num_records)
        
        wifi_stability = np.random.uniform(0.7, 1.0, size=num_records)
        bluetooth_stability = np.random.uniform(0.8, 1.0, size=num_records)
        network_stability = np.random.uniform(0.75, 1.0, size=num_records)
        
        # Diagnostic tests results (0=Pass, 1=Fail)
        camera_fail = np.random.choice([0, 1], size=num_records, p=[0.97, 0.03])
        speaker_fail = np.random.choice([0, 1], size=num_records, p=[0.96, 0.04])
        mic_fail = np.random.choice([0, 1], size=num_records, p=[0.96, 0.04])
        charging_fail = np.random.choice([0, 1], size=num_records, p=[0.98, 0.02])
        touch_fail = np.random.choice([0, 1], size=num_records, p=[0.97, 0.03])
        sensor_fail = np.random.choice([0, 1], size=num_records, p=[0.98, 0.02])
        
        # History
        drops = np.random.poisson(lam=1.2, size=num_records)
        liquid_damage = np.random.choice([0, 1], size=num_records, p=[0.92, 0.08])
        repairs = np.random.poisson(lam=0.3, size=num_records)
        
        self.stdout.write("Injecting failures and target labels based on hardware rules...")
        
        # Define multi-class outputs
        # Classes: 0=Healthy, 1=Battery, 2=PMIC, 3=Motherboard, 4=Charging IC, 5=Display
        labels = np.zeros(num_records, dtype=int)
        
        # 1. Battery Failure conditions: low health, high cycles, high temp
        bat_fail_cond = (battery_health < 72) | (charging_cycles > 800) | (battery_temp > 46.0) & (np.random.rand(num_records) < 0.4)
        labels[bat_fail_cond] = 1
        
        # 2. Charging IC Failure: charging failures, high cycles, slow charging, battery sags
        charging_ic_fail_cond = (charging_fail == 1) & (charging_speed < 15.0) | (charging_duration > 140.0) & (np.random.rand(num_records) < 0.35)
        labels[charging_ic_fail_cond] = 4
        
        # 3. PMIC Failure: high temperatures, liquid damage, unexpected shutdowns, charging voltage spikes
        pmic_fail_cond = (unexpected_shutdowns > 3) & (battery_temp > 44.0) | (liquid_damage == 1) & (cpu_temp > 68.0) & (np.random.rand(num_records) < 0.45)
        labels[pmic_fail_cond] = 2
        
        # 4. Display Failure: touch fail, high drop count, liquid damage
        display_fail_cond = (touch_fail == 1) | (drops > 4) & (np.random.rand(num_records) < 0.5)
        labels[display_fail_cond] = 5
        
        # 5. Motherboard Failure (catastrophic): CPU temp extremely high, network/wifi fail, high restart frequency, drop + liquid
        motherboard_fail_cond = (cpu_temp > 75.0) | (restart_freq > 5) | (wifi_stability < 0.75) & (bluetooth_stability < 0.75) & (np.random.rand(num_records) < 0.5)
        labels[motherboard_fail_cond] = 3
        
        # Map back to binary indicator columns for database representation
        label_motherboard = (labels == 3).astype(int)
        label_charging_ic = (labels == 4).astype(int)
        label_pmic = (labels == 2).astype(int)
        label_capacitor = ((labels == 3) & (np.random.rand(num_records) < 0.4)).astype(int) # capacitor fails are a subset of motherboard failures
        label_battery = (labels == 1).astype(int)
        label_display = (labels == 5).astype(int)
        label_healthy = (labels == 0).astype(int)
        
        # Ensure consistency: if any label is 1, healthy is 0
        any_failure = label_motherboard | label_charging_ic | label_pmic | label_battery | label_display
        label_healthy[any_failure == 1] = 0
        label_healthy[any_failure == 0] = 1

        self.stdout.write("Assembling dataframe...")
        df = pd.DataFrame({
            'brand': brand_array,
            'model': model_array,
            'device_age': device_age,
            'charging_cycles': charging_cycles,
            'battery_health': battery_health,
            'cpu_temperature': cpu_temp,
            'battery_temperature': battery_temp,
            'charging_duration': charging_duration,
            'charging_speed': charging_speed,
            'battery_drain_rate': battery_drain,
            'restart_frequency': restart_freq,
            'unexpected_shutdowns': unexpected_shutdowns,
            'storage_usage': storage_usage,
            'ram_usage': ram_usage,
            'cpu_usage': cpu_usage,
            'wifi_stability': wifi_stability,
            'bluetooth_stability': bluetooth_stability,
            'network_stability': network_stability,
            'camera_failure': camera_fail,
            'speaker_failure': speaker_fail,
            'microphone_failure': mic_fail,
            'charging_failure': charging_fail,
            'touch_failure': touch_fail,
            'sensor_failure': sensor_fail,
            'physical_drop_history': drops,
            'liquid_damage_history': liquid_damage,
            'repair_history': repairs,
            'failure_label': labels, # 0=Healthy, 1=Battery, 2=PMIC, 3=Motherboard, 4=Charging IC, 5=Display
            'motherboard_failure': label_motherboard,
            'charging_ic_failure': label_charging_ic,
            'pmic_failure': label_pmic,
            'capacitor_failure': label_capacitor,
            'battery_failure': label_battery,
            'display_failure': label_display,
            'healthy_device': label_healthy
        })
        
        self.stdout.write(f"Writing to CSV at: {file_path}")
        df.to_csv(file_path, index=False)
        
        # Create record in Database
        db_record, created = SyntheticDataset.objects.get_or_create(
            file_path=file_path,
            defaults={'record_count': num_records}
        )
        if not created:
            db_record.record_count = num_records
            db_record.created_at = timezone.now()
            db_record.save()
            
        self.stdout.write(self.style.SUCCESS(f"Successfully generated {num_records} records!"))
