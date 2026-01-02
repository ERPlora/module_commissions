"""
Commission Views - HTTP handlers for commission module.
"""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST

from apps.modules_runtime.decorators import module_view
from .models import (
    CommissionsConfig,
    CommissionRule,
    CommissionTransaction,
    CommissionPayout,
    CommissionAdjustment,
)
from .services import CommissionService


# ==================== Dashboard ====================

@module_view('commissions', 'dashboard')
def dashboard(request: HttpRequest) -> HttpResponse:
    """Commission dashboard with stats and quick actions."""
    # Get date range (default: current month)
    today = date.today()
    start_date = today.replace(day=1)
    end_date = today

    stats = CommissionService.get_dashboard_stats(start_date, end_date)
    config = CommissionService.get_config()

    # Recent transactions
    recent_transactions = CommissionService.get_transactions()[:10]

    # Pending items
    pending_transactions = CommissionService.get_transactions(status='pending')[:5]
    pending_payouts = CommissionService.get_payouts(status='pending')[:5]

    context = {
        'stats': stats,
        'config': config,
        'recent_transactions': recent_transactions,
        'pending_transactions': pending_transactions,
        'pending_payouts': pending_payouts,
        'page_title': 'Commissions',
    }
    return render(request, 'commissions/dashboard.html', context)


# ==================== Transactions ====================

@module_view('commissions', 'transactions')
def transaction_list(request: HttpRequest) -> HttpResponse:
    """List all commission transactions."""
    status_filter = request.GET.get('status', '')
    search = request.GET.get('q', '')

    transactions = CommissionService.get_transactions(
        status=status_filter if status_filter else None,
    )

    context = {
        'transactions': transactions,
        'status_filter': status_filter,
        'search': search,
        'page_title': 'Transactions',
    }
    return render(request, 'commissions/transaction_list.html', context)


@module_view('commissions', 'transactions')
def transaction_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """View transaction details."""
    transaction = get_object_or_404(CommissionTransaction, pk=pk)

    context = {
        'transaction': transaction,
        'page_title': f'Transaction #{pk}',
        'page_type': 'detail',
        'back_url': '/modules/commissions/transactions/',
    }
    return render(request, 'commissions/transaction_detail.html', context)


@require_POST
def transaction_approve(request: HttpRequest, pk: int) -> HttpResponse:
    """Approve a pending transaction."""
    transaction = get_object_or_404(CommissionTransaction, pk=pk)
    success, error = CommissionService.approve_transaction(
        transaction,
        approved_by_id=request.user.id if request.user.is_authenticated else None,
    )

    if request.headers.get('HX-Request'):
        if success:
            return HttpResponse('<ion-badge color="success">Approved</ion-badge>')
        return HttpResponse(f'<span class="text-danger">{error}</span>')

    if success:
        messages.success(request, 'Transaction approved.')
    else:
        messages.error(request, error)

    return redirect('commissions:transaction_list')


@require_POST
def transaction_reject(request: HttpRequest, pk: int) -> HttpResponse:
    """Reject a pending transaction."""
    transaction = get_object_or_404(CommissionTransaction, pk=pk)
    reason = request.POST.get('reason', '')
    success, error = CommissionService.reject_transaction(transaction, reason)

    if request.headers.get('HX-Request'):
        if success:
            return HttpResponse('<ion-badge color="danger">Rejected</ion-badge>')
        return HttpResponse(f'<span class="text-danger">{error}</span>')

    if success:
        messages.success(request, 'Transaction rejected.')
    else:
        messages.error(request, error)

    return redirect('commissions:transaction_list')


# ==================== Payouts ====================

@module_view('commissions', 'payouts')
def payout_list(request: HttpRequest) -> HttpResponse:
    """List all payouts."""
    status_filter = request.GET.get('status', '')

    payouts = CommissionService.get_payouts(
        status=status_filter if status_filter else None,
    )

    context = {
        'payouts': payouts,
        'status_filter': status_filter,
        'page_title': 'Payouts',
    }
    return render(request, 'commissions/payout_list.html', context)


