# Security

Please report vulnerabilities privately through GitHub: *Security → Report a vulnerability*,
not as a public issue.

Notes for operators:

- The service stores OpenTodo API tokens encrypted (Fernet) with `EINKAUF_SECRET`. Keep the key and
  the `data/` directory private; back up both.
- The service has no login of its own. Run it only on a trusted network or behind a VPN / reverse
  proxy with authentication (for example Tailscale).
- Webhook calls are verified with the HMAC signature of OpenTodo; set `EINKAUF_WEBHOOK_SECRET`.
