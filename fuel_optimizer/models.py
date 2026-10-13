from django.db import models


class CityCoordinate(models.Model):
    geoid = models.CharField(max_length=16, unique=True)
    city = models.CharField(max_length=160)
    normalized_city = models.CharField(max_length=160)
    state = models.CharField(max_length=2)
    latitude = models.FloatField()
    longitude = models.FloatField()
    source = models.CharField(max_length=80, default="census_gazetteer_2025")

    class Meta:
        indexes = [models.Index(fields=["state", "normalized_city"])]


class FuelStation(models.Model):
    # SHA-256 of the seven normalized source values, including price.
    record_key = models.CharField(max_length=64, unique=True)
    source_truckstop_id = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=240)
    address = models.CharField(max_length=300)
    city = models.CharField(max_length=160, db_index=True)
    normalized_city = models.CharField(max_length=160)
    state = models.CharField(max_length=2, db_index=True)
    rack_id = models.CharField(max_length=64, blank=True)
    retail_price = models.DecimalField(max_digits=12, decimal_places=8, db_index=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    coordinate_source = models.CharField(max_length=40, default="unresolved")
    coordinate_reference = models.CharField(max_length=80, blank=True)
    imported_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["state", "normalized_city"]),
            models.Index(fields=["latitude", "longitude"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(retail_price__gt=0), name="positive_retail_price")
        ]


class CachedGeocoding(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    payload = models.JSONField()
    expires_at = models.DateTimeField()


class CachedRoute(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    payload = models.JSONField()
    expires_at = models.DateTimeField()
