"""Commissions module views."""

from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.utils.translation import gettext_lazy as _

from apps.accounts.decorators import login_required
from apps.core.htmx import htmx_view
from apps.modules_runtime.navigation import with_module_nav

from .models import (
    CommissionsSettings,
    CommissionRule,
    CommissionTransaction,
    CommissionPayout,
    CommissionAdjustment,
)
from .forms import (
    CommissionRuleForm,
    CommissionAdjustmentForm,
    CommissionsSettingsForm,
)


def _hub(request):
    return request.session.get('hub_id')


def _employee(request):
    from apps.accounts.models import LocalUser
    uid = request.session.get('local_user_id')
    if uid:
        try:
            return LocalUser.objects.get(pk=uid)
        except LocalUser.DoesNotExist:
            pass
    return None


# =============================================================================
# Dashboard
# =============================================================================

@login_required
@with_module_nav('commissions', 'dashboard')
@htmx_view('commissions/pages/index.html', 'commissions/partials/dashboard.html')
def index(request):
    return _dashboard_context(request)


@login_required
@with_module_nav('commissions', 'dashboard')
@htmx_view('commissions/pages/index.html', 'commissions/partials/dashboard.html')
def dashboard(request):
    return _dashboard_context(request)


def _dashboard_context(request):
    hub = _hub(request)
    today = date.today()
    month_start = today.replace(day=1)

    trans_qs = CommissionTransaction.objects.filter(
        hub_id=hub, is_deleted=False,
        transaction_date__gte=month_start, transaction_date__lte=today,
    )
    trans_stats = trans_qs.aggregate(
        total_commission=Sum('commission_amount'),
        total_net=Sum('net_commission'),
        total_tax=Sum('tax_amount'),
        count=Count('id'),
    )

    pending_count = CommissionTransaction.objects.filter(
        hub_id=hub, is_deleted=False, status='pending'
    ).count()

    stats = {
        'total_commission': trans_stats['total_commission'] or Decimal('0'),
        'total_net': trans_stats['total_net'] or Decimal('0'),
        'total_tax': trans_stats['total_tax'] or Decimal('0'),
        'transaction_count': trans_stats['count'] or 0,
        'pending_transactions': pending_count,
    }

    # Top earners
    top_earners = (
        trans_qs.filter(status__in=['approved', 'paid'])
        .values('staff_id', 'staff_name')
        .annotate(total=Sum('net_commission'))
        .order_by('-total')[:5]
    )

    recent = CommissionTransaction.objects.filter(
        hub_id=hub, is_deleted=False
    ).select_related('rule').order_by('-transaction_date', '-created_at')[:10]

    pending_payouts = CommissionPayout.objects.filter(
        hub_id=hub, is_deleted=False, status='pending'
    ).order_by('-created_at')[:5]

    return {
        'stats': stats,
        'top_earners': top_earners,
        'recent_transactions': recent,
        'pending_payouts': pending_payouts,
    }


# =============================================================================
# Transactions
# =============================================================================

@login_required
@with_module_nav('commissions', 'transactions')
@htmx_view('commissions/pages/transactions.html', 'commissions/partials/transactions.html')
def transaction_list(request):
    hub = _hub(request)
    status_filter = request.GET.get('status', '')
    search = request.GET.get('q', '')

    transactions = CommissionTransaction.objects.filter(
        hub_id=hub, is_deleted=False
    ).select_related('rule', 'staff')

    if status_filter:
        transactions = transactions.filter(status=status_filter)

    if search:
        transactions = transactions.filter(
            Q(staff_name__icontains=search) |
            Q(sale_reference__icontains=search) |
            Q(description__icontains=search)
        )

    return {
        'transactions': transactions,
        'status_filter': status_filter,
        'search': search,
    }


@login_required
@with_module_nav('commissions', 'transactions')
@htmx_view('commissions/pages/transaction_detail.html', 'commissions/partials/transaction_detail.html')
def transaction_detail(request, pk):
    hub = _hub(request)
    trans = CommissionTransaction.objects.select_related(
        'rule', 'staff', 'payout', 'approved_by'
    ).get(pk=pk, hub_id=hub, is_deleted=False)

    return {'transaction': trans}


