from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.forms import inlineformset_factory, Select
from django.db import transaction # To ensure atomicity
from django.db.models import Q, F # Import F object
from django.contrib import messages # For user feedback
from django.utils import timezone # Ensure timezone is imported
from django.http import HttpResponseForbidden, JsonResponse # For access control & JSON
from django_select2.views import AutoResponseView # For select2 AJAX view
from django_select2.forms import ModelSelect2Widget # For select2 form widget
from django.urls import reverse_lazy # For data_url in widget
from django import forms # For forms.NumberInput

from .forms import LoginForm, MaterialRequestForm, MaterialForm, StockTransactionForm
from .models import Material, MaterialRequest, MaterialRequestItem, MaterialCategory, Vendor, StockTransaction

# Helper functions for role checks
def is_crew_member(user):
    return user.is_authenticated and user.groups.filter(name='Crew').exists()

def is_warehouse_staff(user):
    return user.is_authenticated and user.groups.filter(name='Warehouse Staff').exists()

# Authentication views (login_view, logout_view) remain the same
def login_view(request):
    if request.user.is_authenticated:
        return redirect('inventory:material_list')
    form = LoginForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('inventory:material_list')
            else:
                form.add_error(None, "Invalid username or password.")
    context = {'form': form, 'title': 'Login'}
    return render(request, 'inventory/auth/login.html', context)

def logout_view(request):
    if request.method == 'POST':
        logout(request)
        return redirect('inventory:login')
    return redirect('inventory:login')

# Inventory View (material_list_view) remains the same
@login_required
def material_list_view(request):
    query = request.GET.get('q')
    materials = Material.objects.select_related('category', 'vendor').all()
    if query:
        search_filters = Q(name__icontains=query) | Q(sku__icontains=query) | \
                         Q(manufacturer__icontains=query) | Q(category__name__icontains=query) | \
                         Q(vendor__name__icontains=query) | Q(unit_of_measure__icontains=query)
        materials = materials.filter(search_filters)
    context = {'materials': materials, 'search_query': query or "", 'title': 'Material Inventory'}
    return render(request, 'inventory/material/material_list.html', context)

