# Security boundaries and reporting

NEXUS Seed is a local research prototype, not a hardened multi-user service.
Bind only to loopback. Do not expose the Lab through a public reverse proxy or
enable remote access without a separately reviewed authentication/deployment design.

The authored language is a typed, bounded object-world interpreter. It must not
become arbitrary Python, shell commands, file tools, research authorization or
permission changes. Keep the existing Host/Origin/header checks and body bounds.

Private sessions may contain personal examples. Keep them under ignored local
directories; do not attach them publicly. Hash chains detect accidental changes
and stale references, not a malicious local owner replacing every file. Request
cancellation is cooperative, not operating-system sandbox isolation.

For a suspected vulnerability, do not post secrets or exploit details in a public
issue. Use the owner's established private contact channel. If none is available,
request a private reporting channel without disclosing the vulnerability. This
repository does not promise a staffed security team, response SLA, or bug bounty.

Do not change account/repository security settings, install external services or
spend money as part of reporting or verification. Reproduce issues only in a
local authored fixture, with permission and explicit bounds.
