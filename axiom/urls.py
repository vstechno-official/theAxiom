# A Axiom entity ;)
from django.contrib import admin
from django.conf import settings
from django.urls import include, path
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
]

urlpatterns += [
    path("static/<path:path>", serve, {"document_root": settings.STATICFILES_DIRS[0]}),
]
