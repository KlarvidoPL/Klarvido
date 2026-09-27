import graphene
from graphql import GraphQLError
from graphql_relay import from_global_id

from common.acl.policies import IsTenantMemberAccess
from common.graphql.acl import permission_classes

from apps.klarvido.calculations import PeriodPreset
from apps.klarvido.overview import build_overview


class PeriodType(graphene.ObjectType):
    start_date = graphene.Date(required=True)
    end_date = graphene.Date(required=True)


class SourceReferenceType(graphene.ObjectType):
    source_system = graphene.String(required=True)
    external_id = graphene.String(required=True)
    source_record_id = graphene.ID()


class DataQualityType(graphene.ObjectType):
    status = graphene.String(required=True)
    score = graphene.Float()
    limitations = graphene.List(graphene.NonNull(graphene.String), required=True)


class AnalyticalValueType(graphene.ObjectType):
    value = graphene.String()
    unit = graphene.String(required=True)
    period = graphene.Field(PeriodType, required=True)
    comparison_period = graphene.Field(PeriodType)
    sources = graphene.List(graphene.NonNull(SourceReferenceType), required=True)
    calculation_version = graphene.String(required=True)
    calculated_at = graphene.DateTime(required=True)
    quality = graphene.Field(DataQualityType, required=True)
    kind = graphene.String(required=True)
    limitations = graphene.List(graphene.NonNull(graphene.String), required=True)

    @staticmethod
    def resolve_value(root, info):
        return None if root.value is None else str(root.value)


class FinancialSummaryType(graphene.ObjectType):
    revenue = graphene.Field(AnalyticalValueType, required=True)
    costs = graphene.Field(AnalyticalValueType, required=True)
    pre_tax_result = graphene.Field(AnalyticalValueType, required=True)
    gross_margin = graphene.Field(AnalyticalValueType, required=True)
    income_tax = graphene.Field(AnalyticalValueType)
    net_result = graphene.Field(AnalyticalValueType)
    net_margin = graphene.Field(AnalyticalValueType)
    revenue_change = graphene.Field(AnalyticalValueType)
    costs_change = graphene.Field(AnalyticalValueType)
    pre_tax_result_change = graphene.Field(AnalyticalValueType)
    gross_margin_change = graphene.Field(AnalyticalValueType)
    net_result_change = graphene.Field(AnalyticalValueType)
    net_margin_change = graphene.Field(AnalyticalValueType)


class MonthlySummaryType(graphene.ObjectType):
    label = graphene.String(required=True)
    period = graphene.Field(PeriodType, required=True)
    summary = graphene.Field(FinancialSummaryType, required=True)


class PartyTrendPointType(graphene.ObjectType):
    label = graphene.String(required=True)
    period = graphene.Field(PeriodType, required=True)
    amount = graphene.Field(AnalyticalValueType)


class PartyType(graphene.ObjectType):
    id = graphene.ID(required=True)
    name = graphene.String(required=True)
    tax_identifier = graphene.String(required=True)
    amount = graphene.Field(AnalyticalValueType, required=True)
    share = graphene.Field(AnalyticalValueType, required=True)
    percentage_change = graphene.Field(AnalyticalValueType)
    invoice_count = graphene.Field(AnalyticalValueType, required=True)
    trend = graphene.List(graphene.NonNull(PartyTrendPointType), required=True)

    @staticmethod
    def resolve_id(root, info):
        return root.aggregate.counterparty_id

    @staticmethod
    def resolve_name(root, info):
        return root.aggregate.name

    @staticmethod
    def resolve_tax_identifier(root, info):
        return root.aggregate.tax_identifier

    @staticmethod
    def resolve_amount(root, info):
        return root.aggregate.amount

    @staticmethod
    def resolve_share(root, info):
        return root.aggregate.share

    @staticmethod
    def resolve_percentage_change(root, info):
        return root.aggregate.percentage_change

    @staticmethod
    def resolve_invoice_count(root, info):
        return root.aggregate.invoice_count


class PortfolioType(graphene.ObjectType):
    invoice_type = graphene.String(required=True)
    total = graphene.Field(AnalyticalValueType, required=True)
    top_three_concentration = graphene.Field(AnalyticalValueType, required=True)
    active_count = graphene.Field(AnalyticalValueType, required=True)
    largest_party = graphene.Field(PartyType, required=True)
    parties = graphene.List(graphene.NonNull(PartyType), required=True)

    @staticmethod
    def resolve_invoice_type(root, info):
        return root.aggregate.invoice_type

    @staticmethod
    def resolve_total(root, info):
        return root.aggregate.total

    @staticmethod
    def resolve_top_three_concentration(root, info):
        return root.aggregate.top_three_concentration

    @staticmethod
    def resolve_active_count(root, info):
        return root.aggregate.active_count

    @staticmethod
    def resolve_largest_party(root, info):
        party = root.aggregate.largest_party
        return next(item for item in root.parties if item.aggregate.counterparty_id == party.counterparty_id)


class CategoryType(graphene.ObjectType):
    code = graphene.String()
    name = graphene.String(required=True)
    amount = graphene.Field(AnalyticalValueType, required=True)
    share = graphene.Field(AnalyticalValueType, required=True)

    @staticmethod
    def resolve_code(root, info):
        return root.category_code

    @staticmethod
    def resolve_name(root, info):
        return root.category_name


