import { gql } from '@sb/webapp-api-client/graphql';

export const organizationOnboardingProfileQuery = gql(/* GraphQL */ `
  query organizationOnboardingProfile($tenantId: ID!) {
    organizationOnboardingProfile(tenantId: $tenantId) {
      respondentRole
      customerType
      revenueModels
      costDrivers
      pricing
      mainGoal
      currentStep
      isRequired
      ksefStatus
      completedAt
    }
  }
`);

export const saveOrganizationOnboardingStepMutation = gql(/* GraphQL */ `
  mutation saveOnboardingStepOperation(
    $tenantId: ID!
    $step: Int!
    $respondentRole: String
    $customerType: String
    $revenueModels: [String]
    $costDrivers: [String]
    $pricing: String
    $mainGoal: String
    $ksefToken: String
  ) {
    saveOrganizationOnboardingStep(
      tenantId: $tenantId
      step: $step
      respondentRole: $respondentRole
      customerType: $customerType
      revenueModels: $revenueModels
      costDrivers: $costDrivers
      pricing: $pricing
      mainGoal: $mainGoal
      ksefToken: $ksefToken
    ) {
      profile {
        respondentRole
        customerType
        revenueModels
        costDrivers
        pricing
        mainGoal
        currentStep
        isRequired
        ksefStatus
        completedAt
      }
    }
  }
`);

export const updateOnboardingTenantMutation = gql(/* GraphQL */ `
  mutation updateOnboardingTenant($input: UpdateTenantMutationInput!) {
    updateTenant(input: $input) {
      tenant {
        id
        name
        country
        nip
        companyName
        regon
        address
        vatStatus
        onboardingRequired
        onboardingCompleted
      }
    }
  }
`);
