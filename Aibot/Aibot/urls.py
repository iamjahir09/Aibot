from django.contrib import admin
from django.urls import path
from chatbot.views import home, chat,index,signup,get_chat_history,check_session,login,logout_view,check_login_status,chatbot_response,get_conversation_history # <-- yeh zaruri hai

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),          # for index.html
    path('chat', chat, name='chat'),      # for API
    path('signup', signup, name='signup'),
    path('index/',index, name='index'),
    path('login/',login, name='login'),
    path('index/logout/',logout_view, name='logout_view'),
    path('chatbot_response/', chatbot_response, name='chatbot_response'),
    path('get_conversation_history', get_conversation_history, name='get_conversation_history'),
    path('check-login-status/', check_login_status, name='check_login_status'),
    path('check-session/', check_session, name='check_session'),
    path('get_chat_history/', get_chat_history, name='get_chat_history'),


]

