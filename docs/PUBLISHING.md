# Publishing jacquard-kernel — the owner steps

Everything an agent can pave is paved (Phase 9, slice 26).
What remains genuinely needs the account owner: three
registries' first-contact steps and the anchor passphrase.
This document is the whole list, in order, with the exact
strings to paste into the exact fields. Nothing here is
urgent and nothing blocks on anything else; do the steps in
any order, but do step 0 before you forget where the interim
passphrase file is.

**How publishing works here.** Three GitHub Actions
workflows, all dispatch-only (no push or tag triggers — a
publish is always a deliberate dispatch):

| Registry | Workflow | Auth |
|---|---|---|
| PyPI | `Publish to PyPI` (`.github/workflows/publish-pypi.yml`) | Trusted Publishing (OIDC) — no token |
| crates.io | `Publish to crates.io` (`.github/workflows/publish-crate.yml`) | bootstrap token first, then Trusted Publishing |
| npm | `Publish to npm` (`.github/workflows/publish-npm.yml`) | granular token in a repo secret |

Every workflow takes two inputs: **ref** — the release tag
to build (the artifacts always come from the tagged tree,
never from a branch) — and **dry_run**, which defaults to
`true`: with it, the workflow builds from the tag, inspects
the artifacts, uploads them as run artifacts, and the
publish step is skipped entirely. A real publish is the
same dispatch with dry_run set to `false`. Dry runs for
v1.0.1 were executed and inspected on 2026-11-03 (run ids
in the builder's log); their artifacts match the local
1.0.1 builds file-for-file.

**In the GitHub dispatch panel** (Actions → workflow name →
Run workflow): the "Use workflow from" branch is `main`
(the workflows live there). The two inputs then appear as
"Git ref to build (a release tag)" and "Build and inspect
only; publish nothing". For a real publish of the current
release: ref `v1.0.1`, dry_run **false** (checkbox unticked).
For later releases, put that release's tag in the ref field.

---

## Step 0 — re-wrap the anchor keys with your own passphrase

The anchor keys on the Oracle (`~/.jacquard/`) are encrypted
with an interim passphrase that exists only in
`~/.jacquard/PHASE8-INTERIM-PASSPHRASE.txt` (mode 0600,
never committed, never printed). Replace it with yours:

On the Oracle, in a clone of this repo (e.g. `~/jacquard-p9`):

```bash
cd ~/jacquard-p9
PYTHONPATH=src python3 - <<'PY'
import getpass, os
from jacquard.anchor import load_private_key
from cryptography.hazmat.primitives import serialization

old = open(os.path.expanduser(
    "~/.jacquard/PHASE8-INTERIM-PASSPHRASE.txt")).read().strip()
new = getpass.getpass("new anchor passphrase: ")
assert new and getpass.getpass("repeat it: ") == new
for name in ("anchor-key.ed25519",
             "anchor-key-1.retired.ed25519"):
    p = os.path.expanduser("~/.jacquard/" + name)
    key = load_private_key(p, passphrase=old)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(new.encode()))
    tmp = p + ".new"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.write(fd, pem)
    os.close(fd)
    os.replace(tmp, p)
print("both keys re-wrapped")
PY
```

Verify before deleting anything — the derived public key
must match `pubkey.txt` in your jacquard-anchors clone:

```bash
JACQUARD_ANCHOR_PASSPHRASE='<your new passphrase>' \
  PYTHONPATH=src python3 tools/jqanchor.py pubkey
```

Only when that prints the anchors repo's public key, delete
the interim file:

```bash
rm ~/.jacquard/PHASE8-INTERIM-PASSPHRASE.txt
```

If the pubkey does not match, stop: the interim file is
still the only way in, and nothing above has harmed the
keys (a failed load writes nothing; the replace happens
only after a successful decrypt).

## Step 1 — PyPI (Trusted Publishing; no token anywhere)

1. pypi.org → sign in → your avatar → **Account settings**
   → **Publishing** → **Add a new pending publisher**.
2. Fill in exactly:

   | Field | Value |
   |---|---|
   | PyPI Project Name | `jacquard-kernel` |
   | Owner | `SuperInstance` |
   | Repository name | `jacquard` |
   | Workflow name | `publish-pypi.yml` |
   | Environment name | *(leave empty)* |

3. Dispatch **Publish to PyPI** as described above
   (ref `v1.0.1`, dry_run false). The run publishes
   `jacquard_kernel-1.0.1` (sdist + wheel) with no token —
   PyPI trusts the OIDC identity of this workflow in this
   repository because of step 2.

## Step 2 — crates.io (bootstrap token, then replace it with Trusted Publishing)

crates.io has no pending publishers: the first publish of a
new crate needs an API token. This is a one-time bridge.

**Phase A — bootstrap.**

1. crates.io → sign in → **Account Settings** → **API
   Tokens** → **New Token**: name `jacquard bootstrap`;
   scopes **`publish-new`** and **`publish-update`**;
   expiry: the shortest you are offered.
2. In this GitHub repository: **Settings → Secrets and
   variables → Actions → New repository secret**:
   Name `CARGO_REGISTRY_TOKEN`, Secret = the token.
3. Dispatch **Publish to crates.io** (ref `v1.0.1`,
   dry_run false). Note the workflow strips the repo's
   `publish = false` guard **in its own checkout only** —
   the repository keeps the guard, and the build step of
   every run asserts the guard is present in the tagged
   tree before anything publishes.

**Phase B — retire the token (do this right after A).**

4. crates.io → the `jacquard-kernel` crate page →
   **Settings → Trusted Publishing → Add a GitHub trusted
   publisher**: Repository owner `SuperInstance`,
   Repository `jacquard`, Workflow `publish-crate.yml`,
   Environment *(leave empty)*.
5. Delete the `CARGO_REGISTRY_TOKEN` repository secret
   (GitHub Settings → Secrets and variables → Actions) and
   revoke the `jacquard bootstrap` token on crates.io.
   From now on the workflow authenticates by OIDC when no
   secret is set; re-adding a secret would silently
   re-select the token path, so leave it deleted.

## Step 3 — npm (granular token)

1. npmjs.com → sign in → avatar → **Access Tokens** →
   **Generate New Token → Granular Access Token**:
   name `jacquard publish`; **Packages: All packages**
   (a package-scoped token cannot name `jacquard-kernel`
   before it exists — after the first publish you may
   replace this token with a package-scoped one if you
   prefer); Permissions **`Read and write`**; set an
   expiration you are comfortable with.
2. Repository secret: Name `NPM_TOKEN`, Secret = the token
   (same Settings path as step 2.2).
3. Dispatch **Publish to npm** (ref `v1.0.1`,
   dry_run false). The workflow runs the TypeScript
   conformance checker against the tagged tree before
   packing, and publishes `jacquard-kernel@1.0.1`
   (the 6-file tarball the dry run inspected).

## Step 4 — the shelf

List `jacquard-kernel` **1.0.1** on the curated shelf
(si-ready) by its usual intake. Evidence: tag `v1.0.1`,
`docs/release-readiness-1.0.md` (checklist + the v1.0.1
addendum), and this document.

---

*Safety shape, so the steps above can be done tired: a
dispatch with the default inputs publishes nothing; the
PyPI flow has no credential to mistype; the only two
secrets in the whole design are named exactly once each
(`CARGO_REGISTRY_TOKEN` — deleted again in phase B — and
`NPM_TOKEN`); and the crates.io guard line stays in the
repository, so even a mistaken local `cargo publish` from a
clone refuses.*
