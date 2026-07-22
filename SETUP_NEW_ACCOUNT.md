# Runbook: Stand up the pipeline on a NEW GitHub account (Claude + ChatGPT access)

Goal: clone this whole render pipeline to a fresh GitHub account and have it fully
operational — renders firing, secrets in place, and BOTH Claude and ChatGPT able
to trigger renders — in ~20 minutes. Follow top to bottom.

Reference proof: prototype-video/Prototype-Video was built this way from
1974jwatson/TikTok-Video-Pipeline on 2026-07.

---

## 0. What you need before starting
- The **destination** GitHub account (logged in, in the browser).
- A **fine-grained PAT** on the destination account (see step 2 for exact scopes).
- The API keys (kept in a password manager, never in git):
  PEXELS_API_KEY, ELEVENLABS_API_KEY, and the YouTube trio
  YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN.

---

## 1. Create the empty destination repo
On the destination account: github.com/new → name it → **no README, no .gitignore,
no license** (must be empty) → Create.

---

## 2. Fine-grained PAT (destination account)
github.com/settings/personal-access-tokens/new
- Resource owner: the destination account
- Repository access: **Only select repositories** → the new repo
- Repository permissions — set ALL of these to **Read and write**:
  - **Contents**
  - **Actions**
  - **Workflows**
  - **Secrets**  ← (needed so Claude can install the API keys)
  - Metadata auto-selects (read)
- Generate, copy the `github_pat_...` value.

> Gotcha we hit: forgetting **Secrets: write** → HTTP 403 when installing keys.

---

## 3. Mirror the code (history + tags)
The repo is ~1,100 commits / 110 MB. A single `git push --mirror` can time out,
and — CRITICALLY — pushing old history to `main` re-triggers ancient workflows
that fire zombie renders. Push through a **staging branch** (which triggers
nothing), then fast-forward main once at the end.

```bash
git clone --mirror https://github.com/<SOURCE_OWNER>/<SOURCE_REPO>.git src.git
cd src.git
DEST="https://x-access-token:<DEST_PAT>@github.com/<DEST_OWNER>/<DEST_REPO>.git"

# push history in size-bounded chunks to a branch that triggers no workflows
# (checkpoint commits at ~25/50/75/90/100% keep each push under the timeout)
git push "$DEST" <checkpoint_sha>:refs/heads/staging   # repeat per checkpoint
git push "$DEST" main:refs/heads/staging               # tip onto staging
git push "$DEST" main:refs/heads/main                  # single ff to main
git push "$DEST" :refs/heads/staging                   # delete staging
git push "$DEST" 'refs/tags/*:refs/tags/*'             # all video-* release tags
```

> Gotcha we hit: pushing straight to main mid-history woke old `push:`-triggered
> workflows → dozens of zombie renders burning Actions minutes. Cancel any that
> start, and prefer the staging-branch route above. The tip's workflows are all
> `workflow_dispatch`/file-drop, so once main = tip, it's quiet.

---

## 4. Install the 5 Actions secrets (Claude does this via API)
Uses libsodium sealed-box encryption; keys never appear in logs. Requires the
PAT to have **Secrets: write** (step 2).

```python
# pip install pynacl --break-system-packages
import json, base64, urllib.request
from nacl import encoding, public
tok="<DEST_PAT>"; repo="<DEST_OWNER>/<DEST_REPO>"
def gh(p,data=None,m="GET"):
    r=urllib.request.Request(f"https://api.github.com{p}",
        data=json.dumps(data).encode() if data else None, method=m,
        headers={"Authorization":f"Bearer {tok}","Accept":"application/vnd.github+json"})
    b=urllib.request.urlopen(r,timeout=30).read(); return json.loads(b) if b else {}
key=gh(f"/repos/{repo}/actions/secrets/public-key")
box=public.SealedBox(public.PublicKey(key["key"].encode(),encoding.Base64Encoder()))
for name,val in {
  "PEXELS_API_KEY":"...","ELEVENLABS_API_KEY":"...",
  "YT_CLIENT_ID":"...","YT_CLIENT_SECRET":"...","YT_REFRESH_TOKEN":"..."}.items():
    sealed=base64.b64encode(box.encrypt(val.encode())).decode()
    gh(f"/repos/{repo}/actions/secrets/{name}",
       {"encrypted_value":sealed,"key_id":key["key_id"]},"PUT")
```
Verify: `GET /repos/<repo>/actions/secrets` should list all five names.

