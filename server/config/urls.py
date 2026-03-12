from django.conf import settings
from django.contrib import admin
from django.conf.urls.static import static
from django.urls import path, include

urlpatterns = [
    path('ipbcb/admin/', admin.site.urls),
    path('ipbcb/', include('apps.accounts.urls')),
    path('ipbcb/', include('apps.songs.urls')),
    path('ipbcb/', include('apps.schedule.urls')),
    path('ipbcb/', include('apps.members.urls')),
    path('ipbcb/', include('apps.gallery.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
