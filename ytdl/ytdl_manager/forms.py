from urllib.parse import urlparse, parse_qs

from django import forms

from .validators import validate_video_url
from .models import YoutubeVideo
from .services import get_video_id_from_url


class AddVideoByUrlForm(forms.ModelForm):
    
    video_url = forms.CharField(
        max_length=256,
        validators=[validate_video_url,]
    )
    
    class Meta:
        model = YoutubeVideo
        fields = ("video_url",)
    
    def save(self, commit: bool = True) -> YoutubeVideo:
        
        self.instance.video_id = get_video_id_from_url(
            self.cleaned_data["video_url"]
        )

        return super().save(commit)
    