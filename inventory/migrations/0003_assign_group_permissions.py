from django.db import migrations

def assign_permissions(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    # Get content type for the Material model (or other relevant models)
    # Ensure your app_label and model_name are correct.
    # For 'inventory.Material', app_label is 'inventory', model_name is 'material'.
    try:
        material_content_type = ContentType.objects.get(app_label='inventory', model='material')
        material_request_content_type = ContentType.objects.get(app_label='inventory', model='materialrequest')
    except ContentType.DoesNotExist:
        # This might happen if the models were removed or renamed.
        # Handle appropriately, perhaps by skipping or logging.
        print("Warning: ContentType for Material or MaterialRequest not found. Skipping permission assignment.")
        return

    # Define permissions for Material model
    material_permissions = Permission.objects.filter(content_type=material_content_type)
    view_material_perm = material_permissions.filter(codename='view_material').first()
    add_material_perm = material_permissions.filter(codename='add_material').first()
    change_material_perm = material_permissions.filter(codename='change_material').first()
    delete_material_perm = material_permissions.filter(codename='delete_material').first()

    # Define permissions for MaterialRequest model
    material_request_permissions = Permission.objects.filter(content_type=material_request_content_type)
    view_materialrequest_perm = material_request_permissions.filter(codename='view_materialrequest').first()
    add_materialrequest_perm = material_request_permissions.filter(codename='add_materialrequest').first()
    change_materialrequest_perm = material_request_permissions.filter(codename='change_materialrequest').first() # For status updates by warehouse
    # delete_materialrequest_perm = material_request_permissions.filter(codename='delete_materialrequest').first()


    # Assign permissions to "Warehouse Staff"
    warehouse_staff_group, created = Group.objects.get_or_create(name='Warehouse Staff')
    warehouse_perms_to_add = []
    if view_material_perm: warehouse_perms_to_add.append(view_material_perm)
    if add_material_perm: warehouse_perms_to_add.append(add_material_perm)
    if change_material_perm: warehouse_perms_to_add.append(change_material_perm)
    if delete_material_perm: warehouse_perms_to_add.append(delete_material_perm)

    if view_materialrequest_perm: warehouse_perms_to_add.append(view_materialrequest_perm)
    # Warehouse staff might not add requests for themselves, but they change status of existing ones.
    if change_materialrequest_perm: warehouse_perms_to_add.append(change_materialrequest_perm)
    # if delete_materialrequest_perm: warehouse_perms_to_add.append(delete_materialrequest_perm) # If they can delete requests

    if warehouse_perms_to_add:
        warehouse_staff_group.permissions.add(*warehouse_perms_to_add)

    # Assign permissions to "Crew"
    crew_group, created = Group.objects.get_or_create(name='Crew')
    crew_perms_to_add = []
    if view_material_perm: crew_perms_to_add.append(view_material_perm) # Crew can view materials
    if add_materialrequest_perm: crew_perms_to_add.append(add_materialrequest_perm) # Crew can create requests
    if view_materialrequest_perm: crew_perms_to_add.append(view_materialrequest_perm) # Crew can view their own requests (enforced by view logic)

    if crew_perms_to_add:
        crew_group.permissions.add(*crew_perms_to_add)

def remove_permissions(apps, schema_editor):
    # This function could be written to remove these specific permissions if needed,
    # but often, data migrations that add permissions don't provide a granular reverse
    # because other things might depend on those permissions.
    # For simplicity, we can leave it blank or just print a message.
    # If you absolutely need to reverse, you'd fetch the groups and remove the specific permissions.
    Group = apps.get_model('auth', 'Group')
    # Example:
    # warehouse_staff_group = Group.objects.filter(name='Warehouse Staff').first()
    # if warehouse_staff_group:
    #     warehouse_staff_group.permissions.clear() # Or remove specific ones
    # crew_group = Group.objects.filter(name='Crew').first()
    # if crew_group:
    #     crew_group.permissions.clear()
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0002_create_user_groups'), # Depends on the group creation migration
        # Implicitly depends on auth and contenttypes migrations
    ]

    operations = [
        migrations.RunPython(assign_permissions, remove_permissions),
    ]
