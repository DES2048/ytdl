from fileinput import filename
import signal
import time
from pathlib import Path
from typing import Callable, Optional, TypedDict
from typing_extensions import NotRequired

import youtube_dl

from celery import shared_task, Task
from celery.result import AsyncResult

from .models import YoutubeVideo

from .services import VideoStatusHelper, get_download_folder


def stop_download_task(task_id):
    res = AsyncResult(task_id)
    res.revoke(terminate=True)


class YtdlProgressState:
    DOWNLOADING = 'downloading'
    ERROR = 'error'
    FINISHED = 'finished'


class PassAllLogger(object):
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def dn_stub(delay:int):
    time.sleep(10)


class DownloadTask(Task):

    def run(self, video_id:str):
        pass    


def download_progress_callback(t:Task, status, video_id):
    
    set_filedata = False
    
    if not set_filedata and "filename" in status:
        #TODO Move to service
        YoutubeVideo.objects.filter(pk=video_id).update(
            filename=status["filename"]
        )
        set_filedata = True

    t.update_state(state='PROGRESS',        
        meta={
            **status 
        }
    )

class VideoDnResult(TypedDict):
    video_id:str
    status:str
    filename: NotRequired[str]
    error: NotRequired[Exception]


def download_yt_video(video_id:str, progress_callback:Optional[Callable]) -> VideoDnResult:
    
    dn_result:VideoDnResult = {
        "video_id": video_id,
        "status": YtdlProgressState.FINISHED,
    }
    
    set_filename = False

    # TODO check status error
    def status_hook(d):
        if progress_callback and d['status'] ==YtdlProgressState.DOWNLOADING:
            
            nonlocal set_filename
            
            if not set_filename:
                dn_result["filename"] = d["filename"]
                set_filename = True
            
            d.pop("status")
            
            progress_callback(d)
        # TODO process error state
        elif d['status'] == YtdlProgressState.FINISHED:
            
            dn_result["filename"] = Path(d["filename"]).name      
    

    # TODO standart filename tmpl trom ytdl
    ydl_opts = {
        "logger": PassAllLogger(),
        "progress_hooks": [status_hook,],
        "outtmpl": str(get_download_folder() / "%(title)s-%(id)s.%(ext)s"),
        "format": "[ext=mp4]"
    }
    
    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
    except Exception as e:
        dn_result["status"] = "failure"
        dn_result["error"] = e
    finally:    
        return dn_result

    
@shared_task(bind=True)
def download_video(self:Task, video_id:str) -> VideoDnResult:
    
    # when task is revoked, only way catch this event is catching SIGTERM signal
    def revoke_handler(sig, _):
        VideoStatusHelper.clear_status(video_id)
    
    signal.signal(signal.SIGTERM, revoke_handler)

    def prog_cb(status):
        download_progress_callback(self, status, video_id)

    dn_status: Optional[VideoDnResult] = None
    
    try:
        dn_status = download_yt_video(video_id, prog_cb)
    except Exception as e:
        VideoStatusHelper.set_status_failed(video_id)
        raise e

    if dn_status and dn_status["status"] == YtdlProgressState.FINISHED:
        # success
        filename = dn_status.get("filename")
        
        if filename is None:
            raise ValueError("filename in downloaded video is None")
        VideoStatusHelper.set_status_completed(video_id, filename)

    return dn_status
    
    

