from django.db import models, transaction
from django.db.models import F
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.conf import settings # For ForeignKey to User
from decimal import Decimal # For cost calculations
from django.utils import timezone # Import timezone

# User Profile to store requested role and other user-specific, non-auth data
class UserProfile(models.Model):
    ROLE_CREW = 'CREW'
    ROLE_WAREHOUSE_STAFF = 'WAREHOUSE_STAFF'
    REQUESTED_ROLE_CHOICES = [
        (ROLE_CREW, 'Crew'),
        (ROLE_WAREHOUSE_STAFF, 'Warehouse Staff'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, # Use settings.AUTH_USER_MODEL for flexibility
        on_delete=models.CASCADE,
        related_name='profile'
    )
    requested_role = models.CharField(
        max_length=20,
        choices=REQUESTED_ROLE_CHOICES,
        null=True, # Allow null if a profile is created before a role is requested
        blank=True # Allow blank in forms if applicable, or if set programmatically
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile (Requested: {self.get_requested_role_display() or 'N/A'})"

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
    quantity_on_hand = models.PositiveIntegerField( # Still PositiveIntegerField for data integrity
        default=0,
        help_text="Current stock quantity. Updated by stock transactions."
        # editable=False # Consider making this non-editable in forms later
    )
    low_quantity_threshold = models.PositiveIntegerField(
        default=0,
        help_text="Threshold for low stock warning."
    )
    current_average_cost_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Current average cost per unit. Recalculated by stock transactions."
        # editable=False # Consider making this non-editable in forms later
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
        REQUESTED = 'REQUESTED', _('Requested') # New default
        IN_PROCESS = 'IN_PROCESS', _('In Process') # New
        # APPROVED = 'APPROVED', _('Approved') # Removing this for now, can be added back if multi-step approval needed
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
        max_length=12, # Adjusted max_length for 'IN_PROCESS'
        choices=Status.choices,
        default=Status.REQUESTED, # Changed default
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


class StockTransaction(models.Model):
    class TransactionType(models.TextChoices):
        INITIAL_STOCK = 'INITIAL', _('Initial Stock')
        RESTOCK = 'RESTOCK', _('Restock')
        # MANUAL_ADJUSTMENT_ADD = 'ADJUST_ADD', _('Manual Adjustment (Add)')
        # MANUAL_ADJUSTMENT_REMOVE = 'ADJUST_REMOVE', _('Manual Adjustment (Remove)')
        # MATERIAL_REQUEST_FULFILL = 'FULFILLMENT', _('Material Request Fulfillment') # Could also log deductions here

    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='stock_transactions')
    transaction_type = models.CharField(max_length=12, choices=TransactionType.choices)
    quantity_change = models.IntegerField( # Can be positive (add) or negative (remove, if used for that)
        help_text="Quantity of material added (positive) or removed (negative, if applicable)."
    )
    cost_per_unit_at_transaction = models.DecimalField( # Cost of items in *this* transaction
        max_digits=10,
        decimal_places=2,
        null=True, blank=True, # Null if it's a type of transaction without cost (e.g. pure adjustment)
        help_text="Cost per unit for items in this specific transaction (if applicable)."
    )
    total_cost_of_transaction = models.DecimalField( # quantity_change * cost_per_unit_at_transaction
        max_digits=12,
        decimal_places=2,
        null=True, blank=True, # Null if no cost involved
        help_text="Total cost of items in this transaction (quantity * cost per unit)."
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True, # User who performed or logged the transaction
        related_name='stock_transactions_logged'
    )

    def __str__(self):
        return f"{self.get_transaction_type_display()} of {self.quantity_change} x {self.material.name} on {self.created_at.strftime('%Y-%m-%d')}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if is_new and self.transaction_type in [self.TransactionType.INITIAL_STOCK, self.TransactionType.RESTOCK]:
            if self.quantity_change <= 0:
                raise ValueError("For Initial Stock or Restock, quantity_change must be positive.")
            if self.total_cost_of_transaction is None and self.cost_per_unit_at_transaction is not None:
                self.total_cost_of_transaction = self.quantity_change * self.cost_per_unit_at_transaction
            elif self.cost_per_unit_at_transaction is None and self.total_cost_of_transaction is not None and self.quantity_change != 0:
                    self.cost_per_unit_at_transaction = self.total_cost_of_transaction / Decimal(self.quantity_change) # Ensure decimal division

            if self.total_cost_of_transaction is None or self.cost_per_unit_at_transaction is None:
                    raise ValueError("For Initial Stock or Restock, cost (either total or per unit) must be provided.")

        super().save(*args, **kwargs) # Save this transaction first

        if is_new: # Only update material totals on new transactions to prevent issues on re-saves
            # Update Material's quantity and average cost
            material = self.material
            with transaction.atomic(): # Ensure material updates are atomic with transaction save
                # Refresh material from DB to avoid race conditions if possible, though F objects help
                material_to_update = Material.objects.select_for_update().get(pk=material.pk)

                if self.transaction_type in [self.TransactionType.INITIAL_STOCK, self.TransactionType.RESTOCK]:
                    # Recalculate average cost
                    current_total_value = (material_to_update.current_average_cost_per_unit * material_to_update.quantity_on_hand)
                    new_total_quantity = material_to_update.quantity_on_hand + self.quantity_change

                    if new_total_quantity > 0:
                        material_to_update.current_average_cost_per_unit = \
                            (current_total_value + self.total_cost_of_transaction) / Decimal(new_total_quantity) # Ensure decimal
                    elif self.quantity_change > 0 : # This is the first stock
                            material_to_update.current_average_cost_per_unit = self.cost_per_unit_at_transaction
                    else: # Should not happen if quantity_change must be positive for these types
                        material_to_update.current_average_cost_per_unit = Decimal('0.00')

                    material_to_update.quantity_on_hand = F('quantity_on_hand') + self.quantity_change

                # Add other transaction type effects here if needed (e.g., fulfillment decreasing stock)
                # For fulfillment, cost recalculation is not typical, but quantity is reduced.
                # That is handled in request_complete_view currently.

                material_to_update.updated_at = timezone.now() # Also update material's updated_at
                material_to_update.save(update_fields=['quantity_on_hand', 'current_average_cost_per_unit', 'updated_at'])