@module_view('commissions', 'payouts')
def payout_create(request: HttpRequest) -> HttpResponse:
    """Create a new payout."""
    if request.method == 'POST':
        staff_id = request.POST.get('staff_id')
        staff_name = request.POST.get('staff_name', '')
        period_start = request.POST.get('period_start')
        period_end = request.POST.get('period_end')
        notes = request.POST.get('notes', '')

        try:
            payout, error = CommissionService.create_payout(
                staff_id=int(staff_id),
                staff_name=staff_name,
                period_start=date.fromisoformat(period_start),
                period_end=date.fromisoformat(period_end),
                notes=notes,
            )

            if payout:
                messages.success(request, f'Payout created: ${payout.net_amount}')
                return redirect('commissions:payout_detail', pk=payout.id)
            else:
                messages.error(request, error)
        except Exception as e:
            messages.error(request, str(e))

    # Get staff with unpaid commissions
    staff_list = []
    try:
        from staff.models import StaffMember
        staff_list = StaffMember.objects.filter(status='active')
    except Exception:
        pass

    context = {
        'staff_list': staff_list,
        'page_title': 'Create Payout',
        'page_type': 'form',
        'back_url': '/modules/commissions/payouts/',
    }
    return render(request, 'commissions/payout_form.html', context)


@module_view('commissions', 'payouts')
def payout_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """View payout details."""
    payout = get_object_or_404(CommissionPayout, pk=pk)

    context = {
        'payout': payout,
        'transactions': payout.transactions.all(),
        'adjustments': payout.adjustments_list.all(),
        'page_title': f'Payout #{pk}',
        'page_type': 'detail',
        'back_url': '/modules/commissions/payouts/',
    }
    return render(request, 'commissions/payout_detail.html', context)


@require_POST
def payout_approve(request: HttpRequest, pk: int) -> HttpResponse:
    """Approve a pending payout."""
    payout = get_object_or_404(CommissionPayout, pk=pk)
    success, error = CommissionService.approve_payout(
        payout,
        approved_by_id=request.user.id if request.user.is_authenticated else None,
    )

    if success:
        messages.success(request, 'Payout approved.')
    else:
        messages.error(request, error)

    return redirect('commissions:payout_detail', pk=pk)


@require_POST
def payout_process(request: HttpRequest, pk: int) -> HttpResponse:
    """Process/pay a payout."""
    payout = get_object_or_404(CommissionPayout, pk=pk)
    payment_method = request.POST.get('payment_method', '')
    payment_reference = request.POST.get('payment_reference', '')

    success, error = CommissionService.process_payout(
        payout, payment_method, payment_reference,
        paid_by_id=request.user.id if request.user.is_authenticated else None,
    )

    if success:
        messages.success(request, 'Payout processed successfully.')
    else:
        messages.error(request, error)

    return redirect('commissions:payout_detail', pk=pk)


@require_POST
def payout_cancel(request: HttpRequest, pk: int) -> HttpResponse:
    """Cancel a payout."""
    payout = get_object_or_404(CommissionPayout, pk=pk)
    reason = request.POST.get('reason', '')

    success, error = CommissionService.cancel_payout(payout, reason)

    if success:
        messages.success(request, 'Payout cancelled.')
    else:
        messages.error(request, error)

    return redirect('commissions:payout_list')


# ==================== Rules ====================

@module_view('commissions', 'rules')
def rule_list(request: HttpRequest) -> HttpResponse:
    """List all commission rules."""
    rules = CommissionService.get_rules()

    context = {
        'rules': rules,
        'page_title': 'Commission Rules',
    }
    return render(request, 'commissions/rule_list.html', context)


