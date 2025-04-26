from django.db import models
from django.contrib.auth.models import User

class UserStatus(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_logged_in = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {'Logged In' if self.is_logged_in else 'Logged Out'}"

from django.db import models
from django.conf import settings

class ChatMessage(models.Model):
    user_id = models.IntegerField()  # Or ForeignKey if using User model
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class UploadedFile(models.Model):
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    message = models.ForeignKey(ChatMessage, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    @property
    def url(self):
        return self.file.url if self.file else None