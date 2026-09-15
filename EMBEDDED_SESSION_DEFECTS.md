# Embedded sessions — open defects

Findings from automating the embedded-sessions feature (PR #942) with
`03_embedded_test.py`. Environment: **dev**
(`connectstudio-admin-dev.world-television.com`), verified 14 Sep 2026.

TestRail: project 2 (Connect Studio), suite 7 (Admin Panel), section
**Embedded Session**. Latest run: [run 14](https://ferdus.testrail.io/index.php?/runs/view/14)
— 40 passed, 1 failed, 3 blocked.

---

## 1. Session creation fails with HTTP 500 — Kollective stream generation

**TestRail case:** 584 — *Check an embedded session is always Video only*
**Status:** reproducible in organisation `619641a3…`; passes elsewhere
**Severity:** blocks creating any session under the affected organization

### What happens

Completing the Schedule Webcast wizard in embedded mode does nothing: the modal
closes, no session appears, and no error is shown. The POST behind it fails:

```
POST https://api-dev.world-television.com/session_management/api/v1
     /org/619641a37c828e03b362ec17
     /client/6aa7c6c1b8996777fdd48abf
     /portal/6aa7c6c14c54712d0987819a
     /session/create

HTTP 500 · content-type: application/json
"Kollective stream generation failed, session creation failed"
```

### Root cause

Kollective is an **organisation-level** setting, not a portal or session one —
`components/Organization/Modals/AddOrganizationModal.js:40-48` defines
`enableKollective` with `tenantId` / `tokenId` required when it is on. Session
creation generates a Kollective stream, and that generation fails for the
organisation **ConnectStudio CORPORATE One** (`619641a37c828e03b362ec17`).

**This is organisation configuration — not a defect in the embedded feature and
not a defect in newly provisioned portals.** The embedded client created by the
suite only landed in this organisation because the suite defaults to the first
organisation in the list when `--embed-org` is not given.

### Evidence

Two experiments isolate it. Both drive the identical embedded wizard:

| # | Logo attached | Portal / organisation | Result |
|---|---------------|-----------------------|--------|
| 1 | no  | `68dbad0d…` in org `689486e0…` | **HTTP 200 — session created** |
| 2 | yes | `6aa7c6c1…` in org `619641a3…` | **HTTP 500 — nothing created** |

* Experiment 1 rules out "embedded session creation is broken" and "the missing
  logo is the cause" — the same wizard with no logo succeeds elsewhere.
  (The wizard has no client-side validation on step 1, so the logo is optional.)
* Experiment 2 rules out "attaching a logo fixes it".

### Confirmed

Settled by re-running the suite with the embedded client created in
`689486e0…` (the organisation that owns TARGET_PORTAL) instead of the first
organisation on the list: **case 584 passes**. A freshly provisioned embedded
portal accepts session creation normally, so nothing about new portals or about
embedded mode is at fault — only the Kollective configuration of organisation
`619641a3…` (ConnectStudio CORPORATE One).

The suite now derives its organisation from the portal named by TARGET_PORTAL
(`test_02_resolve_target_organization`) rather than taking whichever
organisation sorts first, so it no longer lands in a misconfigured one by
accident.

### Suggested owner

Backend / environment configuration: the Kollective tenant credentials for
`ConnectStudio CORPORATE One`.

---

## 2. The create error is swallowed — the user sees nothing

**TestRail case:** none yet — worth raising separately from #1
**Severity:** hides every current and future failure of this call

`components/Session/Modal/SessionsModal.js:159-168`:

```js
await requestApi.post(`${EnvVariable.CUSTOM_SESSION_MANAGEMENT}/org/.../session/${...}`, finalFormData)
    .then(async (res) => {
        if (res) {
            refetchList();
            SwalToasterConnectStudio.fire({ text: 'Live Session Created Successfully' })
        }
    }).catch((err) => err)      // <-- the 500 and its message are discarded
setSpinner(false)
toggleModal()
```

The backend returned an actionable message
(`"Kollective stream generation failed, session creation failed"`). The user is
shown nothing at all: the spinner stops, the modal closes, the list is empty.

This is independent of defect #1. Even once the Kollective configuration is
fixed, any later failure of this call stays invisible. The success branch also
only fires `if (res)`, so a falsy-but-resolved response is silent too.

**Suggested fix:** surface the server message through `SwalToasterError`, the
way the surrounding `catch (error)` block already does for thrown errors.

---

## 3. PR #942 broke the non-embedded session suite's locator (fixed)

**Status:** fixed in this repo — recorded because the cause is worth knowing.

`session_test.py::test_03_create_all_webcasts` stopped being able to open the
new-webcast wizard. `locators.py` matched the schedule tile on an **exact** class
string:

```
locator was:  //div[@class='stream-modal-container h-full']
app renders:  className='h-full stream-modal-container'
```

PR #942 reordered those two classes in
`components/Session/Modal/SessionsModal.js:247`, so the exact match silently
stopped matching and the wizard never opened. Nothing about the app is broken —
the tile works by hand — but an exact `@class=` match is brittle against any
class reordering.

Fixed by anchoring on the tile's label instead, and excluding the
`stream-modal-container-root` wrapper (which carries no `onClick`):

```python
NEW_WEBCAST_MODAL_BTN = (
    "//div[contains(@class,'stream-modal-container')"
    " and not(contains(@class,'stream-modal-container-root'))]"
    "[.//p[normalize-space()='Create New Webcast']]"
)
```

After the fix `session_test.py` is green again: 4 passed, all five webcast types
created.

---

## 4. Dev is ahead of the `develop` checkout

Not defects, but the local repo at `8a361099` (merge of PR #942) does not match
what dev serves, which made two TestRail cases inaccurate until corrected:

| Observed on dev | In the checkout | TestRail |
|-----------------|-----------------|----------|
| The modal is titled **Embed Code** | `EmbedSessionModal.js` renders "Embed Session" | cases 587 and 617 updated |
| Manage has a 5th **Embed Code** tab, rendering the builder inline | no such tab exists | case 586 updated; case 882 added |

Pull `develop` before reading that code again.

---

## Blocked cases in the latest run

Not failures — these did not execute:

| Case | Why |
|------|-----|
| 571, 572 | The `Automated Embedded` / `Automated Plain` clients already existed, so the suite reused them instead of re-exercising creation. Delete both to verify that path. |
| 611 | `navigator.clipboard` never settles while the browser window is unfocused, so neither toast branch fires. Run with the window in the foreground. |
