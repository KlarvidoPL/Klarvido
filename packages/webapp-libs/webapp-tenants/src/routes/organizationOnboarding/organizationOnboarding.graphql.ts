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

export const organizationOnboardingDraftQuery = gql(/* GraphQL */ `
  query organizationOnboardingDraft {
    organizationOnboardingDraft {
      companyData {
        name
        country
        nip
        companyName
        regon
        address
        vatStatus
      }
      respondentRole
      customerType
      revenueModels
      costDrivers
      pricing
      mainGoal
      currentStep
      isRequired
      completedAt
    }
  }
`);

export const saveOrganizationOnboardingDraftMutation = gql(/* GraphQL */ `
  mutation saveOrganizationOnboardingDraftOperation(
    $step: Int!
    $company: OnboardingCompanyInput
    $respondentRole: String
    $customerType: String
    $revenueModels: [String]
    $costDrivers: [String]
    $pricing: String
    $mainGoal: String
  ) {
    saveOrganizationOnboardingDraft(
      step: $step
      company: $company
      respondentRole: $respondentRole
      customerType: $customerType
      revenueModels: $revenueModels
      costDrivers: $costDrivers
      pricing: $pricing
      mainGoal: $mainGoal
    ) {
      tenant {
        id
        name
      }
      profile {
        currentStep
        completedAt
      }
    }
  }
`);

export const clearOrganizationOnboardingDraftMutation = gql(/* GraphQL */ `
  mutation clearOrganizationOnboardingDraftOperation {
    clearOrganizationOnboardingDraft {
      ok
    }
  }
`);

export const organizationOnboardingChoicesQuery = gql(/* GraphQL */ `
  query organizationOnboardingChoices {
    organizationOnboardingChoices {
      respondentRoles
      customerTypes
      revenueModels
      costDrivers
      pricingModels
      mainGoals
    }
  }
`);
