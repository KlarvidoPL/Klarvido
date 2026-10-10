# Account and organization deletion lifecycle

Account deletion is available in profile settings. Users confirm their email address and authenticate freshly with a password or passkey. Verified 2FA additionally requires a fresh OTP code. Social-only accounts without either credential use the existing verified password setup flow first. An ordinary login session is insufficient.

An accepted last owner must promote another active accepted member or separately delete the shared organization. Ownership is the union of legacy OWNER memberships and RBAC system OWNER roles, counted once per user. `org.delete` alone is not ownership. Ownership-changing mutations and account deletion serialize on organization row locks. Superusers cannot delete accounts through Profile or be deleted through Django Admin. Superuser deletion requires `python manage.py delete_superuser --account-id <id> --administrator-id <id>`, with typed email confirmation and administrator password/OTP. The shared lifecycle and last-active-administrator protection still apply.

## Data removed

- Active account and profile, private/default tenant and its organization-owned content.
- Account memberships, assigned membership roles, and pending invitations associated with the account or its email.
- Passkeys, SSO links/sessions, devices, social associations, OTP secrets, pending authentication challenges and grants, personal favorites, personal notifications, and onboarding drafts.
- Avatar rows and their original/thumbnail files, personal export archives, and unassigned legacy documents created by the account.
- Authentication access is revoked immediately. Cookie responses are cleared; the browser clears Apollo state and reloads the public home page. Old bearer/refresh tokens cannot authenticate the deleted identity. Interactive AI connections recheck account/access state.

## Data preserved

- Shared organizations, their documents and CRUD content, organization-owned activity exports, and notifications delivered to other users.
- Historical organization activity, including immutable actor ID/name snapshots and the existing email snapshot. Backfill uses the currently associated profile where available; it cannot recover previously changed names.
- Minimal account-deletion records containing only immutable account and actor IDs and a deletion time.
- Existing security audit/delivery history follows `AUTH_AUDIT_RETENTION_DAYS` (default 90 days). Historical organization logs/backups follow their organization retention settings. Existing copied historical name/email values are not treated as active profiles.

A new account registered with the same email receives a new identity. It receives no previous memberships or historical actor references. Organization backup restore cannot restore accounts, profiles, memberships or role assignments, and nullable author references to deleted identities remain null.

## Durable cleanup

The shared `ResourceCleanup` outbox distinguishes organization and account IDs, supports public avatar storage and private personal-export storage, retries errors, and survives queue submission failure. Celery Beat sweeps due work every minute. S3 deletion removes object versions and delete markers where versioning exists.

New avatars live under `avatars/users/<account-id>/`; new personal exports under `users/<account-id>/`. Cleanup scans these exact prefixes, and the exact old `exports/<account-id>_` filename prefix for legacy personal exports. Existing recorded avatar paths are also removed. Previously unrecorded legacy avatars with random paths cannot reliably be assigned to a person; this feature cannot safely infer their owner.

User exports and avatar publication hold the account lock, preventing a running publisher from creating new files after account deletion collected cleanup work. Temporary export files use unique filenames and are removed on success/failure. A process killed before its `finally` block can leave a container-local temporary file; container recycling removes it.

Final confirmation uses the durable security email outbox with retries within the configured delivery-history retention window; it contains no login proof. Monitor unresolved delivery failures before retention expires. In-app owner notices are created in the deletion transaction. SMTP delivery is at least once: a worker crash after SMTP acceptance can duplicate confirmation.

## Administration and deployment

Django Admin individual deletion uses the same service, with fresh administrator password/OTP confirmation. The default bulk delete action and direct bulk deletion hook are blocked. A last owner or last active administrator cannot be removed through Admin. Account deletion records and delivery/cleanup outboxes are read-only in Admin.

Apply the new Django migrations and deploy the backend, frontend, email renderer, Celery worker and Beat. Publish the added translations for all eight languages. No subscription changes or production data wipe are included.

Before release, verify storage permissions for public avatars and the private exports bucket include object listing, bucket versioning, version listing and version deletion. The AWS task-role definition already includes these for the upload and export buckets. Other providers must support the configured storage operations or leave failures visible for retry/review.

## Restoring a full database

Durable cleanup also writes minimal external identity markers under `account-deletions/<account-id>.json` in the personal-export storage. These markers contain an immutable ID and deletion time, not an email/name. Keep this ledger outside database rollback and exempt it from personal-export expiry rules. Inspect pending `account_marker` work before planning restoration; unpublished markers must be preserved separately.

Keep the application in maintenance mode while restoring a database. After migrations, with the external storage ledger intact, run:

```sh
python manage.py reconcile_deleted_accounts --administrator-id <surviving-administrator-hashid>
```

The command disables restored deleted identities first, then reapplies deletion through the shared service without interactive grants. It refuses a deleted operator identity. Failures leave accounts disabled and require review before reopening access. PostgreSQL's account sequence is advanced beyond deleted IDs to prevent identity reuse. Shared organizations restored without a surviving owner require administrator repair; they must not be assigned automatically to a newly registered account matching an old email.

Restoring storage to an older point in time can also erase this ledger. Preserve a current ledger copy independently before any such operation. Database backup retention, off-site storage copies, and provider access-log retention remain operational settings; the application does not claim immediate erasure from every historical backup.

## Future feature checklist

The canonical agent instructions are in `CLAUDE.md`. Every new user/organization-owned record, storage path, authentication proof, copied personal value, or background job must define deletion, preservation/anonymization, concurrent publication, durable cleanup and backup-restore behavior, and add regression coverage in the same change.
