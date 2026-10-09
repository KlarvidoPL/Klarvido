# Email/password authentication security review

Reviewed 2026-10-08 against master `a4690b1bd5c6bc5daa9ade6cd683b52e7883f647`.

This is a defensive source review with isolated Docker verification, not a production penetration test or a guarantee of complete security. The original audit did not modify application behavior. Findings distinguish reproduced behavior from code observations and deployment-dependent risks. E01, E02, E03 and the replay portion of E07 are addressed by the subsequent local implementation described below; E14 and E15 are implemented locally but await final verification. E13 requires no action: the current signup behavior and its account-enumeration risk are accepted as an intentional product decision. E09, E11 and E12 are implemented locally with verification deferred; E10 contextual validation is implemented with the eight-character minimum retained by product decision. E04–E06, E08 and the remainder of E07 remain open.

## Scope and trust boundaries

Reviewed Django/DRF/Graphene registration, password login, email confirmation, password change/reset, TOTP enrollment/login/removal, JWT cookies, refresh/logout and tracked sessions; React authentication forms/routes and Sentry initialization; authentication-related settings, production proxy configuration and selected dependency versions. Social login was examined where it interacts with password-created accounts, not as a complete OAuth audit.

Principal boundaries: browser to GraphQL/REST; password verification to pending OTP login; pending OTP login to full session; existing session to credential changes; email delivery to reset/confirmation tokens; database/cache/proxy to authentication enforcement; application to monitoring providers.

No live customer accounts, production credentials, email delivery or production database were accessed. No comprehensive dependency scan, live proxy/header test, historical log inspection or full application authorization audit was performed.

## Prioritized findings

| ID  | Severity                                       | Finding                                                                                                                      | Evidence                                                              |
| --- | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| E01 | High — addressed locally                       | Password-created accounts can be preregistered and later confirmed through social login while retaining attacker credentials | Source, state-transition probe and remediation regressions            |
| E02 | High — addressed locally                       | 2FA removal/replacement requires no fresh authentication                                                                     | HTTP removal and service replacement probes; remediation regressions  |
| E03 | High — addressed locally                       | Pending OTP login survives password changes and lacks account-state binding                                                  | Serializer probe; remediation regressions                             |
| E04 | High                                           | First password can be set on a passwordless account using only an existing session                                           | Serializer probe                                                      |
| E05 | High                                           | Password guessing has no account-wide failure budget                                                                         | Source                                                                |
| E06 | Medium                                         | Rate-limit enforcement has inconsistent proxy trust and operation-level fail-open behavior                                   | Helper/decorator probes; proxy exposure conditional                   |
| E07 | Medium — partially addressed locally           | OTP login proof lacks purpose separation and one-time consumption; TOTP codes are reusable                                   | Serializer/service probes; replay fix shipped with E02/E03, see below |
| E08 | Medium — partially addressed locally           | Reset completion now locks/rechecks; broader reset/session recovery verification is deferred                                 | Original probe; new recovery-race regression prepared                 |
| E09 | Medium — implemented; verification deferred    | Reset-email throttling does not implement the configured policy or recipient limits                                          | Source                                                                |
| E10 | Medium — partial; 8-character minimum accepted | Password validation is weaker than the recommended policy and omits user context                                             | Source                                                                |
| E11 | Medium — implemented; verification deferred    | Monitoring does not comprehensively redact authentication URLs, serialized bodies or OTP secrets                             | Redaction probes; actual export conditional                           |
| E12 | Medium — implemented; verification deferred    | TOTP secrets are stored in plaintext                                                                                         | Source                                                                |
| E13 | Medium — no action needed                      | Signup reveals whether an email is registered                                                                                | Source and existing test expectation                                  |
| E14 | Medium — implemented, verification deferred    | Authentication dependency is in a published vulnerable version range                                                         | Lockfile and maintainer advisory; exploitability conditional          |
| E15 | Low — implemented, verification deferred       | Email/password security events lack a durable audit trail and credential-change notifications                                | Source                                                                |

### E01 — Account preregistration and automatic social linking