@module_view('commissions', 'rules')
def rule_create(request: HttpRequest) -> HttpResponse:
    """Create a new commission rule."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        rule_type = request.POST.get('rule_type', 'percentage')
        rate = request.POST.get('rate', '0')
        description = request.POST.get('description', '')
        priority = request.POST.get('priority', '0')
        is_active = request.POST.get('is_active') == 'on'

        try:
            rule, error = CommissionService.create_rule(
                name=name,
                rule_type=rule_type,
                rate=Decimal(rate),
                description=description,
                priority=int(priority),
                is_active=is_active,
            )

            if rule:
                messages.success(request, f'Rule "{name}" created.')
                return redirect('commissions:rule_list')
            else:
                messages.error(request, error)
        except (InvalidOperation, ValueError) as e:
            messages.error(request, f'Invalid input: {e}')

    context = {
        'page_title': 'New Rule',
        'page_type': 'form',
        'back_url': '/modules/commissions/rules/',
    }
    return render(request, 'commissions/rule_form.html', context)


@module_view('commissions', 'rules')
def rule_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """View rule details."""
    rule = get_object_or_404(CommissionRule, pk=pk)

    context = {
        'rule': rule,
        'page_title': rule.name,
        'page_type': 'detail',
        'back_url': '/modules/commissions/rules/',
    }
    return render(request, 'commissions/rule_detail.html', context)


@module_view('commissions', 'rules')
def rule_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """Edit a commission rule."""
    rule = get_object_or_404(CommissionRule, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        rule_type = request.POST.get('rule_type', 'percentage')
        rate = request.POST.get('rate', '0')
        description = request.POST.get('description', '')
        priority = request.POST.get('priority', '0')
        is_active = request.POST.get('is_active') == 'on'

        try:
            success, error = CommissionService.update_rule(
                rule,
                name=name,
                rule_type=rule_type,
                rate=Decimal(rate),
                description=description,
                priority=int(priority),
                is_active=is_active,
            )

            if success:
                messages.success(request, f'Rule "{name}" updated.')
                return redirect('commissions:rule_list')
            else:
                messages.error(request, error)
        except (InvalidOperation, ValueError) as e:
            messages.error(request, f'Invalid input: {e}')

    context = {
        'rule': rule,
        'page_title': f'Edit {rule.name}',
        'page_type': 'form',
        'back_url': '/modules/commissions/rules/',
    }
    return render(request, 'commissions/rule_form.html', context)


@require_POST
def rule_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete a commission rule."""
    rule = get_object_or_404(CommissionRule, pk=pk)
    success, error = CommissionService.delete_rule(rule)

    if success:
        messages.success(request, 'Rule deleted.')
    else:
        messages.error(request, error)

    return redirect('commissions:rule_list')


@require_POST
def rule_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    """Toggle rule active status."""
    rule = get_object_or_404(CommissionRule, pk=pk)
    is_active = CommissionService.toggle_rule(rule)

    if request.headers.get('HX-Request'):
        color = 'success' if is_active else 'medium'
        text = 'Active' if is_active else 'Inactive'
        return HttpResponse(f'<ion-badge color="{color}">{text}</ion-badge>')

    messages.success(request, f'Rule {"activated" if is_active else "deactivated"}.')
    return redirect('commissions:rule_list')


# ==================== Adjustments ====================

@module_view('commissions', 'transactions')
def adjustment_list(request: HttpRequest) -> HttpResponse:
    """List all adjustments."""
    type_filter = request.GET.get('type', '')

    adjustments = CommissionService.get_adjustments(
        adjustment_type=type_filter if type_filter else None,
    )

    context = {
        'adjustments': adjustments,
        'type_filter': type_filter,
        'page_title': 'Adjustments',
    }
    return render(request, 'commissions/adjustment_list.html', context)


@module_view('commissions', 'transactions')
def adjustment_create(request: HttpRequest) -> HttpResponse:
    """Create a manual adjustment."""
    if request.method == 'POST':
        staff_id = request.POST.get('staff_id')
        staff_name = request.POST.get('staff_name', '')
        adjustment_type = request.POST.get('adjustment_type', 'bonus')
        amount = request.POST.get('amount', '0')
        reason = request.POST.get('reason', '')
        adjustment_date = request.POST.get('adjustment_date')

        try:
            adj, error = CommissionService.create_adjustment(
                staff_id=int(staff_id),
                staff_name=staff_name,
                adjustment_type=adjustment_type,
                amount=Decimal(amount),
                reason=reason,
                adjustment_date=date.fromisoformat(adjustment_date) if adjustment_date else None,
                created_by_id=request.user.id if request.user.is_authenticated else None,
            )

            if adj:
                messages.success(request, 'Adjustment created.')
                return redirect('commissions:adjustment_list')
            else:
                messages.error(request, error)
        except Exception as e:
            messages.error(request, str(e))

    # Get staff list
    staff_list = []
    try:
        from staff.models import StaffMember
        staff_list = StaffMember.objects.filter(status='active')
    except Exception:
        pass

    context = {
        'staff_list': staff_list,
        'page_title': 'New Adjustment',
        'page_type': 'form',
        'back_url': '/modules/commissions/adjustments/',
    }
    return render(request, 'commissions/adjustment_form.html', context)


