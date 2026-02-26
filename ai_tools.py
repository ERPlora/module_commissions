"""AI tools for the Commissions module."""
from assistant.tools import AssistantTool, register_tool


@register_tool
class GetCommissionSummary(AssistantTool):
    name = "get_commission_summary"
    description = "Get commission summary for a date range: total pending, approved, paid by staff."
    module_id = "commissions"
    required_permission = "commissions.view_commissiontransaction"
    parameters = {
        "type": "object",
        "properties": {
            "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
            "date_to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
            "staff_id": {"type": "string", "description": "Filter by staff member ID"},
        },
        "required": [],
        "additionalProperties": False,
    }

    def execute(self, args, request):
        from datetime import date, timedelta
        from django.db.models import Sum, Count
        from commissions.models import CommissionTransaction
        date_from = args.get('date_from', str(date.today().replace(day=1)))
        date_to = args.get('date_to', str(date.today()))
        qs = CommissionTransaction.objects.filter(
            transaction_date__gte=date_from,
            transaction_date__lte=date_to,
        )
        if args.get('staff_id'):
            qs = qs.filter(staff_id=args['staff_id'])
        by_status = qs.values('status').annotate(
            total=Sum('commission_amount'),
            count=Count('id'),
        )
        return {
            "date_from": date_from,
            "date_to": date_to,
            "by_status": [
                {"status": item['status'], "total": str(item['total'] or 0), "count": item['count']}
                for item in by_status
            ],
        }


@register_tool
class ListCommissionRules(AssistantTool):
    name = "list_commission_rules"
    description = "List active commission rules."
    module_id = "commissions"
    required_permission = "commissions.view_commissionrule"
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    def execute(self, args, request):
        from commissions.models import CommissionRule
        rules = CommissionRule.objects.filter(is_active=True).order_by('priority')
        return {
            "rules": [
                {
                    "id": str(r.id),
                    "name": r.name,
                    "rule_type": r.rule_type,
                    "rate": str(r.rate) if r.rate else None,
                    "priority": r.priority,
                    "effective_from": str(r.effective_from) if r.effective_from else None,
                    "effective_until": str(r.effective_until) if r.effective_until else None,
                }
                for r in rules
            ]
        }