Remediation implemented: automatic email association is removed. New social users are created without the
legacy get-or-create fallback; uniqueness collisions fail closed. Existing provider associations remain supported.
For a confirmed existing account, a first provider connection redirects to login with a five-minute, one-use,
HttpOnly browser proof backed by a hashed database record. Linking requires fresh password authentication and
OTP when enabled, or a cryptographically verified user-verified passkey. Account ownership, credential changes,
expiry, replay and provider reassignment are checked; session issuance and linking share a transaction.
Unconfirmed accounts must verify their email before retrying. Callback denials redirect safely even in DEBUG.
Cancellation removes the proof; periodic cleanup removes expired records. Existing historical associations
are not retroactively removed. Deployment requires migrations users/0008_pending_social_account_link and
sso/0013_alter_ssoauditlog_event_type.

Follow-up hardening since the above: the provider must itself assert the email as verified (Google's
`email_verified` claim checked explicitly, not inferred from reaching the callback) before either creating an
account or matching an existing one - this closes a gap where an attacker-controlled but provider-unverified
email could otherwise have driven the same account-creation/linking paths. A linked notification email is now
sent to the account owner on every successful link. The unconfirmed-account case is explicitly split from the
inactive-account case (distinct redirect reasons) and audit-logged on denial, rather than relying on manual
reclaim rules implied by general code: automatic reclaim remains deliberately absent (the account may be the
real owner's own unconfirmed signup, with real org data already attached), but a superuser-only, audited Django
Admin action (`reclaim_unconfirmed_account`, confirmation-gated) now gives support a safe path to strip an
unconfirmed account's password/OTP/passkeys/sessions/social links and email a password-reset link to the real
owner, once ownership is verified out of band. The previously-present stock `social-django` disconnect routes
(which required only an ordinary session, no fresh-auth proof - the same class of gap this review flags
elsewhere for OTP management, E02) were removed rather than exposed without equivalent hardening; unlinking a
provider has no self-service path yet.

Additional hardening: activation links are now bound to the password and email address, so reclaim invalidates
old confirmation links as well as password-reset and pending OTP proofs. Confirmation and password-reset completion recheck the token
under an account lock before saving, preventing an in-flight confirmation from restoring stale credentials
across reclaim. Reclaim removes pending passkey challenges and grants and blacklists outstanding refresh tokens.
A self-service unlink flow now requires fresh password plus OTP or verified UV passkey authentication, prevents
last-method lockout, cancels pending links and revokes sessions atomically. All 24 linking/unlinking and email
messages have real translations in eight languages, including database rows and deployment export.

Historical review: `review_social_links --details` produces a read-only inventory of social associations without
recorded ownership proof. New confirmations and verified provider signups record the exact association ID in the security audit. Legacy
records cannot reliably distinguish legitimate social signup from unsafe email merging, so no automatic
credential deletion is performed. The local inventory found three candidates (two with passwords, one with
OTP, one with an active passkey, one with organization memberships). No customer/production database was
accessed; production inventory and mailbox/credential/membership investigation remain operational work.

Verification before the user requested deferring further test execution: 546 users/SSO backend tests and
45 focused UI/hook tests passed; scoped lint and TypeScript checks passed. The later translation migration
check was interrupted at the user's request, and its locale fixture was corrected by inspection. Subsequent
migration/provenance/recovery-race test updates are prepared but unexecuted; run the complete suite after the remaining
vulnerability fixes. Other audit findings remain open.

- Likelihood: Medium; impact: High. Type: account pre-hijacking.
- Components: [signup serializer](packages/backend/apps/users/serializers.py:92), [social pipeline configuration](packages/backend/config/settings.py:516), [social profile pipeline](packages/backend/apps/users/pipeline.py:13).
- Signup creates an active account and authenticates it before email confirmation. `associate_by_email` subsequently selects an existing account with the provider email. `populate_profile_from_social` marks that account confirmed without replacing its password or invalidating its existing sessions.
- Conceptual risk: someone preregisters an address they do not own; the real owner later uses social login with that address. The original password/session can remain usable against the same account after the owner begins using it. This requires the later social-login interaction and is not an immediate takeover of every registered account. MFA enabled later can restrict password login but does not automatically invalidate the original access session.
- Evidence: a probe of the actual confirmation pipeline preserved both the original usable password and authenticated access token. A complete external-provider browser flow was not exercised.
- Fix: prohibit automatic linking to unverified password-created accounts without a secure ownership/recovery transition. Revoke existing sessions and pending login proofs, invalidate untrusted passwords and other authenticators established before ownership confirmation, and require explicit proof before retaining/linking credentials. Merely blocking unconfirmed password login does not resolve automatic account merging.
- Tests: preregistration followed by verified social ownership must not preserve prior password, access/refresh sessions, pending OTP proof or attacker-enrolled authenticators. Preserve explicit linking for legitimately owned accounts.

### E02 — MFA management trusts the current session

- Likelihood: Medium; impact: High. Type: missing reauthentication.
- Components: [authenticated mutations](packages/backend/apps/users/schema.py:270), [OTP services](packages/backend/apps/users/services/otp.py:16).
- `generateOtp`, `verifyOtp` and `disableOtp` require authentication but no fresh password+current OTP or verified passkey proof. Generation overwrites `otp_base32` directly, including for an already verified authenticator, while preserving verified/enabled flags.
- Conceptual risk: access to an unattended browser or compromised current session can remove or replace the user's second factor. Replacement can also lock the real owner out.
- Evidence: an HTTP GraphQL probe disabled OTP using only an ordinary access token. A service probe replaced an active secret and accepted a code from the replacement immediately.
- Fix: extend the existing passkey-management fresh-proof pattern to MFA actions with dedicated action-bound, one-use grants. Keep enrollment secrets separate from the active secret until successful confirmation; require fresh proof before replacing/removing an active factor. Notify the user and revoke appropriate sessions/pending proofs.
- Tests: absent/expired/replayed/foreign grants, setup cancellation, active-secret preservation, valid password+OTP and verified-passkey alternatives, concurrent replacement/removal.
- **Remediation implemented** (`apps/users/serializers.py::GenerateOTPSerializer/VerifyOTPSerializer/DisableOTPSerializer`, `apps/sso/services/passkey_management.py`): `generateOtp`/`verifyOtp` write a _pending_ secret (`User.otp_pending_base32`) separate from the active one; only a successful `verifyOtp` promotes it, so an abandoned/failed setup never touches the active factor. Replacing an already-active factor, or disabling one, now requires a fresh-auth grant from the same `PasskeyManagementGrant` mechanism passkey management already used (`action="otp_setup"` / `"otp_disable"`), via password+current-OTP or a verified passkey. An account with neither a usable password nor a passkey (first-time 2FA setup on a Google-only account) is allowed to enroll without a grant — otherwise it could never turn 2FA on — but any later replacement or disable still needs proof; for that one case with no stronger factor available, its own current OTP code is accepted as the proof (`otp_only_grant`), never for `register`/`delete`. Every enable/replace/disable is audit-logged (`SSOAuditEventType.OTP_ENABLED`/`OTP_DISABLED`) and triggers a commit-deferred, failure-isolated notification email (`OtpEnabledEmail`/`OtpDisabledEmail`). Tests: `apps/users/tests/test_otp_management.py`, `test_schema.py::TestGenerateOTPMutation/TestVerifyOTPMutation/TestDisableOTPMutation`.

### E03 — Pending OTP proof survives credential changes

- Likelihood: Medium; impact: High. Type: incomplete credential revocation.
- Components: [OTP proof generation](packages/backend/apps/users/utils.py:88), [OTP login validation](packages/backend/apps/users/serializers.py:471).
- Pending proof is an `AccessToken()` carrying a user ID and expiration. The OTP validator checks signature/expiry and loads that ID, but does not compare a password fingerprint, account incarnation/security version, enabled factor version or active-account state.
- Conceptual risk: a still-valid pending proof plus a valid OTP can complete login after the owner has changed/reset the password. A recycled database user ID is also not bound to the original account, although completion still requires the new account's OTP.
- Evidence: after changing a password, the original pending proof completed validation and issued new tokens. An inactive account also received token strings; normal access authentication and refresh independently reject inactive accounts, so that observation alone is not a working inactive-account bypass.
- Fix: use a dedicated pending-login record/token bound to the current account security version, verified factor and first-factor authentication, invalidate it on relevant security changes, and recheck account state under the session-issuance transaction.
- Tests: password change/reset, inactive/delete/recreate, factor replacement, and state changes between validation and issuance.
- **Remediation implemented** (`apps/users/models.py::PendingOTPLogin`, `apps/users/services/otp_login.py`, `apps/users/serializers.py::ValidateOTPSerializer`): the self-signed JWT is replaced by a server-side, one-use `PendingOTPLogin` row (only its SHA-256 hash is stored), created by `begin_otp_login()` after a real password or completed-OAuth first factor and bound to a `credential_version` fingerprint (password hash + OTP enabled/verified/secret). An ordinary access/refresh token can no longer satisfy this step at all, since it can never hash-match a row only `begin_otp_login()` creates. Lookup rejects anything expired, already used, or whose `credential_version` no longer matches (password changed/reset, OTP enabled/disabled/replaced, account deactivated/reclaimed). Validation happens twice: once when the code is checked, and again — under a row lock, atomically with session issuance — immediately before tokens are minted, so a concurrent duplicate submission or a credential change in between cannot both succeed. Account reclaim (`account_reclaim.py`) additionally deletes any outstanding row explicitly. Tests: `apps/users/tests/test_serializers.py`, `test_account_reclaim.py::TestOutstandingProofsFailAfterReclaim`, `test_otp_management.py`.

### E04 — Passwordless accounts can gain passwords without fresh proof

- Likelihood: Medium; impact: High. Type: credential persistence through session compromise.
- Components: [password-change serializer](packages/backend/apps/users/serializers.py:183), [password-change mutation](packages/backend/apps/users/schema.py:417).
- When `has_usable_password()` is false, the serializer skips old-password verification without another identity proof. It then sets the password and issues a full authenticated token pair. Existing password changes verify the old password but do not require an enabled second factor or a dedicated fresh proof.
- Conceptual risk: a compromised social/passwordless session can install a persistent password. This is separate from normal password reset through an owned mailbox.
- Evidence: a passwordless account with OTP enabled accepted password creation without password, OTP or passkey reauthentication.
- Fix: require a fresh verified passkey, provider reauthentication or a verified recovery flow for first-time password creation. For password changes, enforce password plus enabled OTP or a deliberately approved equivalent proof, with action-bound grants and security notifications.
- Tests: passwordless/stale sessions, enabled/disabled OTP, valid alternatives, revoked pending proofs and password-change session handling.

### E05 — Password guessing is limited by IP rather than account

- Likelihood: Medium; impact: High. Type: credential stuffing/brute force.
- Components: [login mutation](packages/backend/apps/users/schema.py:77), [password-change mutation](packages/backend/apps/users/schema.py:423), [login serializer](packages/backend/apps/users/serializers.py:295).
- Password login has a hardcoded `30/min` IP limit. There is no account-wide failed-password counter/backoff. Password-change old-password guesses have no dedicated operation limit, beyond the global authenticated request throttle. The account-wide five-attempt/15-minute control applies to OTP, not passwords.
- Conceptual risk: distributed requests can repeatedly target the same password without consuming a shared failure budget. Accounts without MFA have the greatest exposure. Behind a proxy, the legacy helper can instead group users under the proxy address.
- Fix: layer atomic account and trusted-client-IP failure budgets, progressive cooldown and abuse monitoring. Keep public messages generic; avoid an easily triggered permanent account lockout. Cover password-change and other password checks with appropriately scoped controls.
- Tests: multiple IPs targeting one account, simultaneous guesses, successful-login reset policy, cooldown expiry, unknown emails and proxy identity handling.

### E06 — Inconsistent rate-limit enforcement

- Likelihood: Medium; impact: Medium. Type: throttling bypass/availability risk.
- Components: [global throttle IP helper](packages/backend/common/ratelimiting/utils.py:19), [legacy operation decorator](packages/backend/common/graphql/ratelimit.py:17), [legacy IP helper](packages/backend/common/utils.py:22).
- The global helper trusts the leftmost forwarded address and alternate proxy headers without the trusted-hop policy used by the passkey guard. Whether an external client can control these values in production depends on ingress sanitization. Separately, the legacy operation decorator catches non-rate-limit errors and allows the operation. Its IP helper uses `META['x-forwarded-for']`, unlike Django's conventional `HTTP_X_FORWARDED_FOR`, and normally falls back to the proxy's peer address.
- Evidence: helper probe accepted a supplied forwarded identity; decorator probe executed an operation when its limiter raised a cache error. This does not mean an outage of the shared global throttle also passes: its independent error behavior can still stop the HTTP request.
- Fix: consolidate on one trusted-hop IP resolver and atomic limiter. Authentication operation limits should fail closed with a retryable service error when they cannot enforce policy. Verify edge sanitization for VPS, AWS and Render.
- Tests: spoofed headers, real trusted proxy chains, concurrent counts, limiter outages and operation-count limits under GraphQL aliases.

### E07 — OTP purpose and replay controls are missing

- Likelihood: Medium; impact: Medium. Type: authentication-proof replay.
- Components: [OTP validator](packages/backend/apps/users/serializers.py:480), [TOTP verification](packages/backend/apps/users/services/otp.py:37).
- Any signed access token containing a matching user ID is accepted as pending OTP proof; no dedicated purpose claim is required. Pending proof is not consumed server-side. TOTP verification uses a one-step window but records no accepted timestep.
- Evidence: a regular access token was accepted as pending proof; the same pending proof and current OTP completed twice, producing distinct refresh tokens. Deleting the browser cookie after success does not prevent server-side replay.
- Fix: purpose-separate pending login proofs, bind them to browser/ceremony context, consume them once atomically with session issuance, and reject previously accepted TOTP timesteps under a row lock. Define concurrency UX for multiple tabs and management ceremonies.
- Tests: ordinary/foreign tokens, duplicate success including simultaneous submissions, cookie replay, adjacent-window codes and leading-zero handling. NIST recommends accepting each valid OTP only once.
- **Partially addressed locally, shipped with E02/E03**: purpose separation and ceremony binding of the pending login proof itself are solved as part of E03 above (`PendingOTPLogin` is only ever created by `begin_otp_login()`, so an ordinary token cannot stand in for it, and it is consumed exactly once atomically with session issuance). Separately, `User.otp_last_used_code_hash` (`apps/users/services/otp.py::_check_otp`) now rejects an exact-value replay of the most recently accepted code for every `validate_otp`/`verify_otp` call (login, setup confirmation, and the E02 fresh-auth grants), closing the demonstrated "same proof + same code twice" case. This is value-based, not timestep-based: a _different_ code that is still valid within the adjacent window is still accepted (simpler, and sufficient for the replay risk actually described, but weaker than strict monotonic-timestep rejection). Leading-zero handling and the account-wide rate limiting portions of this finding remain open.

### E08 — Password reset has a validation/use race

Recovery hardening now locks/reloads the account and rechecks the token before updating only the password
field and blacklisting outstanding tokens. This prevents stale prevalidated requests from overwriting a
support reclaim. The new regression is prepared but unexecuted at the user’s request; broader reset/session
revocation and concurrency validation remain part of the final verification work. The evidence below describes
the original audit behavior.

- Likelihood: Low; impact: High. Type: TOCTOU/token reuse.
- Components: [reset confirmation](packages/backend/apps/users/serializers.py:251).
- Validation loads the user and checks the token; `create()` later writes the password from that loaded instance without locking and rechecking. Ordinary sequential reuse is invalidated by the password hash, but two requests validated against the original state can both save.
- Evidence: two independently prevalidated serializers used the same reset token and both saved; the second password won. This is a reproduction of the race interleaving, not a threaded HTTP benchmark.
- Fix: lock/reload the user, validate the token against the current row, update credentials and revoke sessions/pending proofs in one transaction. Commit notifications after success.
- Tests: concurrent token use must produce one success; notification/storage failures must not leave partial state; normal sequential replay must remain rejected.

### E09 — Reset-email abuse controls

- Implemented, verification deferred: reset requests use the configured `auth.password_reset` rate (default five/IP/hour), trusted-proxy IP resolution, and atomic HMAC-keyed database recipient counters. A global row serializes budget admission across workers.
- Accepted behavior change: one email/address per five minutes, five/address per UTC day, and 500 newly queued reset emails/hour globally. Limits are configurable; retries do not consume additional admission budget. Known, unknown, inactive, throttled and limiter-failure requests retain the generic success result. Failed limit checks never bypass sending controls.
- Reset proofs expire after one hour, including previously issued proofs. Activation proofs retain their independent existing lifetime. Tokens are generated at outbox delivery, so the reset lifetime starts when the message is rendered.
- Added deferred tests: configured limits, recipient/case/IP boundaries, concurrent admission, suppression, unavailable limiter, and separate reset/activation expiry.

### E10 — Password policy and contextual validation

- Partially addressed, verification deferred. Signup uses prospective account email context; changes/resets use actual email and profile names. Reset proof validity is checked before contextual validation, then proof and validation are rechecked against the locked account before saving.
- Local blocklist: Django's dependency-versioned common-password corpus plus application-specific predictable choices. No password or hash prefix is sent to an external service. This is a finite blocklist, not an exhaustive breach-password database.
- Accepted product decision: minimum length remains eight characters, including password-only accounts. The recommended 15-character minimum is not adopted. Existing passwords continue to work; no forced resets or new composition requirements. Current trimming/Unicode behavior is retained.
- Added deferred tests: prospective email, profile names, reset validation ordering/recheck and accepted eight-character passwords. Existing frontend translations already cover these rejection codes.

### E11 — Authentication monitoring redaction

- Implemented, verification deferred: error/transaction/breadcrumb hooks sanitize nested and serialized data in backend and frontend. Credential-bearing URL segments/query values are filtered. Bodies, headers and GraphQL variables are discarded; OTP seeds, codes and provisioning material are explicitly sensitive. Default PII collection is disabled and stack locals remain disabled.
- Django/server log formatting and the X-Ray export emitter sanitize output. Unparseable trace documents are dropped without an unredacted fallback. Frontend nginx access logging omits query strings/referrers and replaces credential-bearing paths. Browser documents and supported response headers use `strict-origin`.
- Reset URL routes and refresh behavior remain unchanged; no browser token persistence or extra recovery screen is introduced. These controls govern future application exports. Historical monitoring data, external proxy logs and provider retention require separate operational review.
- Added deferred synthetic tests for structured/serialized bodies, URL tokens, cookies, OAuth codes, enrollment URLs, malformed documents, logging and tracing boundaries.

### E12 — Encrypted TOTP seed storage

- Implemented, verification deferred: versioned AES-256-GCM encrypts active and pending seeds with a dedicated key, binding ciphertext to numeric account identity and active/pending purpose. Plaintext seed and duplicate provisioning-URL columns are removed after conversion; enrollment URLs are derived only when needed.
- Existing seed values, counters/replay state and authenticator registrations are preserved. Credential-version fingerprints use decrypted seeds, so encryption/rotation alone does not invalidate pending proofs. Corrupted ciphertext never bypasses OTP. Secrets are excluded from exports, admin forms, GraphQL user fields and action logs.
- **REQUIRED BEFORE MERGING THIS BRANCH TO MASTER / VPS DEPLOYMENT:** configure a unique `OTP_ENCRYPTION_KEYS` value in the private VPS environment. API, migration, worker and Beat services all receive it. Generate a base64-encoded random 32-byte key and back it up separately from PostgreSQL. Never deploy the public test key or reuse another encryption key.
- VPS CI/CLI deployment now stops old backend/worker/Beat authentication writers before migration; Compose refuses a missing OTP key before starting deployment. Other deployments must also pause old authentication writers during migration. The conversion runs transactionally and has no plaintext reverse migration. Roll back through a coordinated application/database backup restore; do not deploy old code against the new schema. Existing plaintext backups, historical PostgreSQL pages and WAL remain sensitive; this conversion is not a secure erase of past storage.
- Rotation: prepend a new key to the comma-separated keyring, deploy to all services, run `python manage.py rotate_otp_keys`, then remove retired keys from the live keyring only after all rows have converted. Keep older keys offline for encrypted backup restoration. The command is resumable and reports counts only.
- A private development key was generated in the ignored backend `.env`; migration 0013 applied locally. Added deferred tests cover SQL at-rest values, conversion, account/purpose tampering, key rotation, proof stability, missing keys and disable cleanup. Deployed startup requires valid key configuration.

### E13 — Signup account enumeration

- Original evidence: the public duplicate-email validator returned an account-existence error.
- Status: **No action needed — accepted product decision.** The user requires successful signup to immediately authenticate a new, unverified account and enter the main panel. The check-email interstitial has been removed.
- Existing accounts are never overwritten or authenticated through signup. Duplicate-email validation remains, so signup can reveal account existence. Concealing this fully requires changing the onboarding behavior; no mitigation is claimed.
- Signup activation emails use the durable outbox. Successful signup is audited only after revocable session creation, in the same transaction. Rejected signup requests are audited separately.
- Verification deferred: automatic login, activation outbox, unchanged existing credentials and session-failure rollback tests are adjusted but not run.

### E14 — Published vulnerable social-auth dependency

- Original evidence: `social-auth-app-django==5.0.0` was within the affected range of CVE-2025-61783 (fixed in 5.6.0). Source: [maintainer advisory](https://github.com/python-social-auth/social-app-django/security/advisories/GHSA-wv4w-6qv2-qqfg).
- Implemented: project constraints and `uv.lock` now select `social-auth-app-django==6.1.0` and `social-auth-core==5.2.0`, with required cryptography, PyJWT, PyOpenSSL and requests updates. Django 5.2/Python 3.11 remain supported.
- Google initiation uses a top-level CSRF-protected POST, matching version 6’s POST-only authentication initiation. The custom begin view passes no ambient account to the provider flow. Existing callback state checks and explicit E01 linking remain; unused disconnect URLs remain unavailable.
- Verification deferred: provider signup/login, existing password accounts, explicit linking, OTP, cookie/session handling, redirects and legacy associations must pass against the upgraded packages before release. Include the upstream social-auth database migrations during deployment.

### E15 — Missing authentication security audit and alerts

- Implemented: account authentication events are persisted in the security audit store for signup, confirmation, password login, OTP challenges/checks/lockout, reset requests/completion, password changes and MFA enrollment/replacement/removal. Successful login is recorded only after session creation. Rejected operations are logged outside rolled-back mutation transactions; OTP failures share the committed attempt-counter transaction.
- Records contain server-generated correlation IDs, stable account/actor identifiers, controlled outcomes and authentication methods. Unknown submitted emails are HMAC identifiers. Raw user-agent strings are reduced to browser/OS/device categories. Passwords, OTP values/seeds, reset/activation tokens, cookies and request bodies are excluded.
- Audit and notification-outbox creation participate in credential-change transactions; storage failure rolls back the change. Alerts distinguish password changes/resets, MFA enablement, replacement and removal. Durable outbox rows hold no credential proofs; activation/reset tokens are generated only during delivery.
- Delivery: Celery Beat sweeps the outbox every 30 seconds; concurrent workers use row locks. Delivery retries exponentially up to eight attempts, with a one-hour maximum interval. Exhausted retries are visible in superuser-only read-only administration and sanitized logs. Deleted-account and stale-recipient messages are marked cancelled. SMTP delivery is at least once: a crash after SMTP acceptance but before the database commit can produce a duplicate email.
- Retention: the new `auth_*` audit family, email-outbox recipient data and signup cooldown rows expire after `AUTH_AUDIT_RETENTION_DAYS` (default 90), using bounded daily cleanup. Other tenant/SSO audit families keep their existing retention. Account deletion preserves audit identifiers while nulling the user FK. Outbox recipient addresses are retained until cleanup for delivery/accountability.
- IP attribution trusts `REMOTE_ADDR` unless its peer belongs to explicitly configured `AUTH_AUDIT_TRUSTED_PROXIES`; only then is the forwarded chain inspected from the trusted end. Configure only proxy networks that sanitize incoming forwarded headers.
- All new UI/email/event strings have translations in the eight supported locales, with a migration preserving administrator overrides.
- Verification deferred: outcome/attribution/redaction, rollback, deletion, retention, CSRF initiation, outbox retries/cancellation and notification regressions were added or adjusted. Tests, lint and type checks have not been run for these changes, at the user’s request.

## Controls already present

- Django salted password hashing; no plaintext-password persistence identified in the inspected login/reset path. The primary configured hasher is PBKDF2, not raw MD5/SHA1.
- Generic password-login failures; generic reset-request result.
- Signed, expiring access/refresh tokens; password-fingerprint checks reject ordinary access/refresh tokens after password changes and user-ID reuse.
- Browser credentials delivered through HttpOnly cookies, not public auth payloads or localStorage; secure-cookie production validation and API CSRF checks.
- Fail-closed tracked-session creation and atomic refresh/session-revocation linkage.
- OTP failures serialized per account: five failures trigger a 15-minute cooldown; minting another pending token does not reset it.
- Confirmation validates signed tokens even for already-confirmed accounts. Invitations require confirmed email ownership before acceptance, as covered by focused tests.

These controls do not negate the pending-OTP exception in E03 or the credential-management exceptions above.

## Additional policy choices and limitations

- Session revocation blocks refresh, but already-issued stateless access tokens remain usable until expiry (default five minutes). Decide whether immediate access revocation is required; then bind access tokens to server-checked session state. Logout also swallows blacklist/session-bookkeeping errors, so it may clear cookies without durable revocation when storage fails.
- Refresh extends expiry repeatedly; no absolute session age was identified. An absolute lifetime is a policy decision, not an automatic vulnerability finding.
- Unconfirmed users can log in and use an existing-session account. This can be an intentional onboarding design, but unverified identity must never become authority for third-party account linking or organization access.
- Reset/confirmation generators are custom subclasses. Password reset is tied to password state but omits the email address from its hash. If email changes are introduced, tokens must be invalidated on that change.
- No claim is made about absence of client-data leakage. Account takeover paths can expose whatever data the compromised account is legitimately permitted to access.

## Verification and recommended order

Temporary defensive probes cover OTP management, pending-proof freshness/purpose/replay, passwordless password creation, reset interleaving, rate-limit helpers/fail-open behavior, monitoring redaction and social-confirmation credential retention. Passing probes confirm existing insecure behavior; they are not security regression tests proving remediation.

**Result: 182 checks passed (13 audit probes and 169 existing tests), with 202 warnings, in the final isolated run.** Local evidence: `/private/tmp/klarvido-email-security-audit-final.log`; probes: `/private/tmp/klarvido_email_audit_tests.py`. The probes are temporary audit evidence and must be rewritten as rejection assertions when implementing fixes.

Existing targeted coverage was also checked for signup/login, reset/change, serializers, cookies, refresh/logout, account-bound tokens, OTP counters, CSRF, social confirmation and invitation ownership. The isolated database needed its expected `user` seed group restored after earlier transaction-test flushes; that fixture-only adjustment was not an application fix. No frontend lint/type-check was needed because application/frontend code was unchanged.

Recommended order: E01 and E02 first; E03/E07 as one pending-login redesign; E04; E05/E06/E09 as authentication-abuse hardening; E08; E11/E12; then E10/E14/E15. E13 is excluded from remediation by the accepted product decision. The dependency update should precede final validation of revised social-account linking.

Reference guidance: [OWASP authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html), [OWASP MFA](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html), [OWASP password reset](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html), [NIST authenticator guidance](https://pages.nist.gov/800-63-4/sp800-63b/authenticators/), [Python Social Auth linking guidance](https://python-social-auth.readthedocs.io/en/latest/use_cases.html#associate-users-by-email), [maintainer CVE-2025-61783 advisory](https://github.com/python-social-auth/social-app-django/security/advisories/GHSA-wv4w-6qv2-qqfg).
