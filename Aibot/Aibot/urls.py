from django.contrib import admin
from django.urls import path
from chatbot.views import home, chat  # <-- yeh zaruri hai

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),          # for index.html
    path('chat', chat, name='chat'),      # for API
]
