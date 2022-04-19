from urllib.parse import urlparse, parse_qs
from pathlib import Path
from typing import Optional, List

from django.conf import settings
from django.db.models import F
from django.http import Http404

from celery.result import AsyncResult


from .models import YoutubeVideo

# TODO ! TypedDict for return type
def get_videos(video_ids:Optional[List[str]]=None):

    # if no video_ids passed, get info about all videos
    initial_qs = YoutubeVideo.objects.all()
    
    # otherwise filter by ids
    if video_ids:
        initial_qs = initial_qs.filter(video_id__in=video_ids)
    
    # get tasks for poling
    # TODO убать values, сделать с only() и annotate()
    task_ids = initial_qs \
        .values("video_id", "dn_status", task_id=F("dn_last_task_id"), )
    
    # get result
    def res_func(e):
        # TODO !!! переписать
        return (
            AsyncResult(e["task_id"]) if e["task_id"] else None, 
            e["video_id"], 
            e["dn_status"],
            e["task_id"]
        )

    def clean_result(result):
        if not result:
            return None
        if not isinstance(result.result, dict):
            return str(result.result)
        else:
            return result.result
    
    # TODO !! переписать
    data = [ 
        {
            "video_id": video_id,
            "dn_status": dn_status,
            "task_state" : result and result.state,
            "task_id": task_id,
            "result" : clean_result(result)    
        } for result, video_id, dn_status, task_id in map(res_func, task_ids)
        
    ]

    return data


def get_video(video_id):

    videos = get_videos([video_id])

    return videos[0] if videos else None


def get_video_id_from_url(url:str) -> Optional[str]:
    parsed_url = urlparse(url)
        
    qs_dict = parse_qs(parsed_url.query)

    if "v" in qs_dict:
        return qs_dict["v"][0]
    else:
        return None


def check_video_exists(video_id:str, raise_404=False) -> bool:
    exists = YoutubeVideo.objects.filter(pk=video_id).only("pk").exists()
    
    if raise_404 and not exists:
        raise Http404("video with given id not found")
    return exists


def check_affected_rows(rows:int, expected:Optional[int]=1) -> bool:
    if expected is None:
        return True
    
    return rows == expected


def get_download_folder() -> Path:
    return settings.MEDIA_ROOT


class VideoStatusHelper:
    
    @staticmethod
    def set_status_in_progress(video_id:str, task_id:str)->bool:
        
        return check_affected_rows(
            YoutubeVideo.objects.filter(pk=video_id, dn_status__in=[0,2,3]) \
                .update(
                dn_status=1,
                dn_last_task_id=task_id
            )
        ) 


    @staticmethod
    def set_status_failed(video_id:str, error=None) -> bool:
        return check_affected_rows(
            YoutubeVideo.objects.filter(pk=video_id).update(dn_status=3)
        )
    
    @staticmethod
    def set_status_completed(video_id:str, filename:str) -> bool:
        return check_affected_rows(
            YoutubeVideo.objects.filter(pk=video_id).update(
                dn_status=2,
                filename=filename
            )
        )
    
    @staticmethod
    def clear_status(video_id:str) -> bool:
        return check_affected_rows(
            YoutubeVideo.objects.filter(pk=video_id).update(dn_status=0)
        )