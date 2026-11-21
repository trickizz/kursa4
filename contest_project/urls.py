from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from contests.views import serve_media

urlpatterns = [
    path('admin/', admin.site.urls),

    path('accounts/login/', auth_views.LoginView.as_view(
        template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(
        next_page='/'), name='logout'),

    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('contests.urls')),
]

urlpatterns += [re_path(r'^media/(?P<path>.*)$', serve_media, name='serve_media')]
