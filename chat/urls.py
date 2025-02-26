from django.contrib.auth.views import LogoutView
from django.urls import path
from . import views
from .views import users_view, LoginRedirectView, mark_as_read, load_messages, chatbot_response, custom_404_view
from django.contrib.auth import views as auth_views
from .views import custom_logout_view
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('get-response/', chatbot_response, name="chatbot_response"),
    path('users/', views.user_list_view, name='user_list'),
    path('chat/<str:username>/', views.chat_view, name='chat'),
    path('mark-as-read/', mark_as_read, name='mark_as_read'),
    path('load-messages/<str:sender>/<str:recipient>/', load_messages, name='load-messages'),
    path('', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('users/', users_view, name='users'),
    path('chat/fetch-messages/<str:username>/', views.fetch_new_messages, name='fetch_new_messages'),
    path('login_redirect/', LoginRedirectView.as_view(), name='login_redirect'),
    path('screenshare/<str:room_name>/', views.screen_share, name='screen_share'),
    path('password-reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('logout/', custom_logout_view, name='logout'),
]
handler = custom_404_view
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)