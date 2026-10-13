import json
import logging

from django.conf import settings


class JsonFormatter(logging.Formatter):
    def format(self, record):
        output = {"level": record.levelname, "logger": record.name, "event": record.getMessage()}
        for key in ("request_id", "duration_ms", "candidate_count", "stop_count"):
            if hasattr(record, key):
                output[key] = getattr(record, key)
        # Production logs expose exception types, not values or internal stack traces.
        if record.exc_info:
            if settings.DEBUG:
                output["exception"] = self.formatException(record.exc_info)
            else:
                output["exception_type"] = record.exc_info[0].__name__
        return json.dumps(output)
