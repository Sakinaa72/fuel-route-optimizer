import math

from django.conf import settings
from rest_framework import serializers


class CoordinatesSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)


class LocationField(serializers.Field):
    def to_internal_value(self, data):
        if isinstance(data, str):
            value = data.strip()
            if not 2 <= len(value) <= 300 or not any(character.isalpha() for character in value):
                raise serializers.ValidationError("Use a nonempty US location/address of 2–300 characters.")
            return value
        if isinstance(data, dict):
            if set(data) != {"latitude", "longitude"}:
                raise serializers.ValidationError("Coordinates require exactly latitude and longitude.")
            if any(isinstance(v, bool) for v in data.values()):
                raise serializers.ValidationError("Coordinates must be finite numbers.")
            serializer = CoordinatesSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            if not all(math.isfinite(v) for v in serializer.validated_data.values()):
                raise serializers.ValidationError("Coordinates must be finite numbers.")
            return serializer.validated_data
        raise serializers.ValidationError("Use an address string or a latitude/longitude object.")


class PlanRequestSerializer(serializers.Serializer):
    start = LocationField()
    finish = LocationField()
    max_range_miles = serializers.FloatField(default=500, min_value=1, max_value=1000)
    miles_per_gallon = serializers.FloatField(default=10, min_value=1, max_value=100)
    max_station_detour_miles = serializers.FloatField(
        default=lambda: settings.MAX_STATION_DETOUR_MILES, min_value=0, max_value=50
    )

    def validate(self, attrs):
        unknown = set(self.initial_data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({name: "Unknown field." for name in sorted(unknown)})
        for key in ("max_range_miles", "miles_per_gallon", "max_station_detour_miles"):
            if isinstance(self.initial_data.get(key), bool) or not math.isfinite(attrs[key]):
                raise serializers.ValidationError({key: "Must be a finite number."})
        return attrs
