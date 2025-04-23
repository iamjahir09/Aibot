from django.contrib import admin
from django.urls import path
from chatbot.views import home, chat,index,signup,login,logout,check_login_status,chatbot_response,get_conversation_history # <-- yeh zaruri hai

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),          # for index.html
    path('chat', chat, name='chat'),      # for API
    path('signup', signup, name='signup'),
    path('index',index, name='index'),
    path('login',login, name='login'),
    path('logout/',logout, name='logout'),
    path('chatbot_response/', chatbot_response, name='chatbot_response'),
    path('get_conversation_history', get_conversation_history, name='get_conversation_history'),
    path('check-login-status/', check_login_status, name='check_login_status'),

]