@login_required
@require_POST
def transaction_approve(request, pk):
    hub = _hub(request)
    trans = CommissionTransaction.objects.get(pk=pk, hub_id=hub, is_deleted=False)

    if trans.status != 'pending':
        return JsonResponse(
            {'success': False, 'error': f'Transaction is {trans.status}, cannot approve'},
            status=400
        )

    employee = _employee(request)
    trans.status = 'approved'
    trans.approved_by = employee
    trans.approved_at = timezone.now()
    trans.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
    return JsonResponse({'success': True})


@login_required
@require_POST
def transaction_reject(request, pk):
    hub = _hub(request)
    trans = CommissionTransaction.objects.get(pk=pk, hub_id=hub, is_deleted=False)

    if trans.status != 'pending':
        return JsonResponse(
            {'success': False, 'error': f'Transaction is {trans.status}, cannot reject'},
            status=400
        )

    reason = request.POST.get('reason', '')
    trans.status = 'cancelled'
    if reason:
        trans.notes = f"{trans.notes}\nRejection: {reason}".strip()
    trans.save(update_fields=['status', 'notes', 'updated_at'])
    return JsonResponse({'success': True})


# =============================================================================
# Payouts
# =============================================================================

@login_required
@with_module_nav('commissions', 'payouts')
@htmx_view('commissions/pages/payouts.html', 'commissions/partials/payouts.html')
def payout_list(request):
    hub = _hub(request)
    status_filter = request.GET.get('status', '')

    payouts = CommissionPayout.objects.filter(
        hub_id=hub, is_deleted=False
    ).select_related('staff')

    if status_filter:
        payouts = payouts.filter(status=status_filter)

    return {
        'payouts': payouts,
        'status_filter': status_filter,
    }


@login_required
def payout_create(request):
    hub = _hub(request)

    if request.method == 'POST':
        staff_pk = request.POST.get('staff_id')
        period_start = request.POST.get('period_start')
        period_end = request.POST.get('period_end')
        notes = request.POST.get('notes', '')

        try:
            from staff.models import StaffMember
            member = StaffMember.objects.get(pk=staff_pk, hub_id=hub, is_deleted=False)

            p_start = date.fromisoformat(period_start)
            p_end = date.fromisoformat(period_end)

            with transaction.atomic():
                # Find approved transactions not yet in a payout
                transactions = CommissionTransaction.objects.filter(
                    hub_id=hub, is_deleted=False,
                    staff=member, status='approved', payout__isnull=True,
                    transaction_date__gte=p_start, transaction_date__lte=p_end,
                )

                if not transactions.exists():
                    return JsonResponse(
                        {'success': False, 'error': 'No approved transactions for this period'},
                        status=400
                    )

                agg = transactions.aggregate(
                    total_gross=Sum('commission_amount'),
                    total_tax=Sum('tax_amount'),
                    count=Count('id'),
                )

                settings = CommissionsSettings.get_settings(hub)
                gross = agg['total_gross'] or Decimal('0')

                if settings.minimum_payout_amount > 0 and gross < settings.minimum_payout_amount:
                    return JsonResponse(
                        {'success': False, 'error': f'Amount {gross} below minimum {settings.minimum_payout_amount}'},
                        status=400
                    )

                payout = CommissionPayout.objects.create(
                    hub_id=hub,
                    staff=member,
                    staff_name=member.full_name,
                    period_start=p_start,
                    period_end=p_end,
                    gross_amount=gross,
                    tax_amount=agg['total_tax'] or Decimal('0'),
                    transaction_count=agg['count'] or 0,
                    notes=notes,
                    status='pending',
                )
                transactions.update(payout=payout)

            return JsonResponse({'success': True, 'id': str(payout.pk)})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    # GET: show form with staff list
    try:
        from staff.models import StaffMember
        staff_list = StaffMember.objects.filter(
            hub_id=hub, is_deleted=False, status='active'
        )
    except Exception:
        staff_list = []

    return JsonResponse({'staff_list': [
        {'id': str(s.pk), 'name': s.full_name} for s in staff_list
    ]})


