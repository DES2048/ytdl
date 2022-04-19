from django.db import models


class DnStatus(models.IntegerChoices):
    NOT_DN=0
    IN_PROGRESS=1
    COMPLETE=2
    FAILED=3


class YoutubeVideo(models.Model):
    video_id = models.CharField(max_length=26, primary_key=True)
    video_url = models.URLField(max_length=256)

    # where file is stored n fs
    filename = models.FileField(max_length=120, null=True, blank=True)

    dn_status = models.IntegerField(
        choices=DnStatus.choices,
        default=DnStatus.NOT_DN
    )

    # task id that performs or performed video download
    dn_last_task_id=models.CharField(max_length=120,null=True,blank=True)
