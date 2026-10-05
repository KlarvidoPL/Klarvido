import { gql } from '@sb/webapp-api-client/graphql';

export const invoicesQuery = gql(/* GraphQL */ `
  query InvoicesPage($tenantId: ID!, $filters: InvoiceFilters, $page: Int!) {
    invoices(tenantId: $tenantId, filters: $filters, page: $page, pageSize: 25) {
      totalCount
      items {
        id
        number
        ksefNumber
        direction
        kind
        issueDate
        sellerName
        sellerNip
        buyerName
        buyerNip
        currency
        net
        vat
        gross
        category {
          id
          name
        }
      }
    }
  }
`);
export const invoiceQuery = gql(/* GraphQL */ `
  query InvoiceDetails($tenantId: ID!, $id: ID!) {
    invoice(tenantId: $tenantId, id: $id) {
      id
      number
      ksefNumber
      direction
      kind
      issueDate
      permanentStorageDate
      createdAt
      sellerName
      sellerNip
      buyerName
      buyerNip
      currency
      net
      vat
      gross
      correctedKsefNumbers
      category {
        id
        name
      }
      lines {
        position
        description
        unit
        quantity
        unitPrice
        net
        vatRate
      }
    }
  }
`);
export const invoiceSetupQuery = gql(/* GraphQL */ `
  query InvoiceSetup($tenantId: ID!) {
    invoiceCategories(tenantId: $tenantId) {
      id
      name
    }
    invoiceSyncStatus(tenantId: $tenantId) {
      connected
      startDate
      lastSuccessAt
      importErrorCount
      runs {
        id
        status
        importedCount
        errorCode
        createdAt
        finishedAt
        completedSubjects
      }
    }
  }
`);
export const startInvoiceSyncMutation = gql(/* GraphQL */ `
  mutation StartInvoiceSyncOp($input: StartInvoiceSyncInput!) {
    startInvoiceSync(input: $input) {
      runId
    }
  }
`);
export const setInvoiceCategoryMutation = gql(/* GraphQL */ `
  mutation SetInvoiceCategoryOp($input: SetInvoiceCategoryInput!) {
    setInvoiceCategory(input: $input) {
      ok
    }
  }
`);
export const invoiceCsvQuery = gql(/* GraphQL */ `
  query InvoiceCsv($tenantId: ID!, $filters: InvoiceFilters) {
    invoiceCsv(tenantId: $tenantId, filters: $filters)
  }
`);
export const invoiceXmlQuery = gql(/* GraphQL */ `
  query InvoiceXml($tenantId: ID!, $id: ID!) {
    invoiceXml(tenantId: $tenantId, id: $id)
  }
`);
