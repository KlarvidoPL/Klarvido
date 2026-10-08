# Email/password authentication security review

Reviewed 2026-10-08 against master `a4690b1bd5c6bc5daa9ade6cd683b52e7883f647`.

This is a defensive source review with isolated Docker verification, not a production penetration test or a guarantee of complete security. The original audit did not modify application behavior. Findings distinguish reproduced behavior from code observations and deployment-dependent risks. E01, E02, E03 and the replay portion of E07 are addressed by the subsequent local implementation described below; E04–E06, E08–E15 and the remainder of E07 remain open.

## Scope and trust boundaries

Reviewed Django/DRF/Graphene registration, password login, email confirmation, password change/reset, TOTP enrollment/login/removal, JWT cookies, refresh/logout and tracked sessions; React authentication forms/routes and Sentry initialization; authentication-related settings, production proxy configuration and selected dependency versions. Social login was examined where it interacts with password-created accounts, not as a complete OAuth audit.

Principal boundaries: browser to GraphQL/REST; password verification to pending OTP login; pending OTP login to full session; existing session to credential changes; email delivery to reset/confirmation tokens; database/cache/proxy to authentication enforcement; application to monitoring providers.

No live customer accounts, production credentials, email delivery or production database were accessed. No comprehensive dependency scan, live proxy/header test, historical log inspection or full application authorization audit was performed.

## Prioritized findings

| ID  | Severity                             | Finding                                                                                                                      | Evidence                                                              |
| --- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| E01 | High — addressed locally             | Password-created accounts can be preregistered and later confirmed through social login while retaining attacker credentials | Source, state-transition probe and remediation regressions            |
| E02 | High — addressed locally             | 2FA removal/replacement requires no fresh authentication                                                                     | HTTP removal and service replacement probes; remediation regressions  |
| E03 | High — addressed locally             | Pending OTP login survives password changes and lacks account-state binding                                                  | Serializer probe; remediation regressions                             |
| E04 | High                                 | First password can be set on a passwordless account using only an existing session                                           | Serializer probe                                                      |
| E05 | High                                 | Password guessing has no account-wide failure budget                                                                         | Source                                                                |
| E06 | Medium                               | Rate-limit enforcement has inconsistent proxy trust and operation-level fail-open behavior                                   | Helper/decorator probes; proxy exposure conditional                   |
| E07 | Medium — partially addressed locally | OTP login proof lacks purpose separation and one-time consumption; TOTP codes are reusable                                   | Serializer/service probes; replay fix shipped with E02/E03, see below |
| E08 | Medium — partially addressed locally | Reset completion now locks/rechecks; broader reset/session recovery verification is deferred                                 | Original probe; new recovery-race regression prepared                 |
| E09 | Medium                               | Reset-email throttling does not implement the configured policy or recipient limits                                          | Source                                                                |
| E10 | Medium                               | Password validation is weaker than the recommended policy and omits user context                                             | Source                                                                |
| E11 | Medium                               | Monitoring does not comprehensively redact authentication URLs, serialized bodies or OTP secrets                             | Redaction probes; actual export conditional                           |
| E12 | Medium                               | TOTP secrets are stored in plaintext                                                                                         | Source                                                                |
| E13 | Medium                               | Signup reveals whether an email is registered                                                                                | Source and existing test expectation                                  |
| E14 | Medium                               | Authentication dependency is in a published vulnerable version range                                                         | Lockfile and maintainer advisory; exploitability conditional          |
| E15 | Low                                  | Email/password security events lack a durable audit trail and credential-change notifications                                | Source                                                                |

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

### E09 — Reset-email abuse controls are not wired to policy

- Likelihood: High; impact: Medium. Type: email flooding/resource abuse.
- Components: [reset mutation](packages/backend/apps/users/schema.py:165), [configured auth rates](packages/backend/config/settings.py:410), [reset email issuance](packages/backend/apps/users/serializers.py:227).
- Settings advertise `auth.password_reset=5/hour`, but the mutation uses legacy `ip_throttle_rate`, which returns `60/min`. No recipient/account cooldown exists. The response remains generic, which is good, but repeated requests can enqueue repeated emails for one account.
- Fix: apply the configured policy plus a normalized-recipient cooldown and global send budget, without disclosing account existence. Consider a shorter explicitly configured reset expiry; no override is present, so Django's default is three days.
- Tests: configured values actually alter behavior; distributed requests cannot flood one recipient; known/unknown accounts have equivalent public results; failed delivery does not expose account existence.

### E10 — Password policy and contextual validation

- Likelihood: Medium; impact: Medium. Type: weak credential policy.
- Components: [validators](packages/backend/config/settings.py:275), signup/change/reset password validators in [serializers](packages/backend/apps/users/serializers.py:88).
- Django's default minimum length is eight. All three serializer calls invoke `validate_password(password)` without `user`, so the configured user-attribute similarity validator cannot compare the password with the account's email/name. Frontend strength indicators are not server enforcement.
- Fix: adopt an explicit passphrase policy; NIST's current guidance uses at least 15 characters for password-only authentication and permits eight with mandatory MFA. Pass actual/prospective account context to validation, allow password-manager/autofill and sufficiently long passwords, and use an appropriate compromised-password blocklist. Avoid adding arbitrary complexity rules.
- Tests: email/name similarity, minimum policy by intended authentication mode, long/Unicode passwords, whitespace consistency, and equivalent signup/change/reset enforcement.

