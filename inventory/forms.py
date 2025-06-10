from django import forms
from .models import MaterialRequest, Material # Add Material

# ... (LoginForm and MaterialRequestForm remain) ...
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
    class Meta:
        model = Material
        fields = [
            'name', 'sku', 'manufacturer', 'category', 'vendor',
            'unit_of_measure', 'quantity_on_hand',
            'low_quantity_threshold', 'current_average_cost_per_unit',
            'image', 'notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'manufacturer': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'vendor': forms.Select(attrs={'class': 'form-select'}),
            'unit_of_measure': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity_on_hand': forms.NumberInput(attrs={'class': 'form-control'}),
            'low_quantity_threshold': forms.NumberInput(attrs={'class': 'form-control'}),
            'current_average_cost_per_unit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        help_texts = { # Optional: Add or override help texts if needed
            'quantity_on_hand': 'Initial quantity when adding a new material.'
        }
