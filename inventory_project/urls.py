from django.contrib import admin
from django.urls import path, include
from django.conf import settings # For media files
from django.conf.urls.static import static # For media files

urlpatterns = [
    path('admin/', admin.site.urls),
    path('inventory/', include('inventory.urls', namespace='inventory')),
    # Potentially a root path redirecting to inventory or a dashboard later
    # path('', some_view_for_root_path, name='home'),
]

# Add media URL serving during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
