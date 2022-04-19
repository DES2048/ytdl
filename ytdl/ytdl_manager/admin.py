from django.contrib import admin

from .models import YoutubeVideo

# Register your models here.
class YoutubeVideoAdmin(admin.ModelAdmin):
    list_display =("video_id", "dn_status", "dn_last_task_id")

admin.site.register(YoutubeVideo, YoutubeVideoAdmin)
