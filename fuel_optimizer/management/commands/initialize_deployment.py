import json

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from fuel_optimizer.models import CityCoordinate, FuelStation


class Command(BaseCommand):
    help = "Initialize empty reference/price data from public local archives and a private runtime CSV."

    def handle(self, *args, **options):
        if not CityCoordinate.objects.exists():
            call_command("prepare_locations", stdout=self.stdout)
        if FuelStation.objects.exists() and not settings.REFRESH_FUEL_PRICES:
            self.stdout.write(
                json.dumps({"event": "fuel_data_preserved", "records": FuelStation.objects.count()})
            )
        elif settings.FUEL_PRICES_CSV.is_file():
            call_command("load_fuel_prices", csv=str(settings.FUEL_PRICES_CSV), stdout=self.stdout)
        else:
            self.stdout.write(
                json.dumps(
                    {
                        "event": "fuel_data_missing",
                        "action": "Add the private CSV as a runtime secret file, configure FUEL_CSV_PATH and redeploy.",
                        "existing_records": FuelStation.objects.count(),
                    }
                )
            )
