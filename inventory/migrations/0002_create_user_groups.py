from django.db import migrations

def create_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.bulk_create([
        Group(name='Crew'),
        Group(name='Warehouse Staff'),
    ])

def remove_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=['Crew', 'Warehouse Staff']).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0001_initial'), # Depends on the initial schema migration of inventory app
        # It might also implicitly depend on auth app's migrations to ensure Group model exists.
        # Django handles this dependency automatically if 'auth' is in INSTALLED_APPS before 'inventory'.
    ]

    operations = [
        migrations.RunPython(create_groups, remove_groups),
    ]
