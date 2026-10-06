"""Create the multi-language test cases in TestRail (project 2 / suite 7).

The suite already has a top-level, empty `Language` section (id 47). This script
fills it with six sub-sections and the cases below, all derived from reading the
app rather than guessed:

    components/Organization/Modals/AddClientModal.js          client default language
    components/Branding/LanguageDropdown/{index,languages}.js  portal additional languages
    components/Branding/index.js, EditMenuLabelModal/          per-language branding
    components/Home/index.js, Home/LanguageChangeModal.js      per-language home content
    components/Session/WebcastManagement/CustomEvent/CustomEventLanguageECDN.js
    components/Session/WebcastManagement/LanguageECDN.js       session languages
    components/Publish/index.js                                per-language portal URLs

    python testrail_language_cases.py --dry-run     # print, send nothing
    python testrail_language_cases.py               # create sections + cases

Re-running is safe but not a true upsert: a sub-section whose name already exists
under `Language` is reused, and a case whose exact title already exists in that
sub-section is skipped. Nothing is ever edited or deleted.
"""

import argparse

from testrail_upload import call, load_credentials

PROJECT_ID = 2   # Connect Studio
SUITE_ID = 7     # Admin Panel
LANGUAGE_SECTION_ID = 47  # existing top-level 'Language' section

TEMPLATE_TEXT = 1   # 'Test Case (Text)' — what every other case in this suite uses
TYPE_FUNCTIONAL = 7
PRIORITY_MEDIUM = 2


def p(*paragraphs):
    """TestRail's text fields are HTML; the suite's existing cases use <p>."""
    return "".join("<p>{}</p>".format(text) for text in paragraphs)


# Preconditions shared by whole groups of cases.
PRE_CLIENT = p(
    "Logged in as an ADMIN / SUPER_ADMIN or organization admin.",
    "A client exists whose default language is a NON-English language "
    "(e.g. Italian), so that 'default' and 'English' can be told apart.",
)
PRE_PORTAL = PRE_CLIENT + p(
    "A portal exists on that client with at least two additional languages selected."
)

