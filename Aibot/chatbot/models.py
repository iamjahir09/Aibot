from django.db import models
from django.contrib.auth.models import User

class UserStatus(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_logged_in = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {'Logged In' if self.is_logged_in else 'Logged Out'}"
