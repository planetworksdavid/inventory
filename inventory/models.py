from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

class MaterialCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Material Categories"

class Vendor(models.Model):
    name = models.CharField(max_length=200, unique=True)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Material(models.Model):
    name = models.CharField(max_length=200, help_text="Name of the material/item.")
    sku = models.CharField(max_length=100, unique=True, help_text="Stock Keeping Unit.")
    manufacturer = models.CharField(max_length=100, blank=True, null=True)
    category = models.ForeignKey(
        MaterialCategory,
        on_delete=models.PROTECT,
        help_text="Category of the material."
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Supplier of the material."
    )
    unit_of_measure = models.CharField(max_length=50, help_text="e.g., pieces, meters, kg.")
    quantity_on_hand = models.PositiveIntegerField(
        default=0,
        help_text="Current stock quantity."
    )
    low_quantity_threshold = models.PositiveIntegerField(
        default=0,
        help_text="Threshold for low stock warning."
    )
    current_average_cost_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Current average cost per unit of the material."
    )
    image = models.ImageField(
        upload_to='material_images/',
        blank=True,
        null=True,
        help_text="Optional image of the item."
    )
    notes = models.TextField(blank=True, null=True, help_text="Any additional notes.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (SKU: {self.sku})"

    class Meta:
        ordering = ['name']

class MaterialRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        APPROVED = 'APPROVED', _('Approved') # Added for potential approval step
        COMPLETED = 'COMPLETED', _('Completed')
        CANCELLED = 'CANCELLED', _('Cancelled')

    requested_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='material_requests',
        help_text="User who made the request."
    )
    # items = models.ManyToManyField(Material, through='MaterialRequestItem') # Defined below
    date_required = models.DateField(help_text="Date when the materials are required.")
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="Current status of the request."
    )
    justification = models.TextField(blank=True, null=True, help_text="Reason for the request.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Request ID: {self.id} by {self.requested_by.username} - {self.status}"

    class Meta:
        ordering = ['-created_at']

class MaterialRequestItem(models.Model):
    material_request = models.ForeignKey(
        MaterialRequest,
        on_delete=models.CASCADE,
        related_name='request_items'
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT, # Prevent deletion of material if it's in a request
        related_name='request_instances'
    )
    quantity_requested = models.PositiveIntegerField(help_text="Quantity of the material requested.")
    fulfilled_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Quantity actually fulfilled. Can be less than requested if stock is low."
    ) # Added for partial fulfillment scenarios

    def __str__(self):
        return f"{self.quantity_requested} of {self.material.name} for Request ID: {self.material_request.id}"

    class Meta:
        unique_together = ('material_request', 'material') # Ensure a material is not added twice to the same request
