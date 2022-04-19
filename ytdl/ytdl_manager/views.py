import os
import uuid
from django.http import Http404

from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView

from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status as status_codes

from .forms import AddVideoByUrlForm
from .models import YoutubeVideo, DnStatus
from .tasks import download_video as dn_video_task, stop_download_task
from .services import check_video_exists, VideoStatusHelper, get_videos, get_video
from .serializers import (DownloadStatusSerializer, VideoAddByURLSerializer, 
    VideoListSerializer)


def manager(request):
    ''' index view для приложения '''
    
    return render(request, "ytdl_manager/manager_vue.html")


@api_view(["POST"])
def get_dn_status(request):

    # serializes task ids
    serializer = DownloadStatusSerializer(data=request.data)

    if serializer.is_valid():
        
        data = get_videos(serializer.validated_data.get("video_ids"))

        return Response(data=data)
    else:
        return Response(serializer.errors, status=status_codes.HTTP_400_BAD_REQUEST)
    

@api_view(["GET"])
def get_video_detail(request, video_id:str):
    
    check_video_exists(video_id, raise_404=True)
    
    video = get_video(video_id)
    
    if not video:
        raise Http404

    return Response(video)


@api_view(["POST"])
def download_video(request, video_id:str):
    # TODO more strict validating video_id
    
    check_video_exists(video_id, raise_404=True)
        
    ''' чтобы обеспеспечить создание только одной задачи на загрузку, при множественных
        вызовах view, необходимо у видео установить статус in progress. Чтобы исбежать
        race condition, используется идея, схожая с compare and swap. Т.е пытаемся обновить
        статус и если это удается, значит можно стартовать задачу, иначе же вернем id
        уже созданной задачи. Так же для избежания data race id задачи генерим заранее
    '''

    # TODO возможно создавать по одному фикс. наименованию на загрузку
    # по шаблону {video_id}:download_video
    task_id = str(uuid.uuid4())
    
    status=status_codes.HTTP_202_ACCEPTED # optimistic path :)


    # cas lock
    if VideoStatusHelper.set_status_in_progress(video_id, task_id):
        try:
            task = dn_video_task.apply_async(args=(video_id,), task_id=task_id)
        except Exception as ex:
            # set task status to failed
            VideoStatusHelper.set_status_failed(video_id)
            # TODO to status 500
            raise ex
    # already locked    
    else:
        task_id = YoutubeVideo.objects.get(pk=video_id).dn_last_task_id
        status=status_codes.HTTP_200_OK
    
    return Response(
        data={},
        status=status
    )

@api_view(['POST'])
def stop_download(request, video_id:str):
    
    check_video_exists(video_id, raise_404=True)

    video_status = get_video(video_id)

    if not video_status["dn_status"] == DnStatus.IN_PROGRESS:

        return Response(
            data={"message": "video must be in progress status"},
            status=status_codes.HTTP_400_BAD_REQUEST
        )
    
    # stopping task
    stop_download_task(video_status["task_id"])

    # delete file
    obj = YoutubeVideo.objects.filter(pk=video_id).only("filename").first()

    file_to_delete = obj.filename.path+".part" if obj.filename else None

    if not file_to_delete:
        return Response(data={})

    if os.path.exists(file_to_delete):
        os.remove(file_to_delete)
    
    return Response(data={})


# not use
class AddYoutubeVideoView(CreateView):
    form_class = AddVideoByUrlForm
    success_url = reverse_lazy("ytdl-manager")


class VideoListCreateApiView(ListCreateAPIView):
    
    serializer_class = VideoListSerializer
    queryset = YoutubeVideo.objects.all()

    def list(self, request, *args, **kwargs):
        # call without param returns all videos with theur statuses
        data = get_videos()
        return Response(data)

    def get_serializer_class(self):
        # for adding video using apropriate serializer
        if self.request.method == "POST":
            return VideoAddByURLSerializer
        else:
            return super().get_serializer_class()