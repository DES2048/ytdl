from django.urls import path

from . import views

# TODO ?videos views to viewset
urlpatterns = [
    path("", views.manager, name="ytdl-manager"), # index page
    path("videos/", views.VideoListCreateApiView.as_view(), name="list-video"),
    path("videos/<str:video_id>/", views.get_video_detail, name="get-video-detail"),
    path("videos/<str:video_id>/start-dn", views.download_video, name="start-dn-video"),
    path("videos/<str:video_id>/stop-dn", views.stop_download, name="stop-dn-video"),
    path("dn_status", views.get_dn_status, name="get-dn-status"),
]