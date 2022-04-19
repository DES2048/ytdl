from rest_framework import serializers

from .validators import validate_video_url

from .models import YoutubeVideo
from .services import get_video_id_from_url


class DownloadStatusSerializer(serializers.Serializer):
    
    video_ids = serializers.ListField(
        child=serializers.CharField()
    )

class VideoAddByURLSerializer(serializers.ModelSerializer):
    
    video_url = serializers.CharField(max_length=256, validators=[validate_video_url,])

    class Meta:
        model = YoutubeVideo
        fields = ("video_url",)

    def create(self, validated_data):
        video_url = validated_data["video_url"]
        
        return YoutubeVideo.objects.create(
            video_url=video_url,
            pk=get_video_id_from_url(video_url)
        )

class VideoListSerializer(serializers.ModelSerializer):
    
    dn_task_id = serializers.CharField(source="dn_last_task_id")

    class Meta:
        model = YoutubeVideo
        exclude = ("dn_last_task_id",)