### E11 — Monitoring can retain authentication material

- Likelihood: Low; impact: High. Type: sensitive data exposure; deployment-dependent.
- Components: [backend monitoring](packages/backend/config/monitoring.py:10), [frontend monitoring](packages/webapp/src/app/providers/sentry.tsx:7), [reset route](packages/webapp/src/routes/auth/passwordReset/passwordResetConfirm/passwordResetConfirm.component.tsx:16).
- Backend filtering covers dictionary keys containing `token`, `password` or `secret`, but preserves serialized JSON strings and OTP keys such as `otpBase32`/`otpauth_url`. It does not scrub request URL paths. The reset route carries the reset token in its path; frontend Sentry has no application-specific URL/breadcrumb scrubber. Backend monitoring enables default PII collection.
- Evidence: redaction probes preserved serialized credential strings and a representative OTP-secret key. Source shows missing URL filtering. Actual exported events depend on Sentry enablement, SDK capture shape and server-side scrubbing; no live leak is asserted.
- Fix: scrub authentication URL segments, breadcrumbs, headers/cookies and structured or serialized request/response data before export. Explicitly include OTP enrollment material. Minimize PII; evaluate whether any auth bodies should be collected. Clear reset tokens from the browser address once safely captured and enforce a no-referrer policy on sensitive routes.
- Tests: synthetic frontend/backend events with reset URLs, raw JSON, GraphQL variables, OTP enrollment responses and cookies must contain no authentication material.

### E12 — Plaintext TOTP seed storage

- Likelihood: Low; impact: High. Type: secret disclosure at rest.
- Components: [user model](packages/backend/apps/users/models.py:62), [OTP setup](packages/backend/apps/users/services/otp.py:22).
- `otp_base32` and `otp_auth_url` store the same reusable OTP secret without field-level encryption. A database/backup disclosure can expose the possession factor. Passwords are hashed correctly; TOTP seeds cannot be hashed because verification needs the original seed.
- Fix: encrypt seeds using a separately managed application/KMS key with rotation/version support. Avoid duplicating the seed in a stored URL; derive enrollment URLs only when needed. Restrict exports, administrative access and logs.
- Tests: no plaintext seeds in database dumps/serialized output; migration of existing seeds; decrypt/verify after key rotation; fail safely without encryption configuration.

### E13 — Signup account enumeration

- Likelihood: High; impact: Medium. Type: account existence disclosure.
- Components: [signup email validation](packages/backend/apps/users/serializers.py:73).
- `UniqueValidator` returns a distinguishable duplicate-email error. Password reset already returns the same `ok` result for known and unknown addresses, but signup still allows address enumeration.
- Fix: design a consistent registration response and deliver the appropriate next step privately to the email owner. Preserve useful guidance through email rather than disclosing registered addresses publicly. Add recipient cooldowns to any such email flow.
- Tests: known/unknown registration responses and timing characteristics; no repeated-mail abuse; case-insensitive normalization.

### E14 — Published vulnerable social-auth dependency

- Likelihood: Low; impact: High; rated Medium because exploitability depends on provider behavior. Type: vulnerable authentication dependency.
- Components: [lockfile](packages/backend/uv.lock:3890), matching `~=5.0.0` requirement in backend project metadata.
- `social-auth-app-django` is locked to `5.0.0`. The maintainer advisory for CVE-2025-61783 covers versions before `5.6.0`: email association could happen even with that pipeline step omitted. Provider email verification/uniqueness affects exploitability. This application currently explicitly enables email association, so upgrading alone does not fix E01 or make its linking policy safe.
- Fix: update the constraint and lockfile to a supported patched release after compatibility review; run provider-flow, cookie, redirect, account-linking and disconnect regressions. Do not rely only on removing `associate_by_email` while retaining the old dependency.
- Tests: new and existing password accounts, explicit secure linking, disabled automatic linking, provider identity validation and legacy social associations. No external-provider exploit was attempted.

### E15 — Missing authentication security audit and alerts

- Likelihood: Medium; impact: Low. Type: detection/forensics gap.
- Components: users serializers/schema/OTP services.
- Session rows provide session tracking, not a durable record of failed password attempts, credential reset/change, MFA replacement/removal or their outcomes. These paths do not emit the structured security audit events used by passkey services, nor dedicated credential-change notifications.
- Fix: record success/failure security events with stable actor/account identifiers, trustworthy client context and correlation IDs; notify credential/factor changes. Define retention and privacy rules, and never record passwords, reset tokens, OTP values or seeds.
- Tests: events for actual outcomes only, correct actor attribution, secret exclusion and notification delivery after commit.

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

Recommended order: E01 and E02 first; E03/E07 as one pending-login redesign; E04; E05/E06/E09 as authentication-abuse hardening; E08; E11/E12; then E10/E13/E14/E15. The dependency update should precede final validation of revised social-account linking.

Reference guidance: [OWASP authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html), [OWASP MFA](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html), [OWASP password reset](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html), [NIST authenticator guidance](https://pages.nist.gov/800-63-4/sp800-63b/authenticators/), [Python Social Auth linking guidance](https://python-social-auth.readthedocs.io/en/latest/use_cases.html#associate-users-by-email), [maintainer CVE-2025-61783 advisory](https://github.com/python-social-auth/social-app-django/security/advisories/GHSA-wv4w-6qv2-qqfg).
