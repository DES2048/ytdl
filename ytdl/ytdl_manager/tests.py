import json
from unittest import skip
from unittest.mock import patch
from urllib import request

from django.test import TestCase, RequestFactory

from rest_framework.test import APIRequestFactory

from .forms import AddVideoByUrlForm
from .models import YoutubeVideo
from .views import download_video, get_dn_status


'''
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
'''

class AddVideoByURLFormTestCase(TestCase):
    
    def test_url_required(self):
        
        data = {}
        form = AddVideoByUrlForm(data=data)
        
        valid = form.is_valid()

        self.assertFalse(valid)
    
    def test_url_has_v(self):
        
        data = {"video_url":"https://youtube.com/channel/sasasasas"}
        form = AddVideoByUrlForm(data=data)

        valid = form.is_valid()


        self.assertFalse(valid)

        # check validation error
        self.assertIn("video_url", form.errors)
        self.assertEqual(len(form.errors.get("video_url")), 1)
        self.assertEqual(form.errors.get("video_url")[0], "URL must contain v attribute in query string")

    def test_valid_form(self):
        
        data = {"video_url": "https://www.youtube.com/watch?v=u2t1aLYu2QU"}

        form  = AddVideoByUrlForm(data)

        valid = form.is_valid()

        self.assertTrue(valid)
        

        obj = form.save()

        self.assertEqual(obj.video_id, "u2t1aLYu2QU")
        self.assertEqual(obj.video_url, "https://www.youtube.com/watch?v=u2t1aLYu2QU")
        self.assertEqual(obj.dn_status,0)


class DownloadVideoTaskTestCase(TestCase):

    @skip("no!")
    @patch("ytdl_manager.tasks.dn_stub")
    def test_first_task(self, dn_stub):
        
        video = YoutubeVideo.objects.create(
            pk="u2t1aLYu2QU",
            video_url="https://www.youtube.com/watch?v=u2t1aLYu2QU"
        )

        factory = RequestFactory()
        request = factory.post(f"/ytdl/dn_video/{video.pk}")

        resp = download_video(request, video.pk)

        self.assertEqual(resp.status_code, 202)
        
        #print(resp.content)

        video.refresh_from_db()

        self.assertNotEqual(video.dn_status, 0)
        self.assertNotEqual(video.dn_last_task_id, None)

        # perform second request
        resp = download_video(request, video.pk)
        self.assertEqual(resp.status_code, 200)
        
        data = json.loads(resp.content)
        self.assertEqual(data["id"], video.dn_last_task_id)


class GetDnStatusViewTestCase(TestCase):
    
    @classmethod
    def setUpClass(cls) -> None:
        cls.yt_url_tmpl = "https://www.youtube.com/watch?v=%s"
        cls.factory = APIRequestFactory()
        
        super().setUpClass()

    def test_no_progress_tasks(self):
         
        request = self.factory.post(
            "/dn_status", 
            data={"video_ids":[]},
            format="json"
        )
        response = get_dn_status(request)

        # test no video
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        # test all video not downloaded
        obj = YoutubeVideo.objects.create(pk="1", video_url=self.yt_url_tmpl % "1")
        obj = YoutubeVideo.objects.create(pk="2", video_url=self.yt_url_tmpl % "2")

        request = self.factory.post("/dn_status",data={"video_ids":["1","2"]}, format="json")
        response = get_dn_status(request)
                
        self.assertEqual(response.status_code, 200)
        expects = [
            {
                "id" : None,
                "video_id": "1",
                "state" : None,
                "result" : None
            },
            {
                "id" : None,
                "video_id": "2",
                "state" : None,
                "result" : None
            }
        ]
        self.assertListEqual(response.data, expects)

    def test_task_in_progress(self):

        # test data
        test_data = [
            {  # not downloaded yet
                "video_id": "1",
                "video_url": self.yt_url_tmpl % "1",
                "t_result": {
                    "id": None,
                    "video_id": "1",
                    "state": None,
                    "result": None 
                }
            },
            {  # in progress with task in progress
                "video_id": "2",
                "video_url": self.yt_url_tmpl % "2",
                "dn_status": 1,
                "dn_last_task_id": "task_prog",
                "t_result": {
                    "id": "task_prog",
                    "state": "PROGRESS",
                    "video_id": "2",
                    "result": {
                        "downloaded_bytes": 1024,
                        "total_bytes": 65536
                    }
                }
            }, 
            {  # in progress but task is pending
                "video_id": "3",
                "video_url": self.yt_url_tmpl % "3",
                "dn_status": 1,
                "dn_last_task_id": "task_pending",
                "t_result": {
                    "id": "task_pending",
                    "video_id": "3",
                    "state": "PENDING",
                    "result": None
                }
            },
            {  # success task
                "video_id": "4",
                "video_url": self.yt_url_tmpl % "4",
                "dn_status": 2,
                "dn_last_task_id": "task_success",
                "t_result": {
                    "id": "task_success",
                    "state": "SUCCESS",
                    "video_id": "4",
                    "result": {
                        "video_id": "4",
                        "status": "success",
                        "filename": "success_video.mp4"
                    }
                }
            },
            {  # download fail
                "video_id": "5",
                "video_url": self.yt_url_tmpl % "5",
                "dn_status": 3,
                "dn_last_task_id": "task_fail",
                "t_result": {
                    "id": "task_fail",
                    "video_id": "5",
                    "state": "FAILED",
                    "result": Exception("Failed")
                }
            }
        ]

        for d in test_data:
            obj_data = {**d}
            obj_data.pop("t_result")
            YoutubeVideo.objects.create(**obj_data)
        
        request_data = {
            "video_ids": [*range(1,6)]
        }

        request = self.factory.post("/dn_status", data=request_data, format="json")
        
        #print(test_data)

        class AsyncResultMock:
            
            mock_data = {
                data["t_result"]["id"]: {
                    **data["t_result"]
                } for data in test_data
            }
            '''
            mock_data = {
                "task_prog": {
                    "id": "task_prog",
                    "state": "PROGRESS",
                    "result": {
                        "downloaded_bytes": 1024,
                        "total_bytes": 65536
                    }
                },
                "task_pending": {
                    "id": "task_pending",
                    "state": "PENDING",
                    "result": None
                },
                "task_success": {
                    "id": "task_success",
                    "state": "SUCCESS",
                    "result": {
                        "video_id": "4",
                        "status": "success",
                        "filename": "success_video.mp4"
                    }
                },
                "task_fail": {
                    "id": "task_fail",
                    "state": "FAILED",
                    "result": Exception("Failed")
                }

            }
            '''
            def __init__(self, id) -> None:
                self.id = id
                
                result_data = self.mock_data.get(self.id)

                self.state = result_data["state"] if result_data else "PENDING"
                self.result = result_data["result"] if result_data else None

        with patch("ytdl_manager.views.AsyncResult", AsyncResultMock) as m:

            response = get_dn_status(request)

            self.assertEqual(response.status_code, 200)
            
            result_list = [data["t_result"] for data in test_data]

            self.assertListEqual(response.data, result_list)