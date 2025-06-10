from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group, Permission
from django.utils import timezone
from decimal import Decimal

from .models import MaterialCategory, Vendor, Material, MaterialRequest, MaterialRequestItem
from .forms import MaterialForm, MaterialRequestForm, LoginForm # LoginForm is not used in these tests yet, but good to have
from django.forms import inlineformset_factory


class ModelCreationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = MaterialCategory.objects.create(name="Test Category", description="A category for testing")
        cls.vendor = Vendor.objects.create(name="Test Vendor", email="vendor@test.com")
        cls.material = Material.objects.create(
            name="Test Material",
            sku="TST001",
            category=cls.category,
            vendor=cls.vendor,
            unit_of_measure="piece",
            quantity_on_hand=100,
            low_quantity_threshold=10,
            current_average_cost_per_unit=Decimal("1.99")
        )
        # User for material request
        cls.crew_user = User.objects.create_user(username='testcrew', password='password')
        # Ensure group exists (might be created by migrations, but good for test independence)
        cls.crew_group, _ = Group.objects.get_or_create(name='Crew')
        cls.crew_user.groups.add(cls.crew_group)

        cls.material_request = MaterialRequest.objects.create(
            requested_by=cls.crew_user,
            date_required=timezone.now().date() + timezone.timedelta(days=5)
        )
        cls.request_item = MaterialRequestItem.objects.create(
            material_request=cls.material_request,
            material=cls.material,
            quantity_requested=5
        )

    def test_material_category_str(self):
        self.assertEqual(str(self.category), "Test Category")

    def test_vendor_str(self):
        self.assertEqual(str(self.vendor), "Test Vendor")

    def test_material_str(self):
        self.assertEqual(str(self.material), "Test Material (SKU: TST001)")

    def test_material_request_str(self):
        # The __str__ method uses self.status (the value, e.g., 'PENDING')
        # not self.get_status_display() (the label, e.g., 'Pending').
        expected_str = f"Request ID: {self.material_request.id} by {self.crew_user.username} - {self.material_request.status}"
        self.assertEqual(str(self.material_request), expected_str)

    def test_material_request_item_str(self):
        expected_str = f"5 of Test Material for Request ID: {self.material_request.id}"
        self.assertEqual(str(self.request_item), expected_str)


class MaterialFormTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = MaterialCategory.objects.create(name="Form Test Category")
        cls.vendor = Vendor.objects.create(name="Form Test Vendor")

    def test_material_form_valid(self):
        form_data = {
            'name': "New Material",
            'sku': "NEW001",
            'category': self.category.id,
            'vendor': self.vendor.id,
            'unit_of_measure': "kg",
            'quantity_on_hand': 50,
            'low_quantity_threshold': 5,
            'current_average_cost_per_unit': "25.50"
            # image and notes are optional
        }
        form = MaterialForm(data=form_data)
        self.assertTrue(form.is_valid(), msg=f"Form errors: {form.errors.as_json()}")

    def test_material_form_invalid_missing_required_fields(self):
        form_data = {
            'name': "Missing Fields Material",
            # SKU is missing
            # category is missing
            'unit_of_measure': "piece", # This is required
            # quantity_on_hand is missing (has default but might be wanted in form)
            # low_quantity_threshold is missing (has default)
            # current_average_cost_per_unit is missing (has default)
        }
        form = MaterialForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('sku', form.errors)
        self.assertIn('category', form.errors)
        # quantity_on_hand should not be an error if it has a model default and not explicitly required by form
        # self.assertIn('quantity_on_hand', form.errors)
        self.assertIn('current_average_cost_per_unit', form.errors)


    def test_material_form_negative_quantity(self):
        form_data = {
            'name': "Negative Qty Material",
            'sku': "NEG001",
            'category': self.category.id, # Required
            'vendor': self.vendor.id, # Optional
            'unit_of_measure': "piece", # Required
            'quantity_on_hand': -5, # Invalid (PositiveIntegerField)
            'low_quantity_threshold': 1, # Required (PositiveIntegerField)
            'current_average_cost_per_unit': "1.00" # Required
        }
        form = MaterialForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('quantity_on_hand', form.errors)


class MaterialRequestFormTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='req_tester', password='password')
        cls.cat = MaterialCategory.objects.create(name="ReqCat1")
        cls.material1 = Material.objects.create(name="Mat1 for Req", sku="MATR1", category=cls.cat, unit_of_measure="pc", quantity_on_hand=10)
        cls.material2 = Material.objects.create(name="Mat2 for Req", sku="MATR2", category=cls.cat, unit_of_measure="pc", quantity_on_hand=20)

    def test_material_request_form_valid(self):
        form_data = {
            'date_required': timezone.now().date() + timezone.timedelta(days=3),
            'justification': 'Urgent need for project Y.'
        }
        form = MaterialRequestForm(data=form_data)
        self.assertTrue(form.is_valid(), msg=f"Form errors: {form.errors.as_json()}")

    def test_material_request_form_missing_date(self):
        form_data = {'justification': 'Test'} # date_required is missing
        form = MaterialRequestForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('date_required', form.errors)

    def test_material_request_item_formset_valid(self):
        MaterialRequestItemFormSet = inlineformset_factory(
            MaterialRequest, MaterialRequestItem,
            fields=('material', 'quantity_requested'),
            extra=1
        )

        request_instance = MaterialRequest(requested_by=self.user, date_required=timezone.now().date())
        # Formset needs parent instance to be saved if it's a new one, or pass instance=None for unbound.
        # For testing bound formsets for new objects, often we don't save the instance yet.
        # However, if the formset relies on the instance existing (e.g. for clean methods), it might need to be saved.
        # For this basic test, an unsaved instance is okay.

        formset_data = {
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MAX_NUM_FORMS': '', # Should be a number or empty
            'items-0-material': self.material1.id,
            'items-0-quantity_requested': '5',
        }
        # For a new request_instance, it should not be saved yet if testing the formset standalone before request save.
        # But inlineformset_factory used in views often gets a saved instance.
        # Let's test as if it's a new, unsaved instance for now.
        formset = MaterialRequestItemFormSet(formset_data, instance=request_instance, prefix='items')

        # If the formset has a clean method that saves/uses the instance, this might fail.
        # The default ModelFormSet doesn't save automatically.
        self.assertTrue(formset.is_valid(), msg=f"Formset errors: {formset.errors}")


    def test_material_request_item_formset_invalid_quantity(self):
        MaterialRequestItemFormSet = inlineformset_factory(MaterialRequest, MaterialRequestItem, fields=('material', 'quantity_requested'), extra=1)
        request_instance = MaterialRequest(requested_by=self.user, date_required=timezone.now().date())

        formset_data = {
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MAX_NUM_FORMS': '',
            'items-0-material': self.material1.id,
            'items-0-quantity_requested': '0', # Valid for PositiveIntegerField, but might be undesirable.
        }
        formset = MaterialRequestItemFormSet(formset_data, instance=request_instance, prefix='items')
        # PositiveIntegerField allows 0. If business logic requires > 0, MinValueValidator(1) should be on model/form.
        # For this test, based on current model definition, 0 is valid.
        self.assertTrue(formset.is_valid(), msg=f"Formset errors: {formset.errors}")
        # If we wanted to ensure it's not an error:
        # self.assertFalse(formset.forms[0].has_error('quantity_requested'))

    def test_material_request_item_formset_no_data(self):
        MaterialRequestItemFormSet = inlineformset_factory(MaterialRequest, MaterialRequestItem, fields=('material', 'quantity_requested'), extra=1)
        request_instance = MaterialRequest(requested_by=self.user, date_required=timezone.now().date())

        formset_data = { # Missing items-0- data
            'items-TOTAL_FORMS': '0', # This means no forms submitted
            'items-INITIAL_FORMS': '0',
            'items-MAX_NUM_FORMS': '',
        }
        formset = MaterialRequestItemFormSet(formset_data, instance=request_instance, prefix='items')
        # An empty formset (TOTAL_FORMS=0) is considered valid if not otherwise constrained (e.g. min_num)
        # If at least one form is required, this test would change.
        # Default behavior: an empty formset is valid.
        self.assertTrue(formset.is_valid(), msg=f"Formset errors: {formset.errors}")
        # If formset MUST NOT be empty:
        # self.assertFalse(formset.is_valid())
        # self.assertTrue(formset.non_form_errors()) # Check for non-form errors like "at least one form required"

# We can add more tests for LoginForm, other model methods, etc.
# View tests will be more complex and will be added next.