@login_required
@with_module_nav('commissions', 'payouts')
@htmx_view('commissions/pages/payout_detail.html', 'commissions/partials/payout_detail.html')
def payout_detail(request, pk):
    hub = _hub(request)
    payout = CommissionPayout.objects.select_related('staff', 'approved_by', 'paid_by').get(
        pk=pk, hub_id=hub, is_deleted=False
    )
    transactions = payout.transactions.filter(is_deleted=False)
    adjustments = payout.adjustments_list.filter(is_deleted=False)

    return {
        'payout': payout,
        'transactions': transactions,
        'adjustments': adjustments,
    }


@login_required
@require_POST
def payout_approve(request, pk):
    hub = _hub(request)
    payout = CommissionPayout.objects.get(pk=pk, hub_id=hub, is_deleted=False)

    if payout.status not in ['draft', 'pending']:
        return JsonResponse(
            {'success': False, 'error': f'Payout is {payout.status}, cannot approve'},
            status=400
        )

    employee = _employee(request)
    payout.status = 'approved'
    payout.approved_by = employee
    payout.approved_at = timezone.now()
    payout.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
    return JsonResponse({'success': True})


@login_required
@require_POST
def payout_process(request, pk):
    hub = _hub(request)
    payout = CommissionPayout.objects.get(pk=pk, hub_id=hub, is_deleted=False)

    if payout.status not in ['pending', 'approved']:
        return JsonResponse(
            {'success': False, 'error': f'Payout is {payout.status}, cannot process'},
            status=400
        )

    employee = _employee(request)
    payment_method = request.POST.get('payment_method', '')
    payment_reference = request.POST.get('payment_reference', '')

    payout.status = 'completed'
    payout.payment_method = payment_method
    payout.payment_reference = payment_reference
    payout.paid_by = employee
    payout.paid_at = timezone.now()
    payout.save(update_fields=[
        'status', 'payment_method', 'payment_reference',
        'paid_by', 'paid_at', 'updated_at'
    ])
    payout.transactions.filter(is_deleted=False).update(status='paid')
    return JsonResponse({'success': True})


@login_required
@require_POST
def payout_cancel(request, pk):
    hub = _hub(request)
    payout = CommissionPayout.objects.get(pk=pk, hub_id=hub, is_deleted=False)

    if payout.status == 'completed':
        return JsonResponse(
            {'success': False, 'error': 'Cannot cancel a completed payout'},
            status=400
        )

    reason = request.POST.get('reason', '')
    with transaction.atomic():
        payout.transactions.filter(is_deleted=False).update(payout=None, status='approved')
        payout.status = 'cancelled'
        if reason:
            payout.notes = f"{payout.notes}\nCancellation: {reason}".strip()
        payout.save(update_fields=['status', 'notes', 'updated_at'])

    return JsonResponse({'success': True})


# =============================================================================
# Rules
# =============================================================================

@login_required
@with_module_nav('commissions', 'rules')
@htmx_view('commissions/pages/rules.html', 'commissions/partials/rules.html')
def rule_list(request):
    hub = _hub(request)
    rules = CommissionRule.objects.filter(
        hub_id=hub, is_deleted=False
    ).select_related('staff', 'service', 'category', 'product').order_by('-priority', 'name')

    return {'rules': rules}


@login_required
def rule_add(request):
    hub = _hub(request)

    if request.method == 'POST':
        form = CommissionRuleForm(request.POST)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.hub_id = hub
            rule.save()
            return JsonResponse({'success': True, 'id': str(rule.pk)})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    form = CommissionRuleForm()
    return JsonResponse({'form_html': 'TODO'})


@login_required
@with_module_nav('commissions', 'rules')
@htmx_view('commissions/pages/rule_detail.html', 'commissions/partials/rule_detail.html')
def rule_detail(request, pk):
    hub = _hub(request)
    rule = CommissionRule.objects.select_related(
        'staff', 'service', 'category', 'product'
    ).get(pk=pk, hub_id=hub, is_deleted=False)

    transaction_count = rule.transactions.filter(is_deleted=False).count()
    return {'rule': rule, 'transaction_count': transaction_count}


