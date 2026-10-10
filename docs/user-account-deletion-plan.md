x # User account deletion implementation plan

Status: implementation reference. See `user-account-deletion.md` for the implemented behavior and operational steps. Django Admin bulk account deletion is deliberately disabled; individual deletion uses the shared protected service.

## Agreed behavior

- Users can permanently delete their own accounts after explicit confirmation and fresh authentication. Require OTP when verified 2FA is enabled.
- A last owner must first promote another accepted member to owner or separately delete the organization.
- Account deletion does not delete shared organizations or their content.
- Historical attribution remains separate from an active account. A new registration with the same email receives a new account ID and no inherited access.
- No recovery window in the first version. External cleanup may complete asynchronously with durable retries.
- Subscription behavior is outside this feature's scope.

## Findings that must be addressed first

1. `Tenant.creator` currently uses `CASCADE`. Deleting a creator can delete an organization even after ownership transfer. Change this to nullable `SET_NULL`, preserve creator attribution separately where needed, and update `Tenant.email`, which currently falls back to `creator.email`.
2. `CrudDemoItem.created_by

`uses`CASCADE`. Change it to `SET*NULL`so shared organization items survive.
3.`Notification.issuer`uses`CASCADE`. Change it to `SET_NULL`so notifications delivered to other users survive.
4.`ActionLogExport.requested_by`uses`CASCADE`. Preserve organization-owned export records and their files with `SET_NULL`; adjust workers and displays for a missing requester.
5. `UserProfile.avatar`points to`UserAvatar`; deleting the profile does not inherently delete the avatar row or public-storage files. Collect and clean the original and thumbnail explicitly.
6. `ActionLog`already preserves`actor_email`and sets`actor_user`to null, but has no dedicated immutable actor-ID/name snapshot. Add these for future events and backfill existing rows while the referenced account exists.
7. User exports use a separate S3 exports bucket and timestamped`exports/<user-id>*...zip` paths. Existing organization cleanup cannot simply be used unchanged. 8. Ownership exists in both legacy membership roles and RBAC system owner roles. Existing owner-count properties are insufficient for this feature. 9. Default/personal tenants are protected from ordinary organization deletion. Account deletion needs a narrowly scoped internal cleanup path for the account's private tenant.

## 1. Ownership and preservation migrations

Create a shared ownership predicate: distinct active users with accepted memberships, whose legacy role is OWNER or whose assigned system role is OWNER. Custom roles containing `org.delete`, pending invitations, and superuser bypass are not ownership.

Use the predicate for account eligibility and last-owner checks in role assignment, demotion, member removal, leaving an organization, and administrative operations. Serialize those operations on the same organization row locks. Lock multiple organizations in deterministic order and recheck eligibility inside the final transaction. Bulk account deletion must consider all selected users together.

Apply the preservation migrations above. Audit every remaining user relation, including KSeF, translation publishing, Django Admin logs, SSO audit records, and third-party token/social-auth tables. Update serializers, workers, exports, and frontend displays that assume a creator/requester/issuer is always present.

## 2. Historical identity

Store immutable actor ID, display-name snapshot, and the existing email snapshot on organization activity. Keep these as historical attribution, not as a reusable login identity. Snapshot at event creation; do not resolve historical names from a new account or mutable current profile.

Backfill snapshots only from existing referenced users. Do not infer missing historical identities by matching email. Preserve documents and shared CRUD records with neutral attribution where no historical snapshot is available.

Document where historical personal information remains. Define retention separately for security logs, operational logs, delivery records, and backups; signup wording must match the actual behavior.

## 3. Fresh authentication

Introduce an account-deletion-specific, short-lived, single-use server-side authorization grant. Reuse password/passkey verification, credential-version binding, attempt limits, and OTP validation patterns; do not reuse a passkey-management grant for a different action.

- Password users: current password, plus OTP when enabled.
- Passkey users: fresh WebAuthn assertion, plus OTP when enabled.
- Social/SSO-only users without a password or passkey: dedicated fresh provider reauthentication bound to the current account and deletion action. Never use email matching or an ordinary stale session as proof. If provider support cannot be safely implemented in the first release, offer the existing verified password/passkey setup flow before deletion.

Keep OTP failure counters outside the final deletion transaction so failed attempts are not rolled back. Consume the grant atomically with deletion and recheck credential state after acquiring locks. Enforce CSRF and keep credentials out of activity logs and browser storage.

## 4. Shared deletion service and API

