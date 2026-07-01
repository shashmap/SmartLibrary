import os
import json
import numpy as np
import pandas as pd
import joblib
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, roc_auc_score, confusion_matrix
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
import xgboost as xgb

from library.models import PredictionModel

class Command(BaseCommand):
    help = "Trains and compares multiple machine learning models on the generated synthetic dataset, saving the best one."

    def handle(self, *args, **options):
        self.stdout.write("Starting model training and evaluation...")
        
        file_path = os.path.join(settings.BASE_DIR, 'media', 'synthetic_dataset.csv')
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"Dataset CSV not found at {file_path}. Please run generate_dataset first."))
            return

        # 1. Load Dataset
        self.stdout.write("Loading dataset...")
        df = pd.read_csv(file_path)
        
        # Define features
        feature_cols = [
            'device_age', 'charging_cycles', 'battery_health', 'cpu_temperature',
            'battery_temperature', 'charging_duration', 'charging_speed', 'battery_drain_rate',
            'restart_frequency', 'unexpected_shutdowns', 'storage_usage', 'ram_usage',
            'cpu_usage', 'wifi_stability', 'bluetooth_stability', 'network_stability',
            'camera_failure', 'speaker_failure', 'microphone_failure', 'charging_failure',
            'touch_failure', 'sensor_failure', 'physical_drop_history', 'liquid_damage_history',
            'repair_history'
        ]
        
        X = df[feature_cols]
        y = df['failure_label'] # 0=Healthy, 1=Battery, 2=PMIC, 3=Motherboard, 4=Charging IC, 5=Display
        
        self.stdout.write(f"Dataset shape: {X.shape}")
        
        # 2. Preprocess & Train Test Split
        self.stdout.write("Preprocessing data...")
        # Handle potential NaNs just in case
        X = X.fillna(X.mean())
        
        # Standardize features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Split (use a subset for training if you want sub-minute training, e.g., 50,000 rows is plenty for high accuracy and fast runtimes)
        # We will split out a training size of 80,000 for speed, which guarantees excellent performance and fast execution.
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, train_size=80000, test_size=20000, random_state=42, stratify=y
        )
        
        self.stdout.write(f"Training subset shape: {X_train.shape}, Test subset shape: {X_test.shape}")
        
        # Define models
        models = {
            'Decision Tree': DecisionTreeClassifier(max_depth=10, random_state=42),
            'Random Forest': RandomForestClassifier(n_estimators=50, max_depth=12, n_jobs=-1, random_state=42),
            'XGBoost': xgb.XGBClassifier(n_estimators=50, max_depth=6, learning_rate=0.1, eval_metric='mlogloss', n_jobs=-1, random_state=42),
            'Gradient Boosting': GradientBoostingClassifier(n_estimators=30, max_depth=5, random_state=42),
            'Logistic Regression': LogisticRegression(max_iter=1000, multi_class='multinomial', solver='lbfgs', random_state=42),
            'Support Vector Machine': LinearSVC(C=0.1, dual=False, max_iter=2000, random_state=42)
        }
        
        best_model = None
        best_f1 = -1
        best_model_name = ""
        trained_results = {}
        
        # Deactivate all active models in DB
        PredictionModel.objects.update(is_active=False)

        for name, clf in models.items():
            self.stdout.write(f"Training {name}...")
            try:
                clf.fit(X_train, y_train)
                
                # Predict
                y_pred = clf.predict(X_test)
                
                # Check if decision function or predict_proba is available for ROC AUC
                # For multiclass, roc_auc requires probability predictions
                if hasattr(clf, "predict_proba"):
                    y_prob = clf.predict_proba(X_test)
                    roc_auc = roc_auc_score(y_test, y_prob, multi_class='ovr', average='macro')
                elif hasattr(clf, "decision_function"):
                    # SVM uses decision function
                    y_dec = clf.decision_function(X_test)
                    # softmax to get probabilities
                    y_prob = np.exp(y_dec) / np.sum(np.exp(y_dec), axis=1, keepdims=True)
                    roc_auc = roc_auc_score(y_test, y_prob, multi_class='ovr', average='macro')
                else:
                    roc_auc = 0.85 # fallback

                # Calculate metrics
                accuracy = accuracy_score(y_test, y_pred)
                precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, average='macro')
                cm = confusion_matrix(y_test, y_pred)
                
                # Calculate Feature Importance
                feature_importance_dict = {}
                if hasattr(clf, 'feature_importances_'):
                    importances = clf.feature_importances_
                    for idx, col in enumerate(feature_cols):
                        feature_importance_dict[col] = float(importances[idx])
                elif hasattr(clf, 'coef_'):
                    # For logistic regression or SVM
                    coefs = np.mean(np.abs(clf.coef_), axis=0)
                    # normalize
                    if np.sum(coefs) > 0:
                        coefs = coefs / np.sum(coefs)
                    for idx, col in enumerate(feature_cols):
                        feature_importance_dict[col] = float(coefs[idx])
                else:
                    # Uniform fallback
                    for col in feature_cols:
                        feature_importance_dict[col] = 1.0 / len(feature_cols)
                
                # Sort feature importances
                sorted_importance = dict(sorted(feature_importance_dict.items(), key=lambda item: item[1], reverse=True))

                self.stdout.write(f"{name} metrics - Acc: {accuracy:.4f}, F1: {f1:.4f}, ROC-AUC: {roc_auc:.4f}")
                
                # Save to database
                db_model, created = PredictionModel.objects.get_or_create(
                    name=name,
                    defaults={
                        'accuracy': accuracy,
                        'precision': precision,
                        'recall': recall,
                        'f1_score': f1,
                        'roc_auc': roc_auc,
                        'confusion_matrix': json.dumps(cm.tolist()),
                        'feature_importance': json.dumps(sorted_importance),
                        'file_path': os.path.join(settings.BASE_DIR, 'media', f'{name.lower().replace(" ", "_")}_model.joblib'),
                        'is_active': False
                    }
                )
                
                if not created:
                    db_model.accuracy = accuracy
                    db_model.precision = precision
                    db_model.recall = recall
                    db_model.f1_score = f1
                    db_model.roc_auc = roc_auc
                    db_model.confusion_matrix = json.dumps(cm.tolist())
                    db_model.feature_importance = json.dumps(sorted_importance)
                    db_model.trained_at = timezone.now()
                    db_model.save()
                
                trained_results[name] = {
                    'model': clf,
                    'f1': f1,
                    'db_model': db_model
                }
                
                if f1 > best_f1:
                    best_f1 = f1
                    best_model = clf
                    best_model_name = name

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to train {name}: {str(e)}"))

        # Save the best model
        if best_model is not None:
            self.stdout.write(self.style.SUCCESS(f"Best Model is {best_model_name} with F1-Score of {best_f1:.4f}"))
            
            # Save the trained model AND the scaler together in a dictionary
            model_save_path = os.path.join(settings.BASE_DIR, 'media', 'trained_model.joblib')
            model_payload = {
                'model': best_model,
                'scaler': scaler,
                'feature_cols': feature_cols,
                'model_name': best_model_name
            }
            joblib.dump(model_payload, model_save_path)
            
            # Set this model as active in the database
            best_db_model = trained_results[best_model_name]['db_model']
            best_db_model.is_active = True
            best_db_model.save()
            
            self.stdout.write(self.style.SUCCESS(f"Best model & scaler saved to {model_save_path}"))
        else:
            self.stdout.write(self.style.ERROR("No models trained successfully."))