@module_view('commissions', 'transactions')
def adjustment_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """View adjustment details."""
    adjustment = get_object_or_404(CommissionAdjustment, pk=pk)

    context = {
        'adjustment': adjustment,
        'page_title': f'Adjustment #{pk}',
        'page_type': 'detail',
        'back_url': '/modules/commissions/adjustments/',
    }
    return render(request, 'commissions/adjustment_detail.html', context)


@require_POST
def adjustment_approve(request: HttpRequest, pk: int) -> HttpResponse:
    """Approve an adjustment - not applicable in this model."""
    messages.info(request, 'Adjustments are automatically approved.')
    return redirect('commissions:adjustment_detail', pk=pk)


@require_POST
def adjustment_reject(request: HttpRequest, pk: int) -> HttpResponse:
    """Reject an adjustment - delete it."""
    adjustment = get_object_or_404(CommissionAdjustment, pk=pk)
    adjustment.delete()
    messages.success(request, 'Adjustment deleted.')
    return redirect('commissions:adjustment_list')


# ==================== Settings ====================

@module_view('commissions', 'settings')
def settings(request: HttpRequest) -> HttpResponse:
    """Module settings."""
    config = CommissionService.get_config()

    if request.method == 'POST':
        calculation_basis = request.POST.get('calculation_basis', 'net')
        payout_frequency = request.POST.get('payout_frequency', 'monthly')
        payout_day = request.POST.get('payout_day', '1')
        minimum_payout_amount = request.POST.get('minimum_payout_amount', '0')
        default_commission_rate = request.POST.get('default_commission_rate', '0')
        apply_tax_withholding = request.POST.get('apply_tax_withholding') == 'on'
        tax_withholding_rate = request.POST.get('tax_withholding_rate', '0')
        show_commission_on_receipt = request.POST.get('show_commission_on_receipt') == 'on'
        show_pending_commission = request.POST.get('show_pending_commission') == 'on'

        try:
            success, error = CommissionService.update_config(
                calculation_basis=calculation_basis,
                payout_frequency=payout_frequency,
                payout_day=int(payout_day),
                minimum_payout_amount=Decimal(minimum_payout_amount),
                default_commission_rate=Decimal(default_commission_rate),
                apply_tax_withholding=apply_tax_withholding,
                tax_withholding_rate=Decimal(tax_withholding_rate),
                show_commission_on_receipt=show_commission_on_receipt,
                show_pending_commission=show_pending_commission,
            )

            if success:
                messages.success(request, 'Settings updated.')
            else:
                messages.error(request, error)
        except (InvalidOperation, ValueError) as e:
            messages.error(request, f'Invalid input: {e}')

        return redirect('commissions:settings')

    context = {
        'config': config,
        'page_title': 'Settings',
    }
    return render(request, 'commissions/settings.html', context)


# ==================== API Endpoints ====================

@require_POST
def api_calculate_commission(request: HttpRequest) -> JsonResponse:
    """API to calculate commission for a given amount and rule."""
    try:
        amount = Decimal(request.POST.get('amount', '0'))
        rule_id = request.POST.get('rule_id')

        if not rule_id:
            return JsonResponse({'error': 'Rule ID required'}, status=400)

        rule = CommissionService.get_rule(int(rule_id))
        if not rule:
            return JsonResponse({'error': 'Rule not found'}, status=404)

        commission = CommissionService.calculate_commission(amount, rule)
        net, tax = CommissionService.calculate_with_tax(commission)

        return JsonResponse({
            'amount': str(amount),
            'commission_amount': str(commission),
            'tax_withheld': str(tax),
            'net_amount': str(net),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def api_staff_summary(request: HttpRequest, staff_id: int) -> JsonResponse:
    """API to get staff commission summary."""
    try:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        summary = CommissionService.get_staff_summary(
            staff_id,
            start_date=date.fromisoformat(start_date) if start_date else None,
            end_date=date.fromisoformat(end_date) if end_date else None,
        )

        # Convert Decimal to string for JSON
        for key, value in summary.items():
            if isinstance(value, Decimal):
                summary[key] = str(value)

        return JsonResponse(summary)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