Add `apps/users/services/deletion.py`, a self-service eligibility query, and a serializer-based deletion mutation in the existing users schema. The self-service mutation targets only the authenticated account; it must not accept an arbitrary account ID.

Inside the transaction:

1. Lock affected organization rows and the account using one documented lock order shared with relevant membership/job operations.
2. Recheck account identity, fresh proof, and last-owner blockers.
3. Snapshot historical attribution and personal file cleanup work.
4. Remove pending invitations for the deleted account/email so later registration cannot silently inherit access; preserve invitations the user issued to other people where appropriate.
5. Remove the private/default tenant through the internal cleanup workflow, including its documents, backups, exports, and keys. Explicitly verify that it is private; unexpected shared membership blocks deletion for investigation rather than silently deleting shared data.
6. Persist cleanup, final confirmation delivery, owner notifications, and an independent minimal deletion audit record.
7. Revoke access and delete the account and its exclusively owned records. Remove passkeys, devices, SSO sessions/links, OTP state, social associations, pending authentication grants, personal notifications, favorites, and onboarding drafts.
8. Commit; dispatch durable work on commit, with scheduled retry recovery if broker submission fails.

Verify browser JWT, refresh, Django Admin sessions, bearer integrations, WebSockets, and MCP access cannot continue using a deleted identity. Clear response cookies through the existing authentication response mechanism; clear frontend Apollo/user state and redirect to the public home page. Audit existing account-reclaim and SCIM deprovisioning paths so they cannot accidentally bypass the new invariants.

## 5. Durable cleanup and concurrent work

Extend or extract the existing organization cleanup outbox into a service supporting account resources and explicit storage targets. Do not route public avatars or the separate exports bucket through the wrong storage backend.

Track avatar originals/thumbnails, personal exports, local export temporaries, and any other audited personal files. For legacy timestamped exports, scan using the exact account-ID delimiter and canonical IDs, not a loose prefix that can match another account. Delete S3 versions/delete markers where supported and retry provider/retention failures.

Coordinate user export generation and avatar upload/publication with deletion. A worker holding an old in-memory user must not publish files after deletion. Check identity existence under the shared publication lock and clean failed uploads. Ordinary queued security emails should cancel after deletion; the final confirmation needs a separate delivery path independent of the deleted user FK.

Organization backups remain organization-owned. Inspect their user-management restore behavior and prevent recreation or email-based relinking of deleted accounts. Keep minimal deletion markers keyed by immutable account ID for restoration reconciliation. Full database restoration must replay markers from a source that is not rolled back with the restored database; document this operational requirement and backup expiry policy.

## 6. UI and Django Admin

Add a danger-zone section to the existing profile page. Show affected organizations, last-owner blockers, and links to membership management or organization deletion. No silent ownership reassignment or automatic shared-organization deletion.

Confirmation shows permanent deletion consequences, retained shared content/history, typed confirmation, fresh-auth fields, and the existing OTP input/error styling. Support all eight languages, keyboard navigation, mobile layout, loading states, and field-level errors. Recheck backend eligibility even after the UI preflight.

Route Django Admin single/bulk deletion through the same service with explicit admin authorization and fresh authentication of the acting administrator. Preserve ownership rules and prevent removal of the last active administrator. Do not expose the self-service mutation to AI/MCP automation in the initial release.

## 7. Validation and rollout

Backend tests: last owner in multiple organizations; legacy/RBAC owner deduplication; pending/inactive owners; concurrent owner demotion/deletion; creator departure without organization loss; private tenant cleanup; shared CRUD/documents/exports/notifications preservation; avatar cleanup; stale/replayed authentication; OTP budgets; email reuse/invitation isolation; access revocation; worker publication races; durable retry after broker/storage/email failure; restore reconciliation; Admin single/bulk deletion and rollback.

Frontend tests: blocker links, password/passkey/provider paths, OTP errors, confirmation/reset behavior, successful logout/cache cleanup, duplicate submission prevention, and mobile/accessibility behavior.

Regenerate GraphQL schema/types through the running backend; update translations. Run scoped lint/type checks, migration consistency checks, affected backend/frontend tests, and frontend build. Use staging for storage/version cleanup and multi-device manual verification.

Deliver in this order: preservation/ownership foundations; identity and grants; deletion service/outboxes/job coordination; profile/Admin UI; tests and operational documentation. Ship only after the entire workflow is verified. No production wipe or deployment is part of preparing this plan.