# Material Requests (Crew)
@login_required
@user_passes_test(is_crew_member, login_url='inventory:login')
def material_request_create_view(request):
    MaterialRequestItemFormSet = inlineformset_factory(
        MaterialRequest,
        MaterialRequestItem,
        fields=('material', 'quantity_requested'),
        extra=1,
        can_delete=True,
        widgets={
            'material': ModelSelect2Widget(
                model=Material,
                search_fields=['name__icontains', 'sku__icontains'],
                attrs={'data-placeholder': 'Search for a material...', 'style': 'width: 100%;'},
                data_url=reverse_lazy('inventory:material_ajax_search')
            ),
            'quantity_requested': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'})
        }
    )

    if request.method == 'POST':
        form = MaterialRequestForm(request.POST)
        material_request_instance = MaterialRequest(requested_by=request.user)
        formset = MaterialRequestItemFormSet(request.POST, request.FILES, instance=material_request_instance, prefix='items')

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    material_request_instance.date_required = form.cleaned_data['date_required']
                    material_request_instance.justification = form.cleaned_data['justification']
                    # status defaults to REQUESTED via model
                    material_request_instance.save()
                    formset.instance = material_request_instance
                    formset.save()
                messages.success(request, 'Material request submitted successfully!')
                return redirect('inventory:crew_request_list')
            except Exception as e:
                messages.error(request, f'Error submitting request: {e}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = MaterialRequestForm()
        formset = MaterialRequestItemFormSet(instance=MaterialRequest(requested_by=request.user), prefix='items')

    context = {
        'form': form,
        'formset': formset,
        'title': 'Create Material Request'
    }
    return render(request, 'inventory/request/material_request_form.html', context)


@login_required
@user_passes_test(is_crew_member, login_url='inventory:login')
def material_request_cancel_view(request, request_id):
    material_request = get_object_or_404(MaterialRequest, id=request_id)

    # Authorization checks
    if material_request.requested_by != request.user:
        return HttpResponseForbidden("You are not authorized to cancel this request.")

    if material_request.status != MaterialRequest.Status.REQUESTED:
        messages.error(request, f"This request cannot be cancelled as its status is '{material_request.get_status_display()}'.")
        return redirect('inventory:crew_request_list')

    if request.method == 'POST': # Require POST for cancellation
        try:
            with transaction.atomic():
                material_request.status = MaterialRequest.Status.CANCELLED
                material_request.updated_at = timezone.now() # Explicitly update timestamp
                material_request.save(update_fields=['status', 'updated_at'])
            messages.success(request, f"Material Request ID {material_request.id} has been cancelled.")
        except Exception as e: # pragma: no cover
            messages.error(request, f"Error cancelling request: {e}")
            # Log error e
        return redirect('inventory:crew_request_list')
    else: # GET request could show a confirmation page
        context = {
            'request_to_cancel': material_request,
            'title': f"Confirm Cancellation for Request ID: {material_request.id}"
        }
        return render(request, 'inventory/request/request_cancel_confirm.html', context)


@login_required
@user_passes_test(is_crew_member, login_url='inventory:login')
def material_request_edit_view(request, request_id):
    material_request = get_object_or_404(MaterialRequest, id=request_id)

    # Authorization checks
    if material_request.requested_by != request.user:
        # messages.error(request, "You are not authorized to edit this request.")
        # return redirect('inventory:crew_request_list')
        return HttpResponseForbidden("You are not authorized to edit this request.")

    if material_request.status != MaterialRequest.Status.REQUESTED:
        messages.error(request, f"This request cannot be edited as its status is '{material_request.get_status_display()}'.")
        return redirect('inventory:crew_request_list')

    MaterialRequestItemFormSet = inlineformset_factory(
        MaterialRequest,
        MaterialRequestItem,
        fields=('material', 'quantity_requested'),
        extra=1,
        can_delete=True, # Allow items to be deleted
        widgets={
            'material': ModelSelect2Widget(
                model=Material,
                search_fields=['name__icontains', 'sku__icontains'],
                    attrs={
                        'data-placeholder': 'Search for a material...',
                        'style': 'width: 100%;',
                        'data-minimum-input-length': '0' # Add/Ensure this
                    },
                data_url=reverse_lazy('inventory:material_ajax_search')
            ),
            'quantity_requested': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'})
        }
    )

    if request.method == 'POST':
        form = MaterialRequestForm(request.POST, instance=material_request)
        formset = MaterialRequestItemFormSet(request.POST, request.FILES, instance=material_request, prefix='items')

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    updated_request = form.save(commit=False)
                    # requested_by is already set and should not change here
                    updated_request.updated_at = timezone.now() # Explicitly update timestamp
                    updated_request.save()

                    formset.save() # Save changes to items (new, updated, deleted)

                messages.success(request, f"Material Request ID {material_request.id} updated successfully.")
                return redirect('inventory:crew_request_list')
            except Exception as e: # pragma: no cover
                messages.error(request, f"Error updating request: {e}")
                # Log error e
        else:
            messages.error(request, "Please correct the errors below.")
    else: # GET request
        form = MaterialRequestForm(instance=material_request)
        formset = MaterialRequestItemFormSet(instance=material_request, prefix='items')

    context = {
        'form': form,
        'formset': formset,
        'title': f'Edit Material Request ID: {material_request.id}',
        'material_request_instance': material_request # For template to know it's an edit
    }
    return render(request, 'inventory/request/material_request_form.html', context) # Reusing the create form template


@login_required
@user_passes_test(is_crew_member, login_url='inventory:login')
def crew_request_list_view(request):
    user_requests = MaterialRequest.objects.filter(requested_by=request.user) \
                                           .prefetch_related('request_items__material') \
                                           .order_by('-created_at')
    context = {
        'requests': user_requests,
        'title': 'My Material Requests'
    }
    return render(request, 'inventory/request/crew_request_list.html', context)

# Order Fulfillment (Warehouse Staff)
@login_required
@user_passes_test(is_warehouse_staff, login_url='inventory:login')
def pending_request_list_view(request):
    pending_requests = MaterialRequest.objects.filter(
        status__in=[MaterialRequest.Status.REQUESTED, MaterialRequest.Status.IN_PROCESS]
    ).select_related('requested_by').prefetch_related('request_items__material').order_by('date_required', 'created_at')

    context = {
        'requests': pending_requests,
        'title': 'Pending & In Process Material Requests' # Updated title
    }
    return render(request, 'inventory/request/pending_request_list.html', context)

@login_required
@user_passes_test(is_warehouse_staff, login_url='inventory:login')
@transaction.atomic # Ensure status update is atomic
def request_start_processing_view(request, request_id):
    material_request = get_object_or_404(MaterialRequest, id=request_id)

    if request.method == 'POST': # Ensure this is a POST request
        if material_request.status == MaterialRequest.Status.REQUESTED:
            material_request.status = MaterialRequest.Status.IN_PROCESS
            material_request.updated_at = timezone.now() # Update timestamp
            material_request.save(update_fields=['status', 'updated_at'])
            messages.success(request, f"Request ID {material_request.id} is now 'In Process'.")
        elif material_request.status == MaterialRequest.Status.IN_PROCESS:
            messages.info(request, f"Request ID {material_request.id} is already 'In Process'.")
        else:
            messages.error(request, f"Request ID {material_request.id} cannot be started. Current status: {material_request.get_status_display()}.")
    else:
        messages.error(request, "Invalid request method to start processing.")

    # Redirect to a list that can show IN_PROCESS items, or back to pending list which will now be empty of this item.
    # For now, redirecting to pending list. A dedicated "In Process" list might be better.
    return redirect('inventory:pending_request_list')


@login_required
@user_passes_test(is_warehouse_staff, login_url='inventory:login')
def request_complete_view(request, request_id):
    material_request = get_object_or_404(
        MaterialRequest.objects.select_related('requested_by')
                              .prefetch_related('request_items__material'),
        id=request_id
    )

    if material_request.status == MaterialRequest.Status.COMPLETED:
        messages.info(request, f"Request ID {material_request.id} has already been completed.")
        return redirect('inventory:completed_request_list')

    # Allow completion if REQUESTED or IN_PROCESS
    if material_request.status not in [MaterialRequest.Status.REQUESTED, MaterialRequest.Status.IN_PROCESS]:
        messages.error(request, f"Request ID {material_request.id} cannot be completed. Current status: {material_request.get_status_display()}.")
        return redirect('inventory:pending_request_list') # Or wherever appropriate

    if request.method == 'POST':
        form_errors = {}
        items_data = [] # To store validated fulfilled quantities

        with transaction.atomic(): # Use a transaction for the entire process
            sid = transaction.savepoint() # Savepoint for potential rollback on validation errors

            for item in material_request.request_items.all():
                field_name = f'fulfilled_quantity_{item.id}'
                try:
                    fulfilled_quantity_str = request.POST.get(field_name)
                    if fulfilled_quantity_str is None or fulfilled_quantity_str == '':
                        form_errors[item.id] = "This field is required."
                        continue

                    fulfilled_quantity = int(fulfilled_quantity_str)

                    if fulfilled_quantity < 0:
                        form_errors[item.id] = "Quantity cannot be negative."
                    elif fulfilled_quantity > item.material.quantity_on_hand:
                        form_errors[item.id] = f"Cannot fulfill {fulfilled_quantity}. Only {item.material.quantity_on_hand} available."
                    # Optional: Validate against requested quantity if you don't want to over-fulfill
                    # For now, we allow fulfilling up to available stock, even if it's less than requested,
                    # or even 0 if warehouse decides so.
                    # elif fulfilled_quantity > item.quantity_requested:
                    #     form_errors[item.id] = f"Cannot fulfill more than requested ({item.quantity_requested})."

                    if item.id not in form_errors:
                        items_data.append({
                            'item_instance': item,
                            'material_instance': item.material,
                            'fulfilled_quantity': fulfilled_quantity
                        })
                except ValueError:
                    form_errors[item.id] = "Invalid quantity (must be a whole number)."
                except Exception as e: # Catch unexpected errors during item processing
                    form_errors[item.id] = f"An unexpected error occurred processing this item: {str(e)}"


            if form_errors:
                transaction.savepoint_rollback(sid) # Rollback changes if any validation errors
                messages.error(request, "Please correct the errors in the form.")
                context = {
                    'request_to_complete': material_request,
                    'title': f'Confirm Completion for Request ID: {material_request.id}',
                    'form_errors': form_errors, # Pass errors to template
                    # Pass back POST data if needed by template, but template already tries to use request.POST
                }
                return render(request, 'inventory/request/request_complete_confirm.html', context)

            # If all validations passed and no form_errors
            all_items_processed_successfully = True
            for data in items_data:
                item_instance = data['item_instance']
                material_instance = data['material_instance']
                fulfilled_qty = data['fulfilled_quantity']

                try:
                    # Deduct stock
                    # Refresh material_instance from DB to ensure quantity_on_hand is current before update
                    material_to_update = Material.objects.select_for_update().get(pk=material_instance.pk)
                    if fulfilled_qty > material_to_update.quantity_on_hand:
                        # This check is technically redundant if initial validation was thorough and no concurrent updates.
                        # However, it's a safeguard.
                        form_errors[item_instance.id] = f"Stock changed for {material_to_update.name}. Available: {material_to_update.quantity_on_hand}. Cannot fulfill {fulfilled_qty}."
                        all_items_processed_successfully = False
                        break # Exit loop, will trigger rollback

                    material_to_update.quantity_on_hand = F('quantity_on_hand') - fulfilled_qty
                    material_to_update.save(update_fields=['quantity_on_hand'])

                    # Update fulfilled quantity on the request item
                    item_instance.fulfilled_quantity = fulfilled_qty
                    item_instance.save(update_fields=['fulfilled_quantity'])

                except Exception as e_item_update: # Catch errors during DB update for a specific item
                    # Log e_item_update
                    form_errors[item_instance.id] = f"Error updating stock for {material_instance.name}: {str(e_item_update)}"
                    all_items_processed_successfully = False
                    break # Exit loop, will trigger rollback

            if not all_items_processed_successfully:
                transaction.savepoint_rollback(sid) # Rollback changes
                messages.error(request, "Could not complete the request due to errors updating stock or item fulfillment.")
                context = {
                    'request_to_complete': material_request,
                    'title': f'Confirm Completion for Request ID: {material_request.id}',
                    'form_errors': form_errors,
                }
                return render(request, 'inventory/request/request_complete_confirm.html', context)

            # If all items processed successfully
            material_request.status = MaterialRequest.Status.COMPLETED
            material_request.updated_at = timezone.now()
            material_request.save(update_fields=['status', 'updated_at'])

            transaction.savepoint_commit(sid) # Commit the transaction
            messages.success(request, f"Request ID {material_request.id} has been processed and stock updated based on fulfilled quantities.")
            return redirect('inventory:completed_request_list')

        # except Exception as e: # General exception for the whole POST processing, outside transaction usually
        #     # This might catch issues if the transaction itself fails to start/commit/rollback
        #     # Log error e
        #     messages.error(request, f"An unexpected error occurred: {str(e)}")
        #     # Fall through to render the form again, or redirect if appropriate
        #     # The transaction should have rolled back on unhandled exceptions within its block.

    # GET request or if POST processing falls through without redirecting (e.g. after general error)
    items_for_template = []
    if material_request: # Ensure material_request is not None
        for item in material_request.request_items.all():
            available_stock = item.material.quantity_on_hand
            default_qty = min(item.quantity_requested, available_stock)
            items_for_template.append({
                'instance': item, # The MaterialRequestItem instance
                'material_name': item.material.name,
                'material_sku': item.material.sku,
                'quantity_requested': item.quantity_requested,
                'available_stock': available_stock,
                'default_fulfill_qty': default_qty,
                'item_id': item.id # For constructing field names and error keys
            })

    context = {
        'request_to_complete': material_request, # This is the MaterialRequest instance
        'items_for_template': items_for_template, # This is the processed list for the template
        'title': f'Confirm Completion for Request ID: {material_request.id if material_request else "N/A"}',
        'form_errors': {} # Initialize form_errors for GET requests
    }
    return render(request, 'inventory/request/request_complete_confirm.html', context)

@login_required
@user_passes_test(is_warehouse_staff, login_url='inventory:login')
def completed_request_list_view(request):
    completed_requests = MaterialRequest.objects.filter(status=MaterialRequest.Status.COMPLETED) \
                                              .select_related('requested_by') \
                                              .prefetch_related('request_items__material') \
                                              .order_by('-updated_at')
    context = {
        'requests': completed_requests,
        'title': 'Completed Material Requests'
    }
    return render(request, 'inventory/request/completed_request_list.html', context)

# Inventory Management (Warehouse Staff)
@login_required
@user_passes_test(is_warehouse_staff, login_url='inventory:login')
def material_create_view(request):
    if request.method == 'POST':
        form = MaterialForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Save the material instance first.
                    # quantity_on_hand and current_average_cost_per_unit will be default (0)
                    # as they are not part of MaterialForm's direct fields anymore.
                    material = form.save()

                    # Now create the initial stock transaction if initial quantity > 0
                    initial_quantity = form.cleaned_data.get('initial_quantity')
                    if initial_quantity > 0: # Check if initial_quantity is not None and > 0
                        initial_total_cost = form.cleaned_data.get('initial_total_cost')
                        initial_cost_per_unit = form.cleaned_data.get('initial_cost_per_unit')

                        StockTransaction.objects.create(
                            material=material,
                            transaction_type=StockTransaction.TransactionType.INITIAL_STOCK,
                            quantity_change=initial_quantity,
                            cost_per_unit_at_transaction=initial_cost_per_unit,
                            total_cost_of_transaction=initial_total_cost,
                            created_by=request.user,
                            notes="Initial stock added upon material creation."
                        )
                        # The StockTransaction's save() method will update material's quantity and avg cost.

                    messages.success(request, f"Material '{material.name}' added successfully with initial stock recorded.")
                    return redirect('inventory:material_list')
            except ValueError as ve: # Catch errors from StockTransaction save
                messages.error(request, f"Error processing initial stock: {str(ve)}")
            except Exception as e: # Catch other unexpected errors
                messages.error(request, f"An unexpected error occurred: {e}")
                # Log error e (import logging; logging.error(str(e)))
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = MaterialForm()

    context = {
        'form': form,
        'title': 'Add New Material to Inventory'
        # 'material_instance' is not passed for create view, so template condition will work
    }
    return render(request, 'inventory/material/material_form.html', context)

@login_required # Ensure user is logged in, specifics of role can be debated for this utility view
def get_material_stock_view(request, material_id):
    if not request.user.is_authenticated: # Redundant if @login_required is used, but good for clarity
        return JsonResponse({'error': 'Authentication required.'}, status=401)

    try:
        material = Material.objects.get(pk=material_id)
        return JsonResponse({'quantity_on_hand': material.quantity_on_hand})
    except Material.DoesNotExist:
        return JsonResponse({'error': 'Material not found.'}, status=404)
    except Exception as e: # Catch any other unexpected errors
        # Log the error e
        return JsonResponse({'error': 'An unexpected error occurred.'}, status=500)


# AJAX view for material search with django-select2
class MaterialAjaxSearch(AutoResponseView):
    def get_field(self): # Override to bypass field loading if not needed
        return None

    def get_queryset(self):
        # Explicitly check for None or empty string (after stripping whitespace)
        if self.term is None or self.term.strip() == "":
            # No search term, provide initial default options
            return Material.objects.all().order_by('name')[:15] # Initial list limit
        else:
            # User is searching
            qs = Material.objects.filter(
                Q(name__icontains=self.term) | Q(sku__icontains=self.term)
            ).order_by('name')
            return qs[:50] # Limit search results

    def get_result_label(self, item): # Keep this
        return f"{item.name} (SKU: {item.sku})"

    # Optional: Customize result value (usually item.pk)
    # def get_result_value(self, item):
    #     return str(item.pk) # Default is usually fine


@login_required
@user_passes_test(is_warehouse_staff, login_url='inventory:login')
def material_restock_view(request):
    if request.method == 'POST':
        form = StockTransactionForm(request.POST, user=request.user) # Pass user to form if needed for __init__
        if form.is_valid():
            try:
                with transaction.atomic():
                    stock_tx = form.save(commit=False)
                    stock_tx.created_by = request.user # form __init__ user is for other potential uses
                    stock_tx.transaction_type = StockTransaction.TransactionType.RESTOCK

                    # The model's save() method handles cost calculation and material updates.
                    stock_tx.save()

                    messages.success(request, f"Successfully restocked {stock_tx.quantity_change} unit(s) of {stock_tx.material.name}.")
                    return redirect('inventory:material_list') # Or to material detail page
            except ValueError as ve: # Catch validation errors from model's save method
                messages.error(request, str(ve))
            except Exception as e: # Catch other unexpected errors
                messages.error(request, f"An unexpected error occurred during restock: {e}")
                # Log error e (import logging; logging.error(str(e)))
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = StockTransactionForm(user=request.user) # Pass user if form __init__ uses it

    context = {
        'form': form,
        'title': 'Restock Material'
    }
    return render(request, 'inventory/material/restock_form.html', context)

@login_required
@user_passes_test(is_warehouse_staff, login_url='inventory:login')
def material_update_view(request, material_id):
    material_instance = get_object_or_404(Material, id=material_id)

    if request.method == 'POST':
        form = MaterialForm(request.POST, request.FILES, instance=material_instance)
        if form.is_valid():
            form.save()
            messages.success(request, f"Material '{material_instance.name}' updated successfully.")
            return redirect('inventory:material_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = MaterialForm(instance=material_instance)

    context = {
        'form': form,
        'title': f'Update Material: {material_instance.name}',
        'material_instance': material_instance
    }
    return render(request, 'inventory/material/material_form.html', context)
