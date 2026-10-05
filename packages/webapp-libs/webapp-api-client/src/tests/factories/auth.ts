import { Role } from '../../api/auth';
import { TenantType } from '../../constants/tenant.types';
import { CurrentUserType, TenantUserRole } from '../../graphql';
import { createFactory, makeId } from '../utils';

export const currentUserFactory = createFactory<CurrentUserType>(() => ({
  id: makeId(32),
  firstName: 'testFirstName',
  lastName: 'testLastName',
  email: 'mock@example.org',
  language: 'en',
  roles: [Role.ADMIN, Role.USER],
  avatar: 'https://cloudflare-ipfs.com/ipfs/Qmd3W5DuhgHirLHGVixi6V76LhCkZUz6pnFt5AJBiyvHye/avatar/315.jpg',
  otpEnabled: false,
  otpVerified: false,
  hasSeenWelcomeModal: true,
  isConfirmed: true,
  isSuperuser: false,
  defaultOrganizationId: null,
  tenants: [
    {
      id: makeId(32),
      name: 'Tenant Name',
      // Real organization by default - a working org context is the normal/happy-path
      // scenario most tests want; specifically testing the personal/no-org state
      // should opt in explicitly (e.g. `tenants: [{ ...  type: TenantType.PERSONAL }]`).
      type: TenantType.ORGANIZATION,
      onboardingRequired: false,
      onboardingCompleted: true,
      __typename: 'TenantType',
      membership: {
        id: makeId(32),
        invitationAccepted: true,
        invitationToken: makeId(32),
        role: TenantUserRole.OWNER,
        inviteeEmailAddress: 'invitee@example.org',
        userId: makeId(32),
        firstName: 'MembershipFirstName',
        lastName: 'MembershipLastName',
        userEmail: 'membership@example.org',
        avatar: 'https://example.com/avatar.jpg',
        __typename: 'TenantMembershipType',
      },
    },
  ],
}));
