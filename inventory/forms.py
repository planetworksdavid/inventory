from django import forms
from decimal import Decimal # Import Decimal
from django.urls import reverse_lazy
from django_select2.forms import ModelSelect2Widget, Select2Widget
from .models import MaterialRequest, Material, StockTransaction, MaterialCategory

class LoginForm(forms.Form):
    username = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}), required=True)

class MaterialRequestForm(forms.ModelForm):
    date_required = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=True
    )
    class Meta:
        model = MaterialRequest
        fields = ['date_required', 'justification']
        widgets = {
            'justification': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

class MaterialForm(forms.ModelForm):
    initial_quantity = forms.IntegerField(
        min_value=0, required=True, label="Initial Quantity on Hand",
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Initial stock quantity when adding this new material."
    )
    initial_total_cost = forms.DecimalField(
        max_digits=12, decimal_places=2, required=False,
        label="Total Cost for Initial Quantity",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        help_text="The total cost for the initial quantity being added."
    )
    initial_cost_per_unit = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        label="Cost Per Unit for Initial Quantity",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        help_text="The cost for each unit of the initial quantity."
    )

    class Meta:
        model = Material
        fields = [
            'name', 'sku', 'manufacturer', 'category', 'vendor',
            'unit_of_measure', 'low_quantity_threshold',
            'image', 'notes',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'manufacturer': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'vendor': forms.Select(attrs={'class': 'form-select'}),
            'unit_of_measure': forms.TextInput(attrs={'class': 'form-control'}),
            'low_quantity_threshold': forms.NumberInput(attrs={'class': 'form-control'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        initial_total_cost = cleaned_data.get('initial_total_cost')
        initial_cost_per_unit = cleaned_data.get('initial_cost_per_unit')
        initial_quantity = cleaned_data.get('initial_quantity')

        if initial_quantity is not None and initial_quantity > 0:
            if initial_total_cost is None and initial_cost_per_unit is None:
                raise forms.ValidationError(
                    "For initial quantity greater than zero, please provide either 'Total Cost for Initial Quantity' or 'Cost Per Unit for Initial Quantity'.",
                    code='missing_initial_cost'
                )
        elif initial_quantity is None or initial_quantity == 0:
            cleaned_data['initial_total_cost'] = Decimal('0.00')
            cleaned_data['initial_cost_per_unit'] = Decimal('0.00')

        if initial_total_cost is not None and initial_total_cost < 0:
            self.add_error('initial_total_cost', "Initial total cost cannot be negative.")
        if initial_cost_per_unit is not None and initial_cost_per_unit < 0:
            self.add_error('initial_cost_per_unit', "Initial cost per unit cannot be negative.")

        return cleaned_data

from django.contrib.auth.models import User
from .models import UserProfile # Import UserProfile

class SignupForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}),
        required=True,
        min_length=8 # Example: enforce minimum password length
    )
    password_confirmation = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm Password'}),
        required=True,
        label="Confirm Password"
    )
    requested_role = forms.ChoiceField(
        choices=UserProfile.REQUESTED_ROLE_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="I want to register as a"
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("A user with this username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email address is already in use.")
        return email

    def clean_password_confirmation(self):
        password = self.cleaned_data.get('password')
        password_confirmation = self.cleaned_data.get('password_confirmation')
        if password and password_confirmation and password != password_confirmation:
            raise forms.ValidationError("Passwords do not match.")
        return password_confirmation

class StockTransactionForm(forms.ModelForm):
    cost_per_unit_at_transaction = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        label="Cost Per Unit (for this transaction)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    total_cost_of_transaction = forms.DecimalField(
        max_digits=12, decimal_places=2, required=False,
        label="Total Cost (for this transaction)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )

    class Meta:
        model = StockTransaction
        fields = [
            'material', 'quantity_change',
            'cost_per_unit_at_transaction', 'total_cost_of_transaction',
            'notes'
        ]
        widgets = {
            'material': ModelSelect2Widget(
                model=Material,
                search_fields=['name__icontains', 'sku__icontains'],
                    attrs={
                        'data-placeholder': 'Search for a material by name or SKU...',
                        'style': 'width: 100%;',
                        'data-minimum-input-length': '0' # Add/Ensure this
                    },
                data_url=reverse_lazy('inventory:material_ajax_search')
            ),
            'quantity_change': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Positive value for additions'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'quantity_change': 'Quantity Added/Changed',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_quantity_change(self):
        quantity = self.cleaned_data.get('quantity_change')
        if quantity is not None and quantity <= 0:
            raise forms.ValidationError("Quantity must be positive for a restock.")
        return quantity

    def clean(self):
        cleaned_data = super().clean()
        cost_per_unit = cleaned_data.get('cost_per_unit_at_transaction')
        total_cost = cleaned_data.get('total_cost_of_transaction')

        if cost_per_unit is None and total_cost is None:
            raise forms.ValidationError("Please provide either 'Cost Per Unit' or 'Total Cost' for the transaction.")
        if cost_per_unit is not None and cost_per_unit < 0:
            self.add_error('cost_per_unit_at_transaction', "Cost per unit cannot be negative.")
        if total_cost is not None and total_cost < 0:
            self.add_error('total_cost_of_transaction', "Total cost cannot be negative.")

        return cleaned_data
