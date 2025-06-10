from django.db import migrations

def assign_stock_transaction_permissions(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    try:
        stock_transaction_content_type = ContentType.objects.get(
            app_label='inventory',
            model='stocktransaction'
        )
    except ContentType.DoesNotExist:
        print("Warning: ContentType for StockTransaction not found. Skipping permission assignment.")
        return

    # Get relevant permissions for StockTransaction
    add_stocktransaction_perm = Permission.objects.filter(
        content_type=stock_transaction_content_type,
        codename='add_stocktransaction'
    ).first()
    view_stocktransaction_perm = Permission.objects.filter(
        content_type=stock_transaction_content_type,
        codename='view_stocktransaction'
    ).first()
    change_stocktransaction_perm = Permission.objects.filter(
        content_type=stock_transaction_content_type,
        codename='change_stocktransaction'
    ).first()
    delete_stocktransaction_perm = Permission.objects.filter(
        content_type=stock_transaction_content_type,
        codename='delete_stocktransaction'
    ).first()

    # Assign permissions to "Warehouse Staff"
    warehouse_staff_group, created = Group.objects.get_or_create(name='Warehouse Staff')

    stock_perms_to_add = []
    if add_stocktransaction_perm: stock_perms_to_add.append(add_stocktransaction_perm)
    if view_stocktransaction_perm: stock_perms_to_add.append(view_stocktransaction_perm)
    if change_stocktransaction_perm: stock_perms_to_add.append(change_stocktransaction_perm)
    if delete_stocktransaction_perm: stock_perms_to_add.append(delete_stocktransaction_perm)

    if stock_perms_to_add:
        warehouse_staff_group.permissions.add(*stock_perms_to_add)
        print(f"Assigned StockTransaction permissions to 'Warehouse Staff' group.")

def remove_stock_transaction_permissions(apps, schema_editor):
    # For simplicity, this reverse function could remove the added permissions
    # or be a pass if fine-grained rollback isn't critical for this data migration.
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0005_alter_material_current_average_cost_per_unit_and_more'), # Depends on StockTransaction model creation
        ('inventory', '0002_create_user_groups'), # Depends on group creation
        # Auth app migrations for Group/Permission models are implicit
    ]

    operations = [
        migrations.RunPython(assign_stock_transaction_permissions, remove_stock_transaction_permissions),
    ]
