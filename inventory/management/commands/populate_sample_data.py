import random
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.utils import timezone
from decimal import Decimal
from django.db.models import F # Import F for stock deduction simulation

from inventory.models import MaterialCategory, Vendor, Material, MaterialRequest, MaterialRequestItem

class Command(BaseCommand):
    help = 'Populates the database with sample data for the inventory app'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting data population...'))

        # Get or create Groups (should exist from migrations, but get_or_create is safe)
        crew_group, _ = Group.objects.get_or_create(name='Crew')
        warehouse_group, _ = Group.objects.get_or_create(name='Warehouse Staff')

        # Create Sample Users if they don't exist
        crew_user_created_flag = False
        if not User.objects.filter(username='crewuser').exists():
            crew_user = User.objects.create_user(username='crewuser', password='crewpassword', email='crew@example.com', first_name='Crew', last_name='User')
            crew_user.groups.add(crew_group)
            self.stdout.write(self.style.SUCCESS('Created Crew User (crewuser/crewpassword)'))
            crew_user_created_flag = True
        else:
            crew_user = User.objects.get(username='crewuser')
            if not crew_user.groups.filter(name='Crew').exists():
                crew_user.groups.add(crew_group)
                self.stdout.write(self.style.SUCCESS(f'Added {crew_user.username} to Crew group.'))


        warehouse_user_created_flag = False
        if not User.objects.filter(username='warehouseuser').exists():
            warehouse_user = User.objects.create_user(username='warehouseuser', password='warehousepassword', email='warehouse@example.com', first_name='Warehouse', last_name='Staff')
            warehouse_user.groups.add(warehouse_group)
            self.stdout.write(self.style.SUCCESS('Created Warehouse User (warehouseuser/warehousepassword)'))
            warehouse_user_created_flag = True
        else:
            warehouse_user = User.objects.get(username='warehouseuser')
            if not warehouse_user.groups.filter(name='Warehouse Staff').exists():
                warehouse_user.groups.add(warehouse_group)
                self.stdout.write(self.style.SUCCESS(f'Added {warehouse_user.username} to Warehouse Staff group.'))

        # Create Material Categories
        categories_data = [
            {'name': 'Electrical Components', 'description': 'Resistors, capacitors, LEDs, etc.'},
            {'name': 'Fasteners', 'description': 'Nuts, bolts, screws, washers.'},
            {'name': 'Raw Materials', 'description': 'Sheet metal, plastic pellets, wood.'},
            {'name': 'Safety Gear', 'description': 'Gloves, goggles, helmets.'},
            {'name': 'Tools', 'description': 'Hand tools and power tools accessories.'},
        ]
        categories = {}
        for cat_data in categories_data:
            cat, created = MaterialCategory.objects.get_or_create(name=cat_data['name'], defaults={'description': cat_data['description']})
            categories[cat.name] = cat
            if created: self.stdout.write(self.style.SUCCESS(f"Created category: {cat.name}"))

        # Create Vendors
        vendors_data = [
            {'name': 'Spark Components Inc.', 'contact_person': 'Alice Spark', 'email': 'sales@spark.com', 'phone_number': '555-0101', 'address': '123 Circuit Lane'},
            {'name': 'BoltDepot', 'contact_person': 'Bob Bolt', 'email': 'orders@boltdepot.com', 'phone_number': '555-0202', 'address': '456 Thread St'},
            {'name': 'MetalWorks Ltd.', 'contact_person': 'Charlie Metal', 'email': 'info@metalworks.com', 'phone_number': '555-0303', 'address': '789 Alloy Ave'},
            {'name': 'SafeGuard Supply', 'contact_person': 'Diana Shield', 'email': 'contact@safeguard.com', 'phone_number': '555-0404', 'address': '101 Protection Rd'},
        ]
        vendors = {}
        for vend_data in vendors_data:
            vend, created = Vendor.objects.get_or_create(name=vend_data['name'], defaults=vend_data)
            vendors[vend.name] = vend
            if created: self.stdout.write(self.style.SUCCESS(f"Created vendor: {vend.name}"))

        # Ensure at least one category and vendor for fallback
        if not categories:
            default_cat, _ = MaterialCategory.objects.get_or_create(name='Default Category', defaults={'description':'Default'})
            categories['Default Category'] = default_cat
        if not vendors:
            default_vend, _ = Vendor.objects.get_or_create(name='Default Vendor', defaults={'email':'default@vendor.com'})
            vendors['Default Vendor'] = default_vend

        default_category_key = list(categories.keys())[0]
        default_vendor_key = list(vendors.keys())[0]

        # Create Materials
        materials_data = [
            {'name': 'LED - Red 5mm', 'sku': 'LED-R5', 'manufacturer': 'BrightChip', 'category': categories.get('Electrical Components', categories[default_category_key]), 'vendor': vendors.get('Spark Components Inc.', vendors[default_vendor_key]), 'unit_of_measure': 'piece', 'quantity_on_hand': 500, 'low_quantity_threshold': 50, 'current_average_cost_per_unit': Decimal('0.05')},
            {'name': 'M3x10mm Bolt', 'sku': 'BLT-M3X10', 'manufacturer': 'SteelParts', 'category': categories.get('Fasteners', categories[default_category_key]), 'vendor': vendors.get('BoltDepot', vendors[default_vendor_key]), 'unit_of_measure': 'piece', 'quantity_on_hand': 2000, 'low_quantity_threshold': 200, 'current_average_cost_per_unit': Decimal('0.02')},
            {'name': 'Aluminum Sheet 1mm', 'sku': 'AL-SHT-1MM', 'manufacturer': 'MetalCo', 'category': categories.get('Raw Materials', categories[default_category_key]), 'vendor': vendors.get('MetalWorks Ltd.', vendors[default_vendor_key]), 'unit_of_measure': 'sq meter', 'quantity_on_hand': 100, 'low_quantity_threshold': 10, 'current_average_cost_per_unit': Decimal('15.75')},
            {'name': 'Safety Gloves - Large', 'sku': 'SGLV-L', 'manufacturer': 'SafeHands', 'category': categories.get('Safety Gear', categories[default_category_key]), 'vendor': vendors.get('SafeGuard Supply', vendors[default_vendor_key]), 'unit_of_measure': 'pair', 'quantity_on_hand': 150, 'low_quantity_threshold': 20, 'current_average_cost_per_unit': Decimal('3.50')},
            {'name': 'Capacitor 10uF', 'sku': 'CAP-10UF', 'manufacturer': 'CircuitGoods', 'category': categories.get('Electrical Components', categories[default_category_key]), 'vendor': vendors.get('Spark Components Inc.', vendors[default_vendor_key]), 'unit_of_measure': 'piece', 'quantity_on_hand': 1200, 'low_quantity_threshold': 100, 'current_average_cost_per_unit': Decimal('0.12')},
        ]

        created_materials_for_requests = []
        for mat_data in materials_data:
            mat, created = Material.objects.get_or_create(sku=mat_data['sku'], defaults=mat_data)
            if created:
                created_materials_for_requests.append(mat)
                self.stdout.write(self.style.SUCCESS(f"Created material: {mat.name}"))

        if not created_materials_for_requests and Material.objects.exists():
            created_materials_for_requests = list(Material.objects.all()[:3]) # Need at least 3 for varied requests

        # Create Sample Material Requests for crew_user
        # Only if the crew_user was just created or has no requests yet.
        if crew_user and (crew_user_created_flag or not MaterialRequest.objects.filter(requested_by=crew_user).exists()):
            if len(created_materials_for_requests) >= 1:
                request1 = MaterialRequest.objects.create(
                    requested_by=crew_user,
                    date_required=timezone.now().date() + timezone.timedelta(days=7),
                    status=MaterialRequest.Status.REQUESTED, # Changed from PENDING
                    justification='For upcoming Project X'
                )
                MaterialRequestItem.objects.create(material_request=request1, material=created_materials_for_requests[0], quantity_requested=10)
                if len(created_materials_for_requests) >= 2:
                    MaterialRequestItem.objects.create(material_request=request1, material=created_materials_for_requests[1], quantity_requested=5)
                self.stdout.write(self.style.SUCCESS(f"Created PENDING sample material request ID {request1.id} for {crew_user.username}"))

            if len(created_materials_for_requests) >= 3: # Need a third distinct material for the second request
                 request2 = MaterialRequest.objects.create(
                    requested_by=crew_user,
                    date_required=timezone.now().date() + timezone.timedelta(days=-2), # Required in the past
                    updated_at = timezone.now().date() + timezone.timedelta(days=-1), # Completed yesterday
                    status=MaterialRequest.Status.COMPLETED,
                    justification='Restock for general use, already fulfilled'
                )
                 item1_req2 = MaterialRequestItem.objects.create(material_request=request2, material=created_materials_for_requests[2], quantity_requested=20, fulfilled_quantity=20)

                 # Simulate stock deduction for this completed order if it wasn't already done by app logic
                 # THIS IS RISKY if the command is run multiple times without checks.
                 # The quantity_on_hand for created_materials_for_requests[2] is set above.
                 # Only deduct if its current stock is what was set initially.
                 material_for_completed_request = created_materials_for_requests[2]
                 # Check if this is a newly created material or if its stock matches initial sample data.
                 # This is a simplification; real stock management is complex.
                 # For sample data, we assume initial stock was as per materials_data.
                 # We find the original quantity_on_hand for this material if it was in materials_data
                 original_stock = None
                 for m_data in materials_data:
                     if m_data['sku'] == material_for_completed_request.sku:
                         original_stock = m_data['quantity_on_hand']
                         break

                 if original_stock is not None and material_for_completed_request.quantity_on_hand == original_stock:
                    material_for_completed_request.quantity_on_hand = F('quantity_on_hand') - item1_req2.fulfilled_quantity
                    material_for_completed_request.save()
                    self.stdout.write(self.style.SUCCESS(f"Deducted stock for completed sample request for {material_for_completed_request.name}."))
                 elif original_stock is None: # Material was not in the initial list, might be pre-existing
                     pass # Don't touch stock for pre-existing materials in this simplified script

                 self.stdout.write(self.style.SUCCESS(f"Created COMPLETED sample material request ID {request2.id} for {crew_user.username}"))

        self.stdout.write(self.style.SUCCESS('Data population complete.'))
