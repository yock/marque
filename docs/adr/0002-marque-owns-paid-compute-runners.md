# Marque owns paid-compute runners, Beam only

The commission's paid-compute cap had no mechanism behind it. Marque now runs suites on rented compute itself: a runner backend owns the whole lifecycle (create, upload the exact tree, run, tear down, account), and the project supplies only the environment and the suite command. We chose this over wrapping each project's own remote tool because only Marque's own code can guarantee the safeties against paying for idle or orphaned resources. Beam is the only backend: its model (a persistent image, ephemeral sandboxes with a provider-enforced hard lifetime, a CLI that holds its own credentials) is the shape we want. Spend is estimated from run times and published rates, and confirmed against provider-reported start times; Marque never reads the invoice.

## Considered Options

- **Hetzner Cloud.** Rejected for now. Its only way to stop billing is an API delete, so a box that must delete itself when the laptop is gone needs an API token on the box. That breaks the rule that no token enters Marque's context, arguments or files (#37).
- **Beam VMs.** Rejected in favour of sandboxes. A VM's TTL measures idle time and stops rather than deletes it, and detached jobs do not count as activity.
- **Beam's Python SDK.** Rejected in favour of the CLI. The SDK offers per-run CPU tier and TTL renewal, but the CLI keeps Marque's scripts on the standard library, behind an allowlist of commands that never print credentials.
