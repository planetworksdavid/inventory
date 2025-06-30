from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User # Import User
from .models import (
    MaterialCategory, Vendor, Material,
    MaterialRequest, MaterialRequestItem,
    UserProfile # Import UserProfile
)
from django.utils import timezone # For admin actions if needed

# --- User Admin Customization ---
# Define an inline admin descriptor for UserProfile
class UserProfileInline(admin.StackedInline): # Or admin.TabularInline for a more compact view
    model = UserProfile
    can_delete = False # Typically, you don't want to delete the profile when deleting a user from here
    verbose_name_plural = 'User Profile & Role Request'
    # Specify fields to display in the inline form; 'requested_role' is key
    fields = ('requested_role', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at') # Timestamps are usually read-only

# Define a new User admin by extending the base UserAdmin
class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'get_requested_role')
    list_filter = BaseUserAdmin.list_filter + ('is_active', 'profile__requested_role') # Filter by active status & requested role

    @admin.display(description='Requested Role', ordering='profile__requested_role')
    def get_requested_role(self, obj):
        # obj is a User instance
        if hasattr(obj, 'profile') and obj.profile and obj.profile.requested_role:
            return obj.profile.get_requested_role_display()
        return None # Or '-' or 'Not Requested'

    # To make users searchable by their requested role (optional)
    # search_fields = BaseUserAdmin.search_fields + ('profile__requested_role',)

# Unregister the original User admin if it's already registered by Django
admin.site.unregister(User)
# Register the User model with your custom admin
admin.site.register(User, CustomUserAdmin)

# --- Other Model Admins ---
@admin.register(MaterialCategory)
class MaterialCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone_number', 'email')
    search_fields = ('name', 'contact_person', 'email')

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'sku', 'category', 'vendor', 'quantity_on_hand',
        'unit_of_measure', 'low_quantity_threshold', 'current_average_cost_per_unit', 'updated_at'
    )
    list_filter = ('category', 'vendor', 'manufacturer')
    search_fields = ('name', 'sku', 'manufacturer')
    readonly_fields = ('created_at', 'updated_at', 'quantity_on_hand', 'current_average_cost_per_unit') # Added quantity and cost
    fieldsets = (
        (None, {
            'fields': ('name', 'sku', 'category', 'manufacturer', 'vendor')
        }),
        ('Stock Details', { # quantity_on_hand is now readonly
            'fields': ('unit_of_measure', 'quantity_on_hand', 'low_quantity_threshold')
        }),
        ('Financials', { # current_average_cost_per_unit is now readonly
            'fields': ('current_average_cost_per_unit',)
        }),
        ('Media', {
            'fields': ('image',)
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',) # Keep timestamps less prominent
        }),
    )

class MaterialRequestItemInline(admin.TabularInline):
    model = MaterialRequestItem
    extra = 1 # Number of empty forms to display
    autocomplete_fields = ['material'] # If you have many materials, for better UX

@admin.register(MaterialRequest)
class MaterialRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'requested_by', 'date_required', 'status', 'created_at')
    list_filter = ('status', 'date_required', 'requested_by')
    search_fields = ('id', 'requested_by__username')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [MaterialRequestItemInline]
    fieldsets = (
        (None, {
            'fields': ('requested_by', 'date_required', 'status', 'justification')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

# We can also register MaterialRequestItem if direct admin access is needed,
# but it's often managed via MaterialRequest inline.
# If direct access is desired:
# @admin.register(MaterialRequestItem)
# class MaterialRequestItemAdmin(admin.ModelAdmin):
#     list_display = ('material_request', 'material', 'quantity_requested', 'fulfilled_quantity')
#     search_fields = ('material_request__id', 'material__name')