# (sub-section name, [case, ...]) — created in this order under 'Language'.
PLAN = [
    ("Client Default Language", [
        {
            "title": "Client language dropdown offers the full supported language list",
            "custom_preconds": p("On Organization > Client, the 'New Client' modal is open."),
            "custom_steps": p(
                "1. Open the 'Language' dropdown in the New Client modal.",
                "2. Read every option in the list.",
            ),
            "custom_expected": p(
                "The dropdown offers the 12 languages from DefaultLanguages: English, Spanish, "
                "German, Italian, French, Swedish, Danish, Finish, Portuguese, Japanese, "
                "Simplified Chinese, Traditional Chinese.",
                "Each label is title-cased and the control is single-select.",
            ),
        },
        {
            "title": "Client language is mandatory",
            "custom_preconds": p("The 'New Client' modal is open."),
            "custom_steps": p(
                "1. Type a client name but leave 'Language' empty.",
                "2. Click Save.",
            ),
            "custom_expected": p(
                "The client is not created and 'Language is required' is shown in red under the "
                "dropdown. Choosing a language clears the error immediately.",
            ),
        },
        {
            "title": "Create a client with a non-English default language",
            "custom_preconds": p("The 'New Client' modal is open."),
            "custom_steps": p(
                "1. Enter a unique client name.",
                "2. Select 'Italian' as the language.",
                "3. Click Save.",
            ),
            "custom_expected": p(
                "A success toast is shown, the modal closes and the client appears in the client "
                "table. The client is persisted with portalLanguage = 'it'.",
            ),
        },
        {
            "title": "Default-language scope note is shown on the client modal",
            "custom_preconds": p("The 'New Client' modal is open."),
            "custom_steps": p("1. Read the note under the Language dropdown."),
            "custom_expected": p(
                "The note states that the selected default language applies only to the portal, "
                "not to the admin page, and that all portal-creation menus remain in English.",
                "Selecting a non-English language must not translate any part of the admin UI.",
            ),
        },
        {
            "title": "Client default language cascades into a new portal",
            "custom_preconds": PRE_CLIENT,
            "custom_steps": p(
                "1. Start 'Create Portal' and select the organization and the Italian client.",
                "2. Look at the 'Default Language' field in the Portal Settings section.",
            ),
            "custom_expected": p(
                "'Default Language' is populated from the client (Italian) as soon as the client "
                "is chosen — it is fetched from the sub-organisation record, never typed by the "
                "user.",
            ),
        },
    ]),

    ("Portal Additional Languages", [
        {
            "title": "Portal Default Language field is read-only",
            "custom_preconds": PRE_CLIENT,
            "custom_steps": p(
                "1. Open a portal's Branding page.",
                "2. Try to type into and to clear the 'Default Language' field.",
            ),
            "custom_expected": p(
                "The field is disabled (cursor-not-allowed) and cannot be edited. It shows the "
                "client's language name, and the placeholder 'Default language is set from the "
                "selected client' while no client is chosen.",
            ),
        },
        {
            "title": "Additional Language dropdown excludes the default language",
            "custom_preconds": PRE_CLIENT,
            "custom_steps": p(
                "1. On Branding, open 'Select Additional Language'.",
                "2. Compare the options with the default language shown above it.",
            ),
            "custom_expected": p(
                "Every supported language is offered EXCEPT the client's default language, so the "
                "same language can never be counted twice.",
            ),
        },
        {
            "title": "Select multiple additional languages",
            "custom_preconds": PRE_CLIENT,
            "custom_steps": p(
                "1. Open 'Select Additional Language'.",
                "2. Select two or more languages (e.g. English and German).",
            ),
            "custom_expected": p(
                "The control is multi-select; each chosen language is rendered as a removable tag "
                "and stays selected when the dropdown is reopened.",
            ),
        },
        {
            "title": "Remove an additional language",
            "custom_preconds": PRE_PORTAL,
            "custom_steps": p(
                "1. On Branding, remove one language tag with its x.",
                "2. Save the portal and reopen Branding.",
            ),
            "custom_expected": p(
                "The removed language is gone from the tag list, and from every per-language "
                "selector on the portal (Home, menu labels, agenda, resources) after the save.",
            ),
        },
        {
            "title": "Additional languages persist after save and reload",
            "custom_preconds": PRE_CLIENT,
            "custom_steps": p(
                "1. Select two additional languages on Branding and save.",
                "2. Reload the Branding page.",
            ),
            "custom_expected": p(
                "Both languages are still selected — portalSelectedLanguages is persisted with "
                "the branding record and re-hydrated into the dropdown.",
            ),
        },
        {
            "title": "Unknown language search shows 'No Language Found'",
            "custom_preconds": PRE_CLIENT,
            "custom_steps": p(
                "1. Open 'Select Additional Language'.",
                "2. Type a language that is not supported (e.g. 'Klingon').",
            ),
            "custom_expected": p("The dropdown shows the empty state 'No Language Found'."),
        },
        {
            "title": "Additional languages appear in every per-language selector on the portal",
            "custom_preconds": PRE_PORTAL,
            "custom_steps": p(
                "1. Visit Home, Branding > Edit Menu Label, Agenda, an agenda point, and Resources.",
                "2. Open the 'Select Language' selector on each.",
            ),
            "custom_expected": p(
                "Each selector offers exactly [default language, ...additional languages] in that "
                "order and opens on the default language. With no additional languages selected, "
                "the selector is not rendered at all.",
            ),
        },
    ]),

    ("Per-Language Content", [
        {
            "title": "Home page content is stored per language",
            "custom_preconds": PRE_PORTAL,
            "custom_steps": p(
                "1. On Home, with the default language selected, set a distinct event name, "
                "subtitle and introduction, then Save.",
                "2. Switch 'Select Language' to an additional language.",
                "3. Enter different text in the same fields and Save.",
                "4. Switch back to the default language.",
            ),
            "custom_expected": p(
                "Each language keeps its own values (languageObjectList is keyed by language "
                "code); switching back shows the default-language text unchanged, not the "
                "translation.",
            ),
        },
        {
            "title": "Home language selector is locked until the default language is saved",
            "custom_preconds": PRE_PORTAL + p("The portal's Home page has never been saved."),
            "custom_steps": p(
                "1. Open Home on a freshly created portal.",
                "2. Try to use the 'Select Language' dropdown.",
                "3. Fill in the home page for the default language and Save.",
            ),
            "custom_expected": p(
                "Before the first save the dropdown is disabled and the warning 'Save the page "
                "for default language (&lt;CODE&gt;) first!' is shown. After saving the default "
                "language, the dropdown becomes usable and the warning disappears.",
            ),
        },
        {
            "title": "Switching language with unsaved changes — Save Changes",
            "custom_preconds": PRE_PORTAL,
            "custom_steps": p(
                "1. On Home, edit a field but do not save.",
                "2. Change 'Select Language'.",
                "3. On the Confirmation modal click 'Save Changes'.",
            ),
            "custom_expected": p(
                "The modal asks 'Do you want to save your changes before switching the language?'. "
                "'Save Changes' persists the edit against the ORIGINAL language and only then "
                "loads the newly selected language's content.",
            ),
        },
        {
            "title": "Switching language with unsaved changes — Cancel",
            "custom_preconds": PRE_PORTAL,
            "custom_steps": p(
                "1. On Home, edit a field but do not save.",
                "2. Change 'Select Language'.",
                "3. On the Confirmation modal click 'Cancel'.",
            ),
            "custom_expected": p(
                "The unsaved edit is discarded and the form loads the newly selected language's "
                "stored content. Reselecting the original language shows the pre-edit values.",
            ),
        },
        {
            "title": "Header menu logo can differ per language",
            "custom_preconds": PRE_PORTAL,
            "custom_steps": p(
                "1. On Branding, note the extra 'Select Language' dropdown beside the header menu "
                "logo dropzone.",
                "2. Upload and crop a logo for the default language, then switch language and "
                "upload a different logo.",
                "3. Save and revisit each language.",
            ),
            "custom_expected": p(
                "The per-language logo dropdown appears only when at least one additional "
                "language is selected, and each language keeps its own logo, file name and size.",
            ),
        },
        {
            "title": "Menu labels are saved per language",
            "custom_preconds": PRE_PORTAL,
            "custom_steps": p(
                "1. Open Branding > Edit Menu Label.",
                "2. With the default language selected, rename Homepage / Agenda / Session / "
                "Resource / Speaker / Video Library and save.",
                "3. Reopen the modal, switch to an additional language and enter different labels.",
            ),
            "custom_expected": p(
                "'Menu label edited successfully' is shown each time, and each tab entry keeps a "
                "separate value per language (languageValueMap keyed by language code). Switching "
                "language inside the modal reloads that language's labels.",
            ),
        },
        {
            "title": "Agenda and agenda points hold per-language content",
            "custom_preconds": PRE_PORTAL,
            "custom_steps": p(
                "1. Open Agenda > Edit Agenda, switch 'Select Language', enter a translated "
                "title/description and save.",
                "2. Repeat on an individual agenda point.",
            ),
            "custom_expected": p(
                "Both modals offer [default, ...additional] languages, and the fields that only "
                "apply to the default language stay editable only while the default language is "
                "selected.",
            ),
        },
        {
            "title": "Resources can be added per language",
            "custom_preconds": PRE_PORTAL,
            "custom_steps": p(
                "1. Open Resources > Add Resource.",
                "2. Choose an additional language in 'Select Language' and add a resource.",
                "3. Switch the language on the resource list.",
            ),
            "custom_expected": p(
                "The resource is stored against the selected language and listed under that "
                "language only; the default-language resource list is unaffected.",
            ),
        },
        {
            "title": "Speaker details can be entered per language",
            "custom_preconds": PRE_PORTAL,
            "custom_steps": p(
                "1. Open Speakers and edit a speaker.",
                "2. Switch 'Select Language', enter a translated biography/role and save.",
                "3. Switch back to the default language.",
            ),
            "custom_expected": p(
                "Each language keeps its own speaker text, while shared fields (photo, name) "
                "remain common to all languages.",
            ),
        },
    ]),

    ("Session Additional Languages", [
        {
            "title": "Session Default Language is shown checked and disabled",
            "custom_preconds": p("A session exists on a portal; its Language & eCDN tab is open."),
            "custom_steps": p("1. Look at the 'Default Language' row."),
            "custom_expected": p(
                "A single checkbox is rendered checked, disabled and dimmed, labelled with the "
                "session's default language name. It cannot be unchecked.",
            ),
        },
        {
            "title": "Session additional-language list excludes the session default",
            "custom_preconds": p("A session's Language & eCDN tab is open."),
            "custom_steps": p("1. Read every checkbox under 'Additional Languages'."),
            "custom_expected": p(
                "All supported languages are offered alphabetically EXCEPT the session's default "
                "language, which appears only in the disabled Default Language row above.",
            ),
        },
        {
            "title": "Add additional languages to a session and save",
            "custom_preconds": p("A session's Language & eCDN tab is open."),
            "custom_steps": p(
                "1. Tick two additional languages.",
                "2. Click Save.",
                "3. Navigate away and reopen the tab.",
            ),
            "custom_expected": p(
                "'Webcast Details updated successfully' is shown and both languages are still "
                "ticked after the reload (additionalLanguages persisted on the session).",
            ),
        },
        {
            "title": "Session languages drive the Content and Webcast Layout selectors",
            "custom_preconds": p("A session with at least one additional language."),
            "custom_steps": p(
                "1. Open the session's Content tab and its Webcast Layout tab.",
                "2. Open the 'Select Language' dropdown on each.",
            ),
            "custom_expected": p(
                "Each dropdown offers [session default, ...session additional languages]; it is "
                "hidden entirely when the session has no additional languages. Switching reloads "
                "that language's description, initial content and uploaded documents.",
            ),
        },
        {
            "title": "A session may use languages the portal does not list",
            "custom_preconds": PRE_PORTAL,
            "custom_steps": p(
                "1. Note the portal's additional languages on Branding.",
                "2. On a session under that portal, tick an additional language that is NOT in "
                "the portal's list and save.",
            ),
            "custom_expected": p(
                "The session accepts it — session additional languages are filtered only by the "
                "session's own default language, deliberately allowing extra languages per "
                "session on top of the portal's set.",
            ),
        },
        {
            "title": "Unticking a session language removes its per-language content selector",
            "custom_preconds": p(
                "A session with two additional languages and content saved against each."
            ),
            "custom_steps": p(
                "1. On Language & eCDN, untick one additional language and save.",
                "2. Reopen the Content tab.",
            ),
            "custom_expected": p(
                "The removed language is no longer offered in the language selector, and the "
                "remaining languages' content is untouched.",
            ),
        },
    ]),

    ("Publish & Portal URLs", [
        {
            "title": "Publish lists one portal URL per language",
            "custom_preconds": PRE_PORTAL,
            "custom_steps": p("1. Open the portal's Publish page."),
            "custom_expected": p(
                "One URL row is shown per language — the default language first, then each "
                "additional language, de-duplicated — each of the form "
                "&lt;publish-url&gt;/&lt;language-code&gt;/&lt;portalId&gt;, with the code shown "
                "in upper case beside it.",
            ),
        },
        {
            "title": "Each language URL opens the portal in that language",
            "custom_preconds": PRE_PORTAL,
            "custom_steps": p(
                "1. On Publish, open the default-language URL.",
                "2. Go back and open an additional-language URL.",
            ),
            "custom_expected": p(
                "Each opens in a new tab and renders the content saved for that language (home "
                "text, menu labels, logo). Untranslated fields fall back to blank/default rather "
                "than showing another language's text.",
            ),
        },
        {
            "title": "Copy button copies the correct per-language URL",
            "custom_preconds": PRE_PORTAL,
            "custom_steps": p(
                "1. Hover a language row on Publish and read the tooltip.",
                "2. Click the copy button and paste the clipboard contents.",
            ),
            "custom_expected": p(
                "The tooltip reads 'Copy &lt;CODE&gt; URL' and the pasted value is exactly that "
                "row's URL, not the default-language one.",
            ),
        },
        {
            "title": "Portal preview from the portal list uses the default language",
            "custom_preconds": PRE_PORTAL,
            "custom_steps": p("1. On the portal list, use the portal card's preview/open action."),
            "custom_expected": p(
                "The portal opens at /&lt;portalLanguage&gt;/&lt;portalId&gt;, falling back to "
                "'en' only when the portal has no language set.",
            ),
        },
    ]),

    ("Language — Known Defects & Risks", [
        {
            "title": "DEFECT: session step 1 saves language names while the edit screen expects codes",
            "custom_preconds": p("Creating a new session through the Schedule Webcast steps."),
            "custom_steps": p(
                "1. On step 1, tick 'German' under Additional Languages and complete the session.",
                "2. Open the created session's Language & eCDN tab.",
            ),
            "custom_expected": p(
                "EXPECTED: German is ticked.",
                "ACTUAL (risk): step 1 posts the language NAME ('German') while Language &amp; "
                "eCDN reads and writes the language CODE ('de'), so the selection does not "
                "round-trip. Source: SessionStreamStep1.js uses value={item.name}; LanguageECDN.js "
                "and CustomEventLanguageECDN.js use value={item.value}.",
            ),
        },
        {
            "title": "DEFECT: client and portal language lists are inconsistent",
            "custom_preconds": p("Any client and any portal."),
            "custom_steps": p(
                "1. Compare the client 'Language' dropdown with the portal 'Select Additional "
                "Language' dropdown.",
            ),
            "custom_expected": p(
                "EXPECTED: both offer the same supported languages.",
                "ACTUAL (risk): the client list offers Danish but not Turkish; the portal list "
                "offers Turkish but not Danish. A Danish client therefore has a default language "
                "that cannot be resolved to a name on the portal, and the read-only Default "
                "Language field renders empty.",
            ),
        },
        {
            "title": "Per-language selectors show language codes instead of language names",
            "custom_preconds": PRE_PORTAL,
            "custom_steps": p(
                "1. Open the 'Select Additional Language' dropdown on Branding and read the "
                "option labels.",
                "2. Open the 'Select Language' dropdown on Home, Edit Menu Label, Agenda, "
                "Resources and the per-language header-logo picker.",
            ),
            "custom_expected": p(
                "EXPECTED: language names are shown consistently everywhere.",
                "ACTUAL (risk): only the Branding additional-language dropdown maps codes to "
                "names; every other per-language selector is fed the raw code list, so users pick "
                "between 'it' and 'de' rather than 'Italian' and 'German'. 'zh_TW' is especially "
                "unreadable.",
            ),
        },
        {
            "title": "Legacy webcast Language & eCDN offers only a reduced language set",
            "custom_preconds": p("A legacy (non custom-event) webcast."),
            "custom_steps": p("1. Open its Language & eCDN tab and read the checkbox list."),
            "custom_expected": p(
                "Only German, Spanish, French, Italian, Japanese and Chinese are offered — the "
                "rest of languageArr is commented out. Confirm with product whether the legacy "
                "screen is meant to stay reduced while the custom-event screen offers all 12.",
            ),
        },
    ]),
]


