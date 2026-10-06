# Enterprise SSO and SCIM are disabled

SAML/OIDC login, metadata/callbacks, SCIM provisioning, discovery, connection/token
GraphQL operations, enterprise admin screens, SSO enforcement, the Manage SSO
permission, and SSO notifications are disconnected. SSO access and refresh JWTs
are rejected across HTTP and WebSocket authentication. No environment variable
can reactivate enterprise SSO.

Keep `apps.sso` installed. Its passkey, session/device, and audit infrastructure is
still used by supported authentication. Database rows, secrets, migrations, and
historical audit events are retained. Disabled permissions and notifications are
filtered even when their old rows or cached permissions exist.

Enterprise-only frontend files and tests end in `.disabled` so TypeScript,
GraphQL codegen, Jest, and pytest do not discover them. Mixed backend suites keep
shared security tests active; enterprise cases are retained beside them in
`.py.disabled` files. `test_disabled.py` verifies the shutdown boundary.

## Deployment

Deploy backend restrictions before or alongside the frontend, and restart API,
WebSocket, and Celery processes to drop existing connections and loaded receivers.
Previously signed-in SSO users must use supported login. Users without usable
credentials can use the existing password-reset flow.

## Future reactivation

Perform a security review before restoring routes, schema fields, admin and signal
registrations, permission visibility, enforcement, notifications, or JWT support.
Restore archived source/tests selectively, regenerate GraphQL schema/types, and
review provider configuration and stored tokens before enabling any connection.
Do not remove token rejection or restore enterprise tests independently of that
review. The feature documentation describes retained implementation, not current
availability.
