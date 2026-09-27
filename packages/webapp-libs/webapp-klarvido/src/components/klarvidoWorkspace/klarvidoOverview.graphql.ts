import { gql } from '@sb/webapp-api-client/graphql';

export const klarvidoOverviewQuery = gql(/* GraphQL */ `
  query klarvidoOverviewQuery($tenantId: ID!, $preset: String!) {
    klarvidoOverview(tenantId: $tenantId, preset: $preset) {
      preset
      period {
        startDate
        endDate
      }
      comparisonPeriod {
        startDate
        endDate
      }
      company {
        legalName
        taxIdentifier
        regon
        pkdCode
        countryCode
        defaultCurrency
      }
      financialSummary {
        revenue { value unit kind calculationVersion calculatedAt quality { status score limitations } revenueSources: sources { sourceSystem externalId sourceRecordId } }
        costs { value unit kind calculationVersion calculatedAt quality { status score limitations } }
        preTaxResult { value unit kind calculationVersion calculatedAt quality { status score limitations } }
        grossMargin { value unit kind calculationVersion calculatedAt quality { status score limitations } }
        revenueChange { value unit }
        costsChange { value unit }
        preTaxResultChange { value unit }
        grossMarginChange { value unit }
      }
      monthlySummaries {
        label
        period { startDate endDate }
        summary {
          revenue { value unit }
          costs { value unit }
          preTaxResult { value unit }
          grossMargin { value unit }
        }
      }
      customers {
        total { value unit }
        activeCount { value unit }
        topThreeConcentration { value unit }
        largestParty { id name amount { value unit } share { value unit } invoiceCount { value unit } trend { label amount { value unit } } }
        parties {
          id name taxIdentifier
          amount { value unit }
          share { value unit }
          percentageChange { value unit }
          invoiceCount { value unit }
          trend { label amount { value unit } }
        }
      }
      suppliers {
        total { value unit }
        activeCount { value unit }
        topThreeConcentration { value unit }
        largestParty { id name amount { value unit } share { value unit } invoiceCount { value unit } trend { label amount { value unit } } }
        parties {
          id name taxIdentifier
          amount { value unit }
          share { value unit }
          percentageChange { value unit }
          invoiceCount { value unit }
          trend { label amount { value unit } }
        }
      }
      costStructure {
        total { value unit }
        categories { code name amount { value unit } share { value unit } }
      }
      invoices {
        id documentNumber invoiceType status issueDate dueDate
        counterpartyName counterpartyTaxIdentifier currency
        netAmount taxAmount grossAmount categories
        sourceSystem sourceExternalId qualityStatus
      }
      readiness {
        analysis status score limitations policyVersion checkedAt
        metrics { code label value unit status readyThreshold limitedThreshold }
      }
    }
  }
`);
