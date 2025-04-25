from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('chat/', views.chat, name='chat'),
    path('signup/', views.signup, name='signup'),
    path('index/',views.index, name='index'),
    path('login/',views.login, name='login'),
    path('index/logout/',views.logout_view, name='logout'),
    path('chatbot_response/', views.chatbot_response, name='chatbot_response'),
    path('get_conversation_history/', views.get_conversation_history, name='get_conversation_history'),
    path('check-login-status/', views.check_login_status, name='check_login_status'),
    path('check-session/', views.check_session, name='check_session'),


]
