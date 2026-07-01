import os
import sys
from django.apps import AppConfig

class LibraryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'library'

    def ready(self):
        # Import signals to register them
        import library.signals

        # Start the background task scheduler if this is the runserver command
        if 'runserver' in sys.argv:
            # Ensure it only runs once under Django's auto-reloader
            if os.environ.get('RUN_MAIN') == 'true' or '--noreload' in sys.argv:
                from library.tasks import start_scheduler
                start_scheduler()