@login_required
def rule_edit(request, pk):
    hub = _hub(request)
    rule = CommissionRule.objects.get(pk=pk, hub_id=hub, is_deleted=False)

    if request.method == 'POST':
        form = CommissionRuleForm(request.POST, instance=rule)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    form = CommissionRuleForm(instance=rule)
    return JsonResponse({'form_html': 'TODO'})


@login_required
@require_POST
def rule_delete(request, pk):
    hub = _hub(request)
    rule = CommissionRule.objects.get(pk=pk, hub_id=hub, is_deleted=False)

    # Check if used in transactions
    if rule.transactions.filter(is_deleted=False).exists():
        return JsonResponse(
            {'success': False, 'error': 'Cannot delete rule with existing transactions'},
            status=400
        )

    rule.is_deleted = True
    rule.deleted_at = timezone.now()
    rule.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
    return JsonResponse({'success': True})


@login_required
@require_POST
def rule_toggle(request, pk):
    hub = _hub(request)
    rule = CommissionRule.objects.get(pk=pk, hub_id=hub, is_deleted=False)
    rule.is_active = not rule.is_active
    rule.save(update_fields=['is_active', 'updated_at'])
    return JsonResponse({'success': True, 'is_active': rule.is_active})


# =============================================================================
# Adjustments
# =============================================================================

@login_required
@with_module_nav('commissions', 'adjustments')
@htmx_view('commissions/pages/adjustments.html', 'commissions/partials/adjustments.html')
def adjustment_list(request):
    hub = _hub(request)
    type_filter = request.GET.get('type', '')

    adjustments = CommissionAdjustment.objects.filter(
        hub_id=hub, is_deleted=False
    ).select_related('staff', 'created_by')

    if type_filter:
        adjustments = adjustments.filter(adjustment_type=type_filter)

    return {
        'adjustments': adjustments,
        'type_filter': type_filter,
    }


@login_required
def adjustment_add(request):
    hub = _hub(request)

    if request.method == 'POST':
        staff_pk = request.POST.get('staff_id')
        form = CommissionAdjustmentForm(request.POST)
        if form.is_valid():
            adj = form.save(commit=False)
            adj.hub_id = hub
            adj.created_by = _employee(request)

            try:
                from staff.models import StaffMember
                member = StaffMember.objects.get(pk=staff_pk, hub_id=hub, is_deleted=False)
                adj.staff = member
                adj.staff_name = member.full_name
            except Exception:
                adj.staff_name = request.POST.get('staff_name', 'Unknown')

            adj.save()
            return JsonResponse({'success': True, 'id': str(adj.pk)})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    form = CommissionAdjustmentForm()
    return JsonResponse({'form_html': 'TODO'})


@login_required
@with_module_nav('commissions', 'adjustments')
@htmx_view('commissions/pages/adjustment_detail.html', 'commissions/partials/adjustment_detail.html')
def adjustment_detail(request, pk):
    hub = _hub(request)
    adj = CommissionAdjustment.objects.select_related(
        'staff', 'payout', 'created_by'
    ).get(pk=pk, hub_id=hub, is_deleted=False)

    return {'adjustment': adj}


@login_required
@require_POST
def adjustment_delete(request, pk):
    hub = _hub(request)
    adj = CommissionAdjustment.objects.get(pk=pk, hub_id=hub, is_deleted=False)

    if adj.payout:
        return JsonResponse(
            {'success': False, 'error': 'Cannot delete adjustment linked to a payout'},
            status=400
        )

    adj.is_deleted = True
    adj.deleted_at = timezone.now()
    adj.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
    return JsonResponse({'success': True})


# =============================================================================
# Settings
# =============================================================================

@login_required
@with_module_nav('commissions', 'settings')
@htmx_view('commissions/pages/settings.html', 'commissions/partials/settings.html')
def settings(request):
    hub = _hub(request)
    comm_settings = CommissionsSettings.get_settings(hub)
    form = CommissionsSettingsForm(instance=comm_settings)
    return {'settings': comm_settings, 'form': form}


@login_required
@require_POST
def settings_save(request):
    hub = _hub(request)
    comm_settings = CommissionsSettings.get_settings(hub)
    form = CommissionsSettingsForm(request.POST, instance=comm_settings)
    if form.is_valid():
        form.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required