class CostStructureType(graphene.ObjectType):
    total = graphene.Field(AnalyticalValueType, required=True)
    categories = graphene.List(graphene.NonNull(CategoryType), required=True)


class InvoiceType(graphene.ObjectType):
    id = graphene.ID(required=True)
    document_number = graphene.String(required=True)
    invoice_type = graphene.String(required=True)
    status = graphene.String(required=True)
    issue_date = graphene.Date(required=True)
    due_date = graphene.Date()
    counterparty_name = graphene.String(required=True)
    counterparty_tax_identifier = graphene.String(required=True)
    currency = graphene.String(required=True)
    net_amount = graphene.String(required=True)
    tax_amount = graphene.String(required=True)
    gross_amount = graphene.String(required=True)
    categories = graphene.List(graphene.NonNull(graphene.String), required=True)
    source_system = graphene.String(required=True)
    source_external_id = graphene.String(required=True)
    quality_status = graphene.String(required=True)

    @staticmethod
    def resolve_id(root, info):
        return str(root.invoice.id)

    @staticmethod
    def resolve_counterparty_name(root, info):
        return root.invoice.counterparty.name

    @staticmethod
    def resolve_counterparty_tax_identifier(root, info):
        return root.invoice.counterparty.tax_identifier

    @staticmethod
    def resolve_source_system(root, info):
        return root.invoice.source_record.source_system

    @staticmethod
    def resolve_source_external_id(root, info):
        return root.invoice.source_record.external_id

    @staticmethod
    def resolve_quality_status(root, info):
        return root.invoice.source_record.validation_status

    @staticmethod
    def resolve_document_number(root, info):
        return root.invoice.document_number

    @staticmethod
    def resolve_invoice_type(root, info):
        return root.invoice.invoice_type

    @staticmethod
    def resolve_status(root, info):
        return root.invoice.status

    @staticmethod
    def resolve_issue_date(root, info):
        return root.invoice.issue_date

    @staticmethod
    def resolve_due_date(root, info):
        return root.invoice.due_date

    @staticmethod
    def resolve_currency(root, info):
        return root.invoice.currency

    @staticmethod
    def resolve_net_amount(root, info):
        return str(root.invoice.net_amount)

    @staticmethod
    def resolve_tax_amount(root, info):
        return str(root.invoice.tax_amount)

    @staticmethod
    def resolve_gross_amount(root, info):
        return str(root.invoice.gross_amount)


class ReadinessMetricType(graphene.ObjectType):
    code = graphene.String(required=True)
    label = graphene.String(required=True)
    value = graphene.Float(required=True)
    unit = graphene.String(required=True)
    status = graphene.String(required=True)
    ready_threshold = graphene.Float(required=True)
    limited_threshold = graphene.Float(required=True)


class ReadinessType(graphene.ObjectType):
    analysis = graphene.String(required=True)
    status = graphene.String(required=True)
    score = graphene.Float(required=True)
    limitations = graphene.List(graphene.NonNull(graphene.String), required=True)
    metrics = graphene.List(graphene.NonNull(ReadinessMetricType), required=True)
    policy_version = graphene.String(required=True)
    checked_at = graphene.DateTime(required=True)


class CompanyType(graphene.ObjectType):
    legal_name = graphene.String(required=True)
    tax_identifier = graphene.String(required=True)
    regon = graphene.String(required=True)
    pkd_code = graphene.String(required=True)
    country_code = graphene.String(required=True)
    default_currency = graphene.String(required=True)


class KlarvidoOverviewType(graphene.ObjectType):
    company = graphene.Field(CompanyType)
    preset = graphene.String(required=True)
    period = graphene.Field(PeriodType, required=True)
    comparison_period = graphene.Field(PeriodType)
    financial_summary = graphene.Field(FinancialSummaryType, required=True)
    monthly_summaries = graphene.List(graphene.NonNull(MonthlySummaryType), required=True)
    customers = graphene.Field(PortfolioType, required=True)
    suppliers = graphene.Field(PortfolioType, required=True)
    cost_structure = graphene.Field(CostStructureType, required=True)
    invoices = graphene.List(graphene.NonNull(InvoiceType), required=True)
    readiness = graphene.List(graphene.NonNull(ReadinessType), required=True)


class Query(graphene.ObjectType):
    klarvido_overview = graphene.Field(
        KlarvidoOverviewType,
        tenant_id=graphene.ID(required=True),
        preset=graphene.String(default_value=PeriodPreset.HALF_YEAR.value),
    )

    @staticmethod
    @permission_classes(IsTenantMemberAccess)
    def resolve_klarvido_overview(root, info, tenant_id, preset):
        _, requested_tenant_id = from_global_id(tenant_id)
        tenant = info.context.tenant
        if str(tenant.id) != requested_tenant_id:
            raise GraphQLError("The requested tenant does not match the authenticated tenant context.")
        try:
            period_preset = PeriodPreset(preset)
        except ValueError as error:
            raise GraphQLError("Unsupported Klarvido period preset.") from error
        return build_overview(tenant, period_preset)
