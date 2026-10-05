import { gql } from '@sb/webapp-api-client/graphql';

export const dashboardStatsQuery = gql(/* GraphQL */ `
  query dashboardStatsQuery($tenantId: ID!, $canViewInvoices: Boolean!) {
    invoices(tenantId: $tenantId, pageSize: 1) @include(if: $canViewInvoices) {
      totalCount
    }
    allDocumentDemoItems(first: 100) {
      edges {
        node {
          id
          createdAt
        }
      }
    }
    allNotifications(first: 100) {
      edges {
        node {
          id
          type
          createdAt
          readAt
        }
      }
    }
    tenant(id: $tenantId) {
      userMemberships {
        id
        role
        invitationAccepted
      }
    }
  }
`);