@require_POST
def settings_toggle(request):
    hub = _hub(request)
    comm_settings = CommissionsSettings.get_settings(hub)
    field = request.POST.get('field', '')

    toggleable = [
        'apply_tax_withholding', 'show_commission_on_receipt', 'show_pending_commission',
    ]

    if field not in toggleable:
        return JsonResponse({'success': False, 'error': _('Invalid field')}, status=400)

    setattr(comm_settings, field, not getattr(comm_settings, field))
    comm_settings.save(update_fields=[field, 'updated_at'])
    return JsonResponse({'success': True, 'value': getattr(comm_settings, field)})


@login_required
@require_POST
def settings_input(request):
    hub = _hub(request)
    comm_settings = CommissionsSettings.get_settings(hub)
    field = request.POST.get('field', '')
    value = request.POST.get('value', '')

    input_fields = {
        'default_commission_rate': lambda v: Decimal(v),
        'payout_day': int,
        'minimum_payout_amount': lambda v: Decimal(v),
        'tax_withholding_rate': lambda v: Decimal(v),
    }

    if field not in input_fields:
        return JsonResponse({'success': False, 'error': _('Invalid field')}, status=400)

    try:
        parsed = input_fields[field](value)
        setattr(comm_settings, field, parsed)
        comm_settings.save(update_fields=[field, 'updated_at'])
        return JsonResponse({'success': True})
    except (ValueError, TypeError, InvalidOperation) as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def settings_reset(request):
    hub = _hub(request)
    comm_settings = CommissionsSettings.get_settings(hub)
    defaults = CommissionsSettings()
    for f in CommissionsSettingsForm.Meta.fields:
        setattr(comm_settings, f, getattr(defaults, f))
    comm_settings.save()
    return JsonResponse({'success': True})


# =============================================================================
# API Endpoints
# =============================================================================

@login_required
@require_POST
def api_calculate(request):
    """Calculate commission for given amount and rule."""
    hub = _hub(request)
    try:
        amount = Decimal(request.POST.get('amount', '0'))
        rule_pk = request.POST.get('rule_id')

        if not rule_pk:
            return JsonResponse({'error': 'Rule ID required'}, status=400)

        rule = CommissionRule.objects.get(pk=rule_pk, hub_id=hub, is_deleted=False)
        commission = rule.calculate_commission(amount)

        comm_settings = CommissionsSettings.get_settings(hub)
        net, tax = comm_settings.calculate_tax(commission)

        return JsonResponse({
            'amount': str(amount),
            'commission_amount': str(commission),
            'tax_withheld': str(tax),
            'net_amount': str(net),
        })
    except CommissionRule.DoesNotExist:
        return JsonResponse({'error': 'Rule not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_GET
def api_staff_summary(request, staff_pk):
    """Get commission summary for a staff member."""
    hub = _hub(request)
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    try:
        qs = CommissionTransaction.objects.filter(
            hub_id=hub, is_deleted=False, staff_id=staff_pk
        )
        if start_date:
            qs = qs.filter(transaction_date__gte=date.fromisoformat(start_date))
        if end_date:
            qs = qs.filter(transaction_date__lte=date.fromisoformat(end_date))

        totals = qs.aggregate(
            total_sales=Sum('sale_amount'),
            total_commission=Sum('commission_amount'),
            total_net=Sum('net_commission'),
            total_tax=Sum('tax_amount'),
            count=Count('id'),
        )

        pending = qs.filter(status='pending').aggregate(
            amount=Sum('net_commission'), count=Count('id')
        )
        paid = qs.filter(status='paid').aggregate(
            amount=Sum('net_commission'), count=Count('id')
        )

        summary = {
            'total_sales': str(totals['total_sales'] or Decimal('0')),
            'total_commission': str(totals['total_commission'] or Decimal('0')),
            'total_net': str(totals['total_net'] or Decimal('0')),
            'total_tax': str(totals['total_tax'] or Decimal('0')),
            'transaction_count': totals['count'] or 0,
            'pending_amount': str(pending['amount'] or Decimal('0')),
            'pending_count': pending['count'] or 0,
            'paid_amount': str(paid['amount'] or Decimal('0')),
            'paid_count': paid['count'] or 0,
        }

        return JsonResponse(summary)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