def existing_sections(url, user, key):
    """{name: id} for the sub-sections already under 'Language'."""
    data = call(url, user, key, f"get_sections/{PROJECT_ID}&suite_id={SUITE_ID}")
    sections = data.get("sections", data) if isinstance(data, dict) else data
    return {s["name"]: s["id"] for s in sections if s.get("parent_id") == LANGUAGE_SECTION_ID}


def existing_titles(url, user, key, section_id):
    """Case titles already in one section — the duplicate guard."""
    data = call(
        url, user, key,
        f"get_cases/{PROJECT_ID}&suite_id={SUITE_ID}&section_id={section_id}",
    )
    cases = data.get("cases", data) if isinstance(data, dict) else data
    return {c["title"] for c in cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the sections and cases that would be created and send nothing.",
    )
    args = parser.parse_args()

    total = sum(len(cases) for _, cases in PLAN)
    print(f"Project {PROJECT_ID} / suite {SUITE_ID}, under section {LANGUAGE_SECTION_ID} 'Language'")
    print(f"{len(PLAN)} sub-section(s), {total} case(s)\n")
    for name, cases in PLAN:
        print(f"  {name}")
        for case in cases:
            print(f"    - {case['title']}")
    if args.dry_run:
        print("\n--dry-run: nothing was sent to TestRail.")
        return

    url, user, key = load_credentials()
    present = existing_sections(url, user, key)
    created = 0

    for name, cases in PLAN:
        section_id = present.get(name)
        if section_id:
            print(f"\nSection '{name}' already exists (id {section_id}) — reusing.")
        else:
            section = call(url, user, key, f"add_section/{PROJECT_ID}", {
                "suite_id": SUITE_ID,
                "parent_id": LANGUAGE_SECTION_ID,
                "name": name,
            })
            section_id = section["id"]
            print(f"\nCreated section '{name}' (id {section_id})")

        already = existing_titles(url, user, key, section_id)
        for case in cases:
            if case["title"] in already:
                print(f"  skip (exists): {case['title']}")
                continue
            payload = {
                "template_id": TEMPLATE_TEXT,
                "type_id": TYPE_FUNCTIONAL,
                "priority_id": PRIORITY_MEDIUM,
                **case,
            }
            result = call(url, user, key, f"add_case/{section_id}", payload)
            created += 1
            print(f"  C{result['id']}  {case['title']}")

    print(f"\nCreated {created} case(s).")


if __name__ == "__main__":
    main()
