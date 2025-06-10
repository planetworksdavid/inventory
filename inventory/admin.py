from django.contrib import admin
from .models import MaterialCategory, Vendor, Material, MaterialRequest, MaterialRequestItem

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
        'unit_of_measure', 'low_quantity_threshold', 'current_average_cost_per_unit'
    )
    list_filter = ('category', 'vendor', 'manufacturer')
    search_fields = ('name', 'sku', 'manufacturer')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'sku', 'category', 'manufacturer', 'vendor')
        }),
        ('Stock Details', {
            'fields': ('unit_of_measure', 'quantity_on_hand', 'low_quantity_threshold')
        }),
        ('Financials', {
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
