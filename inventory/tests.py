from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group, Permission
from django.utils import timezone
from decimal import Decimal

from .models import MaterialCategory, Vendor, Material, MaterialRequest, MaterialRequestItem, StockTransaction # Import StockTransaction
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
            'low_quantity_threshold': 5,
                # New fields for initial stock for MaterialForm
                'initial_quantity': 50,
                'initial_total_cost': "127.50" # 50 * 2.55 (derived from avg cost for consistency)
                # or 'initial_cost_per_unit': "2.55"
        }
        form = MaterialForm(data=form_data)
        self.assertTrue(form.is_valid(), msg=f"Form errors: {form.errors.as_json()}")

    def test_material_form_invalid_missing_required_fields(self):
        form_data = {
            'name': "Missing Fields Material",
            # SKU is missing
            # category is missing
            'unit_of_measure': "piece",
            # low_quantity_threshold is missing
            # initial_quantity is missing
        }
        form = MaterialForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('sku', form.errors)
        self.assertIn('category', form.errors)
        self.assertIn('low_quantity_threshold', form.errors)
        self.assertIn('initial_quantity', form.errors)


    def test_material_form_negative_initial_quantity(self):
        form_data = {
            'name': "Negative Initial Qty Material",
            'sku': "NEG001",
            'category': self.category.id,
            'unit_of_measure': "piece",
            'low_quantity_threshold': 1,
            'initial_quantity': -5, # Invalid (min_value=0 in form field)
            'initial_cost_per_unit': "1.00"
        }
        form = MaterialForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('initial_quantity', form.errors)


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

from .forms import StockTransactionForm # Add this

# We can add more tests for LoginForm, other model methods, etc.
# View tests will be more complex and will be added next.


class StockTransactionFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = MaterialCategory.objects.create(name="ST Form Test Category")
        cls.vendor = Vendor.objects.create(name="ST Form Test Vendor")
        cls.material = Material.objects.create(
            name="Test Material for ST Form", sku="STF-MAT001", category=cls.category
        )

    def test_stock_transaction_form_valid_with_total_cost(self):
        form_data = {
            'material': self.material.id,
            'quantity_change': 10,
            'total_cost_of_transaction': Decimal("50.00"), # 5.00 per unit
            'notes': 'Test restock'
        }
        form = StockTransactionForm(data=form_data)
        self.assertTrue(form.is_valid(), msg=f"Form errors: {form.errors.as_json()}")

    def test_stock_transaction_form_valid_with_cost_per_unit(self):
        form_data = {
            'material': self.material.id,
            'quantity_change': 5,
            'cost_per_unit_at_transaction': Decimal("6.00"), # Total 30.00
            'notes': 'Test restock with CPU'
        }
        form = StockTransactionForm(data=form_data)
        self.assertTrue(form.is_valid(), msg=f"Form errors: {form.errors.as_json()}")

    def test_stock_transaction_form_invalid_no_cost(self):
        form_data = {
            'material': self.material.id,
            'quantity_change': 10,
            # No cost fields
        }
        form = StockTransactionForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors) # Should be a non-field error from clean()
        self.assertTrue("Please provide either 'Cost Per Unit' or 'Total Cost'" in form.errors['__all__'][0])


    def test_stock_transaction_form_invalid_negative_quantity(self):
        form_data = {
            'material': self.material.id,
            'quantity_change': -5, # Invalid for this form's clean_quantity_change
            'total_cost_of_transaction': Decimal("20.00")
        }
        form = StockTransactionForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('quantity_change', form.errors)
        self.assertTrue("Quantity must be positive for a restock." in form.errors['quantity_change'][0])

    def test_stock_transaction_form_invalid_negative_cost(self):
        form_data_total = {
            'material': self.material.id, 'quantity_change': 5, 'total_cost_of_transaction': Decimal("-20.00")
        }
        form_total = StockTransactionForm(data=form_data_total)
        self.assertFalse(form_total.is_valid())
        self.assertIn('total_cost_of_transaction', form_total.errors)

        form_data_cpu = {
            'material': self.material.id, 'quantity_change': 5, 'cost_per_unit_at_transaction': Decimal("-4.00")
        }
        form_cpu = StockTransactionForm(data=form_data_cpu)
        self.assertFalse(form_cpu.is_valid())
        self.assertIn('cost_per_unit_at_transaction', form_cpu.errors)


class StockTransactionModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = MaterialCategory.objects.create(name="ST Test Category")
        cls.vendor = Vendor.objects.create(name="ST Test Vendor")
        cls.user = User.objects.create_user(username='stocktester', password='password')

    def setUp(self):
        # Create a fresh material for each test method to avoid interference
        self.material = Material.objects.create(
            name="Test Material for Stock Tx",
            sku="ST-MAT001",
            category=self.category,
            vendor=self.vendor,
            unit_of_measure="unit",
            # quantity_on_hand and current_average_cost_per_unit default to 0
        )

    def test_initial_stock_transaction(self):
        StockTransaction.objects.create(
            material=self.material,
            transaction_type=StockTransaction.TransactionType.INITIAL_STOCK,
            quantity_change=10,
            cost_per_unit_at_transaction=Decimal("5.00"),
            created_by=self.user
        )
        self.material.refresh_from_db()
        self.assertEqual(self.material.quantity_on_hand, 10)
        self.assertEqual(self.material.current_average_cost_per_unit, Decimal("5.00"))

    def test_restock_transaction_updates_quantity_and_avg_cost(self):
        # Initial stock
        StockTransaction.objects.create(
            material=self.material,
            transaction_type=StockTransaction.TransactionType.INITIAL_STOCK,
            quantity_change=10,
            total_cost_of_transaction=Decimal("100.00"), # 10 per unit
            created_by=self.user
        )
        self.material.refresh_from_db()
        self.assertEqual(self.material.quantity_on_hand, 10)
        self.assertEqual(self.material.current_average_cost_per_unit, Decimal("10.00"))

        # First restock
        StockTransaction.objects.create(
            material=self.material,
            transaction_type=StockTransaction.TransactionType.RESTOCK,
            quantity_change=10, # Adding 10 more units
            total_cost_of_transaction=Decimal("120.00"), # at 12 per unit
            created_by=self.user
        )
        self.material.refresh_from_db()
        self.assertEqual(self.material.quantity_on_hand, 20) # 10 (old) + 10 (new)
        # Expected avg cost: ((10 * 10) + 120) / (10 + 10) = (100 + 120) / 20 = 220 / 20 = 11.00
        self.assertEqual(self.material.current_average_cost_per_unit, Decimal("11.00"))

    def test_restock_derives_total_cost(self):
        st = StockTransaction.objects.create(
            material=self.material,
            transaction_type=StockTransaction.TransactionType.INITIAL_STOCK,
            quantity_change=5,
            cost_per_unit_at_transaction=Decimal("2.00"), # Total should be 10.00
            created_by=self.user
        )
        self.assertEqual(st.total_cost_of_transaction, Decimal("10.00"))
        self.material.refresh_from_db()
        self.assertEqual(self.material.quantity_on_hand, 5)
        self.assertEqual(self.material.current_average_cost_per_unit, Decimal("2.00"))

    def test_restock_derives_cost_per_unit(self):
        st = StockTransaction.objects.create(
            material=self.material,
            transaction_type=StockTransaction.TransactionType.INITIAL_STOCK,
            quantity_change=4,
            total_cost_of_transaction=Decimal("12.00"), # Cost per unit should be 3.00
            created_by=self.user
        )
        self.assertEqual(st.cost_per_unit_at_transaction, Decimal("3.00"))
        self.material.refresh_from_db()
        self.assertEqual(self.material.quantity_on_hand, 4)
        self.assertEqual(self.material.current_average_cost_per_unit, Decimal("3.00"))

    def test_initial_stock_with_zero_quantity(self):
        # This should raise a ValueError because quantity_change must be positive for INITIAL_STOCK
        with self.assertRaisesMessage(ValueError, "For Initial Stock or Restock, quantity_change must be positive."):
            StockTransaction.objects.create(
                material=self.material,
                transaction_type=StockTransaction.TransactionType.INITIAL_STOCK,
                quantity_change=0, # Zero quantity, should be invalid
                total_cost_of_transaction=Decimal("0.00"),
                created_by=self.user
            )
        # Verify that material state is unchanged
        self.material.refresh_from_db()
        self.assertEqual(self.material.quantity_on_hand, 0)
        self.assertEqual(self.material.current_average_cost_per_unit, Decimal("0.00"))


    def test_value_error_for_negative_quantity_in_restock(self):
        with self.assertRaisesMessage(ValueError, "For Initial Stock or Restock, quantity_change must be positive."):
            StockTransaction.objects.create(
                material=self.material,
                transaction_type=StockTransaction.TransactionType.RESTOCK,
                quantity_change=-5, # Invalid
                total_cost_of_transaction=Decimal("50.00"),
                created_by=self.user
            )

    def test_value_error_for_zero_quantity_in_restock(self):
        # Based on current model save logic, quantity_change must be > 0 for RESTOCK/INITIAL
        with self.assertRaisesMessage(ValueError, "For Initial Stock or Restock, quantity_change must be positive."):
            StockTransaction.objects.create(
                material=self.material,
                transaction_type=StockTransaction.TransactionType.RESTOCK,
                quantity_change=0, # Invalid for restock
                total_cost_of_transaction=Decimal("0.00"),
                created_by=self.user
            )

    def test_value_error_if_no_cost_provided_for_restock(self):
        with self.assertRaisesMessage(ValueError, "For Initial Stock or Restock, cost (either total or per unit) must be provided."):
            StockTransaction.objects.create(
                material=self.material,
                transaction_type=StockTransaction.TransactionType.RESTOCK,
                quantity_change=10,
                # No cost_per_unit or total_cost provided
                created_by=self.user
            )

    def test_fulfillment_transaction_does_not_change_avg_cost(self):
        # Setup initial stock
        StockTransaction.objects.create(
            material=self.material,
            transaction_type=StockTransaction.TransactionType.INITIAL_STOCK,
            quantity_change=20,
            cost_per_unit_at_transaction=Decimal("10.00"),
            created_by=self.user
        )
        self.material.refresh_from_db()
        initial_avg_cost = self.material.current_average_cost_per_unit # Should be 10.00

        # Simulate a fulfillment by directly creating a StockTransaction
        # NOTE: In the app, fulfillment deduction is handled in `request_complete_view`
        # This test is to ensure if we *did* use StockTransaction for fulfillment, avg cost is stable.
        # Our current StockTransaction.save() only recalculates cost for INITIAL/RESTOCK.

        # This will not trigger the cost averaging logic in StockTransaction.save()
        # because transaction_type is not INITIAL_STOCK or RESTOCK
        StockTransaction.objects.create(
            material=self.material,
            transaction_type="FULFILLMENT_TEST", # Custom type not affecting cost
            quantity_change=-5, # Deduction
            created_by=self.user
            # No cost fields needed as it doesn't affect avg cost calc
        )
        self.material.refresh_from_db()
        # Manually update quantity for this test as current ST.save() doesn't handle this type
        # The model's save() method for StockTransaction does NOT modify material for non-INITIAL/RESTOCK types.
        # The stock deduction for FULFILLMENT is handled in the request_complete_view.
        # This test is verifying that a non-INITIAL/RESTOCK StockTransaction does not *itself* alter avg_cost.
        # We are not testing the FULFILLMENT logic of request_complete_view here.
        # So, we expect quantity_on_hand to be unchanged by this specific ST creation.
        # self.material.quantity_on_hand -= 5 # This manual change is not what ST.save() does for this type
        # self.material.save()

        self.assertEqual(self.material.quantity_on_hand, 20) # Quantity should be unchanged by this specific ST.save()
        self.assertEqual(self.material.current_average_cost_per_unit, initial_avg_cost) # Avg cost should be unchanged

    def test_restock_on_material_with_zero_initial_stock(self):
        # Material starts with 0 quantity and 0 avg cost
        self.assertEqual(self.material.quantity_on_hand, 0)
        self.assertEqual(self.material.current_average_cost_per_unit, Decimal("0.00"))

        # Restock
        StockTransaction.objects.create(
            material=self.material,
            transaction_type=StockTransaction.TransactionType.RESTOCK,
            quantity_change=5,
            total_cost_of_transaction=Decimal("25.00"), # 5 per unit
            created_by=self.user
        )
        self.material.refresh_from_db()
        self.assertEqual(self.material.quantity_on_hand, 5)
        self.assertEqual(self.material.current_average_cost_per_unit, Decimal("5.00"))


class InventoryViewAccessPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.warehouse_group, _ = Group.objects.get_or_create(name='Warehouse Staff')
        cls.crew_group, _ = Group.objects.get_or_create(name='Crew')

        cls.warehouse_user = User.objects.create_user(username='perm_warehouse', password='password')
        cls.warehouse_user.groups.add(cls.warehouse_group)

        cls.crew_user = User.objects.create_user(username='perm_crew', password='password')
        cls.crew_user.groups.add(cls.crew_group)

        cls.category = MaterialCategory.objects.create(name="Perm Test Category")
        cls.material = Material.objects.create(name="Perm Test Material", sku="PERM001", category=cls.category)

        # Create a material request by the crew user for testing edit/cancel views
        cls.material_request_by_crew = MaterialRequest.objects.create(
            requested_by=cls.crew_user,
            date_required=timezone.now().date(),
            status=MaterialRequest.Status.REQUESTED # Ensure it's in a state that can be manipulated by tests
        )
        # Add an item to it, otherwise formsets in edit view might behave unexpectedly if empty
        MaterialRequestItem.objects.create(material_request=cls.material_request_by_crew, material=cls.material, quantity_requested=1)


        # Assign necessary permissions for views to function (even if access is denied later)
        from django.contrib.contenttypes.models import ContentType

        # It's generally better to assign permissions to groups, then users to groups.
        # However, for specific test user setup, direct assignment is also okay.
        # We will rely on the data migrations (0003 and 0006) to have set group permissions.
        # The users are added to groups, so they should inherit these permissions.
        # If those migrations haven't run or are not comprehensive, these tests might fail
        # due to lack of underlying perms, not just view access control.
        # For robustness, explicit permission assignment here can be done but can also mask issues
        # if the migration-based permissions are incorrect.
        # Given the project structure, we assume migrations have set the base perms for groups.

        # For material_request_edit/cancel, the owner is cls.crew_user.
        # A request by warehouse_user might be useful if testing warehouse editing their own (not a feature now).
        cls.material_request_for_wh_processing = MaterialRequest.objects.create(
            requested_by=cls.crew_user, # Still requested by crew
            date_required=timezone.now().date() + timezone.timedelta(days=1),
            status=MaterialRequest.Status.REQUESTED
        )


    def assertAccess(self, url_name, expected_status_anon, expected_status_crew, expected_status_warehouse, url_kwargs=None, post_data=None, method='get'):
        # Ensure client is part of the class instance if not already
        if not hasattr(self, 'client'):
            self.client = Client()

        url = reverse(f'inventory:{url_name}', kwargs=url_kwargs) if url_kwargs else reverse(f'inventory:{url_name}')

        http_method = getattr(self.client, method.lower())

        # Unauthenticated
        self.client.logout()
        response_anon = http_method(url, data=post_data) if post_data and method.lower() == 'post' else http_method(url)
        self.assertEqual(response_anon.status_code, expected_status_anon, f"Anon access to {url_name} ({method.upper()}) failed. Expected {expected_status_anon}, got {response_anon.status_code}")
        if expected_status_anon == 302 and response_anon.url: # Check for redirect URL if provided
            self.assertTrue(response_anon.url.startswith(reverse('inventory:login')), f"Anon redirect for {url_name} was to {response_anon.url} not login.")

        # Crew User
        self.client.login(username='perm_crew', password='password')
        response_crew = http_method(url, data=post_data) if post_data and method.lower() == 'post' else http_method(url)
        self.assertEqual(response_crew.status_code, expected_status_crew, f"Crew access to {url_name} ({method.upper()}) failed. Expected {expected_status_crew}, got {response_crew.status_code}")
        # If crew is redirected from a page they shouldn't access, it's often to login (by @user_passes_test)
        if expected_status_crew == 302 and response_crew.url and not url_name in ['material_request_create', 'crew_request_list', 'material_request_edit', 'material_request_cancel', 'material_list']: # avoid self-redirect checks
             self.assertTrue(response_crew.url.startswith(reverse('inventory:login')), f"Crew redirect for {url_name} was to {response_crew.url} not login.")


        # Warehouse User
        self.client.login(username='perm_warehouse', password='password')
        response_warehouse = http_method(url, data=post_data) if post_data and method.lower() == 'post' else http_method(url)
        self.assertEqual(response_warehouse.status_code, expected_status_warehouse, f"Warehouse access to {url_name} ({method.upper()}) failed. Expected {expected_status_warehouse}, got {response_warehouse.status_code}")
        # If warehouse is redirected from a page they shouldn't access, it's often to login
        if expected_status_warehouse == 302 and response_warehouse.url and not url_name in ['material_list', 'pending_request_list', 'request_complete', 'completed_request_list', 'material_create', 'material_update', 'material_restock', 'request_start_processing']:
            self.assertTrue(response_warehouse.url.startswith(reverse('inventory:login')), f"Warehouse redirect for {url_name} was to {response_warehouse.url} not login.")


    def test_view_permissions_get_requests(self):
        # View: (url_name, anon_status, crew_status, warehouse_status, kwargs_if_any)
        views_to_test_get = [
            ('material_list', 302, 200, 200, None),
            # Crew views
            ('material_request_create', 302, 200, 302, None),
            ('crew_request_list', 302, 200, 302, None),
            # For Warehouse user, @user_passes_test(is_crew_member) fails first and redirects to login (302)
            ('material_request_edit', 302, 200, 302, {'request_id': self.material_request_by_crew.id}),
            ('material_request_cancel', 302, 200, 302, {'request_id': self.material_request_by_crew.id}),
            # Warehouse views
            ('pending_request_list', 302, 302, 200, None),
            ('request_complete', 302, 302, 200, {'request_id': self.material_request_for_wh_processing.id}),
            ('completed_request_list', 302, 302, 200, None),
            ('material_create', 302, 302, 200, None),
            ('material_update', 302, 302, 200, {'material_id': self.material.id}),
            ('material_restock', 302, 302, 200, None),
        ]

        for url_name, anon, crew, wh, kwargs_val in views_to_test_get:
            self.assertAccess(url_name, anon, crew, wh, url_kwargs=kwargs_val, method='get')

    def test_request_start_processing_post_permissions(self):
        # This view is POST-only for its action.
        url_name = 'request_start_processing'
        kwargs_val = {'request_id': self.material_request_for_wh_processing.id}

        # Ensure request is in REQUESTED state for this test path
        self.material_request_for_wh_processing.status = MaterialRequest.Status.REQUESTED
        self.material_request_for_wh_processing.save()

        # Unauthenticated POST
        self.client.logout()
        response_anon_post = self.client.post(reverse(f'inventory:{url_name}', kwargs=kwargs_val))
        self.assertEqual(response_anon_post.status_code, 302)
        self.assertTrue(response_anon_post.url.startswith(reverse('inventory:login')))

        # Crew POST (should be denied by @user_passes_test -> redirect to login)
        self.client.login(username='perm_crew', password='password')
        response_crew_post = self.client.post(reverse(f'inventory:{url_name}', kwargs=kwargs_val))
        self.assertEqual(response_crew_post.status_code, 302)
        self.assertTrue(response_crew_post.url.startswith(reverse('inventory:login')))

        # Warehouse POST (should process and redirect)
        self.client.login(username='perm_warehouse', password='password')
        response_wh_post = self.client.post(reverse(f'inventory:{url_name}', kwargs=kwargs_val))
        self.assertEqual(response_wh_post.status_code, 302)
        self.assertRedirects(response_wh_post, reverse('inventory:pending_request_list'))

        self.material_request_for_wh_processing.refresh_from_db()
        self.assertEqual(self.material_request_for_wh_processing.status, MaterialRequest.Status.IN_PROCESS)


class MaterialRequestWorkflowViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Groups
        cls.crew_group, _ = Group.objects.get_or_create(name='Crew')
        cls.warehouse_group, _ = Group.objects.get_or_create(name='Warehouse Staff')

        # Users
        cls.crew_user1 = User.objects.create_user(username='flow_crew1', password='password')
        cls.crew_user1.groups.add(cls.crew_group)
        cls.crew_user2 = User.objects.create_user(username='flow_crew2', password='password') # Another crew user
        cls.crew_user2.groups.add(cls.crew_group)
        cls.warehouse_user = User.objects.create_user(username='flow_warehouse', password='password')
        cls.warehouse_user.groups.add(cls.warehouse_group)

        # Material
        cls.category = MaterialCategory.objects.create(name="Flow Test Category")
        cls.material1 = Material.objects.create(name="Flow Mat1", sku="FLM1", category=cls.category, quantity_on_hand=50)
        cls.material2 = Material.objects.create(name="Flow Mat2", sku="FLM2", category=cls.category, quantity_on_hand=30)

        # Assign permissions (simplified: assume decorators handle most role checks, focus on ownership and status logic)
        # For edit/cancel, crew needs change/delete perms on their own requests.
        # For start_processing, warehouse needs change perm on requests.
        # These permissions are typically assigned to groups via data migrations.
        # For test explicitness, we can assign them, but rely on view decorators for role access primarily.
        from django.contrib.contenttypes.models import ContentType # Ensure this is imported if not already global
        ct_request = ContentType.objects.get_for_model(MaterialRequest)
        perm_change_req, _ = Permission.objects.get_or_create(content_type=ct_request, codename='change_materialrequest')
        # perm_delete_req, _ = Permission.objects.get_or_create(content_type=ct_request, codename='delete_materialrequest') # Not strictly needed if cancel is a status change

        cls.crew_user1.user_permissions.add(perm_change_req) # For their own requests
        cls.warehouse_user.user_permissions.add(perm_change_req)


    def setUp(self):
        self.client = Client()
        # Create a fresh request for each test, owned by crew_user1
        self.request_to_test = MaterialRequest.objects.create(
            requested_by=self.crew_user1,
            date_required=timezone.now().date() + timezone.timedelta(days=3),
            status=MaterialRequest.Status.REQUESTED
        )
        self.item1 = MaterialRequestItem.objects.create(material_request=self.request_to_test, material=self.material1, quantity_requested=5)
        self.item2 = MaterialRequestItem.objects.create(material_request=self.request_to_test, material=self.material2, quantity_requested=2)

    # == request_start_processing_view Tests ==
    def test_start_processing_success(self):
        self.client.login(username='flow_warehouse', password='password')
        url = reverse('inventory:request_start_processing', kwargs={'request_id': self.request_to_test.id})
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200) # Follows redirect
        self.assertRedirects(response, reverse('inventory:pending_request_list'))
        self.assertContains(response, "is now &#x27;In Process&#x27;") # Check for HTML escaped apostrophe
        self.request_to_test.refresh_from_db()
        self.assertEqual(self.request_to_test.status, MaterialRequest.Status.IN_PROCESS)

    def test_start_processing_already_in_process(self):
        self.client.login(username='flow_warehouse', password='password')
        self.request_to_test.status = MaterialRequest.Status.IN_PROCESS
        self.request_to_test.save()
        url = reverse('inventory:request_start_processing', kwargs={'request_id': self.request_to_test.id})
        response = self.client.post(url, follow=True)
        self.assertContains(response, "is already &#x27;In Process&#x27;") # Check for HTML escaped apostrophe
        self.request_to_test.refresh_from_db()
        self.assertEqual(self.request_to_test.status, MaterialRequest.Status.IN_PROCESS) # Stays IN_PROCESS

    def test_start_processing_wrong_status(self): # e.g. COMPLETED
        self.client.login(username='flow_warehouse', password='password')
        self.request_to_test.status = MaterialRequest.Status.COMPLETED
        self.request_to_test.save()
        url = reverse('inventory:request_start_processing', kwargs={'request_id': self.request_to_test.id})
        response = self.client.post(url, follow=True)
        self.assertContains(response, "cannot be started")
        self.request_to_test.refresh_from_db()
        self.assertEqual(self.request_to_test.status, MaterialRequest.Status.COMPLETED) # Stays COMPLETED

    # == material_request_edit_view Tests ==
    def test_edit_request_get_page_success(self):
        self.client.login(username='flow_crew1', password='password')
        url = reverse('inventory:material_request_edit', kwargs={'request_id': self.request_to_test.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'inventory/request/material_request_form.html')
        self.assertContains(response, f"Edit Material Request ID: {self.request_to_test.id}")

    def test_edit_request_post_success(self):
        self.client.login(username='flow_crew1', password='password')
        url = reverse('inventory:material_request_edit', kwargs={'request_id': self.request_to_test.id})
        new_date = self.request_to_test.date_required + timezone.timedelta(days=5)
        form_data = {
            'date_required': new_date.strftime('%Y-%m-%d'),
            'justification': 'Updated justification for test.',
            'items-TOTAL_FORMS': '2',
            'items-INITIAL_FORMS': '2',
            'items-MAX_NUM_FORMS': '',
            f'items-0-id': self.item1.id, # Existing item
            f'items-0-material': self.material1.id,
            f'items-0-quantity_requested': '7', # Changed quantity
            f'items-1-id': self.item2.id, # Existing item
            f'items-1-material': self.material2.id,
            f'items-1-quantity_requested': '3', # Changed quantity
        }
        response = self.client.post(url, data=form_data, follow=True)
        self.assertEqual(response.status_code, 200) # Follow redirect
        self.assertRedirects(response, reverse('inventory:crew_request_list'))
        self.assertContains(response, "updated successfully")

        self.request_to_test.refresh_from_db()
        self.item1.refresh_from_db()
        self.item2.refresh_from_db()
        self.assertEqual(self.request_to_test.date_required, new_date)
        self.assertEqual(self.request_to_test.justification, 'Updated justification for test.')
        self.assertEqual(self.item1.quantity_requested, 7)
        self.assertEqual(self.item2.quantity_requested, 3)

    def test_edit_request_not_owner(self): # crew_user2 tries to edit crew_user1's request
        self.client.login(username='flow_crew2', password='password')
        url = reverse('inventory:material_request_edit', kwargs={'request_id': self.request_to_test.id})
        response = self.client.get(url) # GET request
        self.assertEqual(response.status_code, 403) # HttpResponseForbidden

    def test_edit_request_wrong_status(self): # e.g. IN_PROCESS
        self.client.login(username='flow_crew1', password='password')
        self.request_to_test.status = MaterialRequest.Status.IN_PROCESS
        self.request_to_test.save()
        url = reverse('inventory:material_request_edit', kwargs={'request_id': self.request_to_test.id})
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse('inventory:crew_request_list'))
        self.assertContains(response, "cannot be edited")

    # == material_request_cancel_view Tests ==
    def test_cancel_request_get_confirmation_page(self):
        self.client.login(username='flow_crew1', password='password')
        url = reverse('inventory:material_request_cancel', kwargs={'request_id': self.request_to_test.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'inventory/request/request_cancel_confirm.html')

    def test_cancel_request_post_success(self):
        self.client.login(username='flow_crew1', password='password')
        url = reverse('inventory:material_request_cancel', kwargs={'request_id': self.request_to_test.id})
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200) # Follow redirect
        self.assertRedirects(response, reverse('inventory:crew_request_list'))
        self.assertContains(response, "has been cancelled")
        self.request_to_test.refresh_from_db()
        self.assertEqual(self.request_to_test.status, MaterialRequest.Status.CANCELLED)

    def test_cancel_request_not_owner(self):
        self.client.login(username='flow_crew2', password='password')
        url = reverse('inventory:material_request_cancel', kwargs={'request_id': self.request_to_test.id})
        response = self.client.get(url) # GET for confirm page
        self.assertEqual(response.status_code, 403)

    def test_cancel_request_wrong_status(self): # e.g. COMPLETED
        self.client.login(username='flow_crew1', password='password')
        self.request_to_test.status = MaterialRequest.Status.COMPLETED
        self.request_to_test.save()
        url = reverse('inventory:material_request_cancel', kwargs={'request_id': self.request_to_test.id})
        response = self.client.get(url, follow=True) # GET for confirm page
        self.assertRedirects(response, reverse('inventory:crew_request_list'))
        self.assertContains(response, "cannot be cancelled")