---

## 5. Enable Actions + sanity-check
On the new repo: **Actions** tab → "I understand… enable". Then dispatch one
render to confirm the toolchain + secrets work end to end:
`POST /repos/<repo>/actions/workflows/render.yml/dispatches`
body `{"ref":"main","inputs":{"slug":"the-loop","long_render":true}}` — watch it
go green and publish a `video-the-loop` release.

Optional: make the `tiktok-render` container package **public** (repo → Packages →
Package settings → visibility) to enable the fast `use_container` path.

---

## 6. Give CLAUDE access
Claude just needs the **destination PAT** (step 2) pasted into the chat once.
From then on Claude can clone, author scripts + hero art, dispatch renders,
install secrets, read logs, and pull finished releases. Nothing else to install.

---

## 7. Give CHATGPT access (two mechanisms)

### 7a. The file-drop trigger (already in the repo)
`.github/workflows/render-request.yml` fires the real `render.yml` whenever a file
`build/<slug>/render.request` is committed to main, then self-cleans. This is how
ChatGPT triggers renders — by committing a file (a code write it CAN do), never by
calling the Actions API (which it can't from Code Interpreter or its connector).

### 7b. Install the ChatGPT Codex Connector (one-time, in the browser)
In the browser signed into the **destination** account:
1. Open `https://github.com/apps/chatgpt-codex-connector/installations/select_target`
2. Choose the destination account → **Only select repositories** → the new repo.
3. Permissions shown will include read/write to actions, code, workflows — correct.
4. **Install & Authorize.**
5. GitHub throws a **sudo-mode "Confirm access"** screen → **Verify via email** →
   enter the code from the account's inbox (only the human can do this step).
6. It redirects to `chatgpt.com/...oauth/callback` = connection complete.
7. Repo visibility in ChatGPT can lag **~5 minutes**.

Confirm at `github.com/settings/installations` → "ChatGPT Codex Connector" listed.

> Then in ChatGPT: "In repo <owner>/<repo>, create file
> `build/<slug>/render.request` with contents `go` and commit to main." → render fires.

---

## 8. Division of labor (important)
- **Fire a render of an EXISTING video:** ChatGPT alone (file drop) or one tap in
  GitHub Actions / mobile.
- **Author a NEW video** (script.json + 6 hero_*_raw.jpg art files): let **Claude**
  do it — ChatGPT is weak at committing structured JSON + binary art correctly.
  Clean split: Claude builds the script + art, ChatGPT/you drop the request.

---

## 9. What travels vs. what doesn't
- Travels in git: all code, scripts, hero art, memory.json, taste.npz,
  published_videos.json, WHATS_WORKING.md, workflows, this runbook.
- Does NOT travel: Actions **secrets** (step 4), **releases**/finished mp4s
  (copy release-by-release if you want the archive), the **container package**
  (rebuild or make public), Actions **enablement** (one click), caches (rebuild).

---

## 10. Fast checklist
- [ ] Empty dest repo created
- [ ] Fine-grained PAT (Contents+Actions+Workflows+Secrets = write)
- [ ] Mirror pushed via staging branch; tags pushed; main = tip
- [ ] 5 secrets installed + verified
- [ ] Actions enabled; one test render green
- [ ] Claude has the PAT
- [ ] Codex Connector installed (email-verified) + file-drop tested
- [ ] (opt) container package public; (opt) release archive copied
