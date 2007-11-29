from os import path

from django.test import TestCase
from regressiontests.views.urls import media_dir

class StaticTests(TestCase):
    """Tests django views in django/views/static.py"""

    def test_serve(self):
        "The static view can serve static media"
        media_files = ['file.txt',]
        for filename in media_files:
            response = self.client.get('/views/site_media/%s' % filename)
            file = open(path.join(media_dir, filename))
            self.assertEquals(file.read(), response.content)

    def test_copes_with_empty_path_component(self):
        file_name = 'file.txt'
        response = self.client.get('/views/site_media//%s' % file_name)
        file = open(path.join(media_dir, file_name))
        self.assertEquals(file.read(), response.content)
        
        