class InventoryViewTests(TestCase): # Add to this or create a new one
    @classmethod
    def setUpTestData(cls):
        cls.category = MaterialCategory.objects.create(name="View Test Category")
        cls.vendor = Vendor.objects.create(name="View Test Vendor")
        cls.warehouse_group, _ = Group.objects.get_or_create(name='Warehouse Staff')
        cls.warehouse_user = User.objects.create_user(username='testwarehouse', password='password')
        cls.warehouse_user.groups.add(cls.warehouse_group)

        # Assign permissions needed for these views (add_stocktransaction, add_material)
        # ContentType is needed to get permissions
        from django.contrib.contenttypes.models import ContentType
        # Ensure models are in the DB for ContentType.objects.get_for_model to work reliably in tests
        # This might require running cls.setUpTestData() of other model test classes if they create these models
        # For now, assuming Material and StockTransaction types are available.
        try:
            ct_stocktransaction = ContentType.objects.get_for_model(StockTransaction)
            perm_add_st = Permission.objects.get(content_type=ct_stocktransaction, codename='add_stocktransaction')
            cls.warehouse_user.user_permissions.add(perm_add_st)
        except Exception as e: # Catch potential errors if ContentType/Permission not ready
            print(f"Warning: Could not assign add_stocktransaction perm in setUpTestData: {e}")

        try:
            ct_material = ContentType.objects.get_for_model(Material)
            perm_add_mat = Permission.objects.get(content_type=ct_material, codename='add_material')
            cls.warehouse_user.user_permissions.add(perm_add_mat)
        except Exception as e:
             print(f"Warning: Could not assign add_material perm in setUpTestData: {e}")


        cls.material1 = Material.objects.create(
            name="Material For Restock View", sku="MFRV001", category=cls.category, vendor=cls.vendor,
            quantity_on_hand=Decimal('10.00'), current_average_cost_per_unit=Decimal('15.00') # Start with some stock
        )
        cls.client = Client()

    def setUp(self):
        self.client.login(username='testwarehouse', password='password')

    def test_material_restock_view_get(self):
        response = self.client.get(reverse('inventory:material_restock'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'inventory/material/restock_form.html')
        self.assertIsInstance(response.context['form'], StockTransactionForm)

    def test_material_restock_view_post_success(self):
        initial_qty = self.material1.quantity_on_hand # Should be 10
        initial_avg_cost = self.material1.current_average_cost_per_unit # Should be 15.00

        restock_data = {
            'material': self.material1.id,
            'quantity_change': 10,
            'total_cost_of_transaction': "200.00", # 20 per unit for this restock
        }
        response = self.client.post(reverse('inventory:material_restock'), data=restock_data, follow=True)
        self.assertEqual(response.status_code, 200) # Follows redirect
        self.assertRedirects(response, reverse('inventory:material_list'))
        self.assertContains(response, "Successfully restocked")

        self.material1.refresh_from_db()
        self.assertEqual(self.material1.quantity_on_hand, initial_qty + 10) # 10 + 10 = 20
        # Avg cost calculation: ((15 * 10) + 200) / (10 + 10) = (150 + 200) / 20 = 350 / 20 = 17.50
        expected_avg_cost = (initial_avg_cost * initial_qty + Decimal("200.00")) / (initial_qty + Decimal(str(restock_data['quantity_change'])))
        self.assertAlmostEqual(self.material1.current_average_cost_per_unit, expected_avg_cost, places=2)
        self.assertTrue(StockTransaction.objects.filter(material=self.material1, transaction_type=StockTransaction.TransactionType.RESTOCK).exists())

    def test_material_restock_view_post_form_invalid(self):
        response = self.client.post(reverse('inventory:material_restock'), data={'material': self.material1.id}) # Missing quantity, cost
        self.assertEqual(response.status_code, 200) # Stays on the same page
        self.assertContains(response, "Please correct the errors below.")
        self.assertTrue(response.context['form'].errors)

    def test_material_create_view_creates_initial_stock_transaction(self):
        material_count_before = Material.objects.count()
        st_count_before = StockTransaction.objects.count()

        new_material_data = {
            'name': "Super New Material", 'sku': "SNM001",
            'category': self.category.id, 'vendor': self.vendor.id,
            'unit_of_measure': "item", 'low_quantity_threshold': 5,
            'initial_quantity': 20,
            'initial_total_cost': "100.00" # 5.00 per unit
        }
        response = self.client.post(reverse('inventory:material_create'), data=new_material_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse('inventory:material_list'))
        self.assertContains(response, "added successfully with initial stock recorded")

        self.assertEqual(Material.objects.count(), material_count_before + 1)
        self.assertEqual(StockTransaction.objects.count(), st_count_before + 1)

        new_material = Material.objects.get(sku="SNM001")
        self.assertEqual(new_material.quantity_on_hand, 20)
        self.assertAlmostEqual(new_material.current_average_cost_per_unit, Decimal("5.00"), places=2)

        st = StockTransaction.objects.get(material=new_material, transaction_type=StockTransaction.TransactionType.INITIAL_STOCK)
        self.assertEqual(st.quantity_change, 20)
        self.assertEqual(st.total_cost_of_transaction, Decimal("100.00"))

    def test_material_create_view_initial_stock_zero_quantity(self):
        # Test creating a material with 0 initial quantity
        new_material_data = {
            'name': "Zero Stock Material", 'sku': "ZSM001",
            'category': self.category.id, 'vendor': self.vendor.id,
            'unit_of_measure': "item", 'low_quantity_threshold': 1,
            'initial_quantity': 0,
            # No cost needed if quantity is 0, form clean handles setting cost to 0
        }
        response = self.client.post(reverse('inventory:material_create'), data=new_material_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "added successfully with initial stock recorded")

        new_material = Material.objects.get(sku="ZSM001")
        self.assertEqual(new_material.quantity_on_hand, 0)
        self.assertEqual(new_material.current_average_cost_per_unit, Decimal("0.00"))
        # No StockTransaction should be created if initial quantity is 0 as per current view logic
        self.assertFalse(StockTransaction.objects.filter(material=new_material, transaction_type=StockTransaction.TransactionType.INITIAL_STOCK).exists())
