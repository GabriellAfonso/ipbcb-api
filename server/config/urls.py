from django.conf import settings
from django.contrib import admin
from django.conf.urls.static import static
from django.urls import path, include
from django.urls import re_path
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(('apps.api.urls', 'api'), namespace='api')),
]

if settings.DEBUG:
    # Serve arquivos de mídia
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]

    # FORÇA o Django a servir qualquer coisa que peça /ipbcb/static/
    # Pegando o caminho físico direto do seu STATIC_ROOT
    urlpatterns += [
        re_path(r'^ipbcb/static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    ]