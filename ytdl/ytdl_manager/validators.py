from urllib.parse import urlparse, parse_qs
from django.core.exceptions import ValidationError

from .services import get_video_id_from_url


def validate_video_url(value):
    
    if not get_video_id_from_url(value):
        raise ValidationError("URL must contain v attribute in query string", code="invalid")
