from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Inventory
    path('', views.material_list_view, name='material_list'), # Assuming root of app is material list

    # Material Requests (Crew)
    path('requests/new/', views.material_request_create_view, name='material_request_create'),
    path('requests/my/', views.crew_request_list_view, name='crew_request_list'),
    path('requests/<int:request_id>/edit/', views.material_request_edit_view, name='material_request_edit'),
    path('requests/<int:request_id>/cancel/', views.material_request_cancel_view, name='material_request_cancel'),

    # Order Fulfillment (Warehouse Staff)
    path('warehouse/requests/pending/', views.pending_request_list_view, name='pending_request_list'),
    path('warehouse/requests/<int:request_id>/start_processing/', views.request_start_processing_view, name='request_start_processing'),
    path('warehouse/requests/<int:request_id>/complete/', views.request_complete_view, name='request_complete'),
    path('warehouse/requests/completed/', views.completed_request_list_view, name='completed_request_list'),

    # Inventory Management (Warehouse Staff)
    path('warehouse/materials/new/', views.material_create_view, name='material_create'),
    path('warehouse/materials/<int:material_id>/update/', views.material_update_view, name='material_update'),
    path('warehouse/materials/restock/', views.material_restock_view, name='material_restock'),
    # AJAX Search URL for Select2
    path('ajax/material_search/', views.MaterialAjaxSearch.as_view(), name='material_ajax_search'),
]
