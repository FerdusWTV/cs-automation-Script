"""Create the attendee-portal language test cases in TestRail (project 2 / suite 8).

Suite 8 'Portal Panel' already has a `Localization` section (id 153) holding the
broad cases C421-C428. This script adds six sub-sections beneath it with the
mechanics those cases do not reach, all read out of the portal app
(`C:\\Users\\User\\wtv.sharestudio-portal`) rather than guessed:

    next-i18next.config.js                       the 12 locales + defaultLocale
    custom/guards/helpers/localeUtils.js         first-visit redirect, locale cookie
    custom/hooks/useLocale.js                    locale switching
    components/.../LanguageFloatBtn/             the selector and the flag button
    components/.../MainContainer/TopBar/         per-locale menu labels and logo
    components/.../Common/FlowPlayerSession/     in-player stream language
    public/locales/<locale>/common.json          the translated UI strings

It deliberately does NOT restate C421-C428; where a new case touches the same
screen it tests a different, code-specific rule.

    python testrail_portal_language_cases.py --dry-run     # print, send nothing
    python testrail_portal_language_cases.py               # create sections + cases

Re-running reuses a sub-section whose name already exists and skips a case whose
exact title already exists in it. Nothing is ever edited or deleted.
"""

import argparse

from testrail_upload import call, load_credentials

PROJECT_ID = 2   # Connect Studio
SUITE_ID = 8     # Portal Panel
PARENT_SECTION_ID = 153  # existing 'Localization' section

TEMPLATE_TEXT = 1
TYPE_FUNCTIONAL = 7
PRIORITY_MEDIUM = 2


def p(*paragraphs):
    """TestRail's text fields are HTML; the suite's existing cases use <p>."""
    return "".join("<p>{}</p>".format(text) for text in paragraphs)


# The portal serves 12 locales, default 'en' (next-i18next.config.js). Note the
# set matches the ADMIN portal dropdown (Turkish, no Danish) and not the admin
# CLIENT dropdown (Danish, no Turkish) — see the Known Defects section.
PRE_MULTI = p(
    "A published portal whose branding has a default language and at least two "
    "additional languages (e.g. default Italian, additional English + German).",
    "The attendee is a fresh browser profile unless the case says otherwise — the "
    "first-visit locale redirect only fires while the portal's locale cookie is unset.",
)

PLAN = [
    ("Locale Routing & Persistence", [
        {
            "title": "Every published per-language URL opens the portal in that language",
            "custom_preconds": PRE_MULTI + p(
                "The per-language URLs are taken from the admin Publish page."
            ),
            "custom_steps": p(
                "1. Open the default-language URL /&lt;code&gt;/&lt;portalID&gt;.",
                "2. Open each additional-language URL in turn.",
            ),
            "custom_expected": p(
                "Each URL renders the portal with that locale active: the locale prefix stays in "
                "the address bar, the UI strings are that language's, and the language selector "
                "shows it as the current choice.",
            ),
        },
        {
            "title": "The English URL published by the admin resolves",
            "custom_preconds": PRE_MULTI + p("English is one of the portal's languages."),
            "custom_steps": p(
                "1. Open /en/&lt;portalID&gt; exactly as the admin Publish page prints it.",
            ),
            "custom_expected": p(
                "The portal opens in English. 'en' is the default locale and the portal's own "
                "internal links build unprefixed paths for it, so confirm the prefixed form is "
                "still served (not a 404) and that any redirect to the unprefixed URL keeps the "
                "portal and the page intact.",
            ),
        },
        {
            "title": "First visit with a locale the portal does not offer redirects to the branding language",
            "custom_preconds": PRE_MULTI + p(
                "Clear cookies for the portal so &lt;portalID&gt;__locale_set is unset."
            ),
            "custom_steps": p(
                "1. Open /fr/&lt;portalID&gt; for a portal on which French is NOT enabled.",
            ),
            "custom_expected": p(
                "A 302 redirects to the same path under the branding default language, and the "
                "page renders in that language. A locale the portal DOES offer is never "
                "redirected away.",
            ),
        },
        {
            "title": "The locale redirect only fires on the first visit",
            "custom_preconds": PRE_MULTI,
            "custom_steps": p(
                "1. Open the portal once so the &lt;portalID&gt;__locale_set cookie is written.",
                "2. Switch to an additional language.",
                "3. Reload the page, then close and reopen the tab.",
            ),
            "custom_expected": p(
                "The cookie is set with Path=/ and a 30-day max-age on the first visit. Afterwards "
                "the attendee stays on whichever locale they chose — no reload bounces them back "
                "to the branding default.",
            ),
        },
        {
            "title": "Switching language keeps the attendee on the same page",
            "custom_preconds": PRE_MULTI,
            "custom_steps": p(
                "1. Navigate to an inner page (Agenda, Resources or a session).",
                "2. Switch the language from the selector.",
            ),
            "custom_expected": p(
                "The same page reloads under the new locale prefix — the attendee is not sent back "
                "to home — and scroll position/route parameters (session id, custom page id) are "
                "preserved.",
            ),
        },
        {
            "title": "The locale prefix survives top-bar navigation and deep links",
            "custom_preconds": PRE_MULTI,
            "custom_steps": p(
                "1. Switch to a secondary language.",
                "2. Walk the whole top bar: Home, Sessions, Agenda &amp; Speakers, Resources, "
                "Video Library, any custom page.",
                "3. Copy an inner-page URL and open it in a new tab.",
            ),
            "custom_expected": p(
                "Every link keeps the locale prefix, including the logo link back to home, and "
                "the pasted deep link opens directly in that language with no redirect.",
            ),
        },
        {
            "title": "The attendee's language preference is remembered in local storage",
            "custom_preconds": PRE_MULTI,
            "custom_steps": p(
                "1. Open the portal for the first time and read localStorage 'defaultLanguage'.",
                "2. Switch to another language and read it again.",
            ),
            "custom_expected": p(
                "'defaultLanguage' is written once on the first visit, only for portals that "
                "actually have additional languages, and an existing value is never overwritten. "
                "Confirm with product whether a later switch is meant to update it — today it "
                "does not, so the stored value can disagree with the active locale.",
            ),
        },
        {
            "title": "Locale is preserved through login, registration and portal-status redirects",
            "custom_preconds": PRE_MULTI + p("The portal requires login or registration."),
            "custom_steps": p(
                "1. Open a protected page under a secondary locale while signed out.",
                "2. Complete the login / registration you are redirected to.",
            ),
            "custom_expected": p(
                "Each guard redirect keeps the locale prefix, the auth screens render in that "
                "language, and after signing in the attendee lands on the originally requested "
                "page still in that language.",
            ),
        },
    ]),

    ("Language Selector", [
        {
            "title": "The selector is hidden when the portal has only one language",
            "custom_preconds": p("A portal with a default language and NO additional languages."),
            "custom_steps": p("1. Open the portal and inspect the top bar."),
            "custom_expected": p(
                "No language selector is rendered at all (not an empty or single-option "
                "dropdown), and nothing is written to localStorage 'defaultLanguage'.",
            ),
        },
        {
            "title": "Selector options are labelled in their own language",
            "custom_preconds": PRE_MULTI + p(
                "Enable a spread of languages: Spanish, German, Simplified and Traditional Chinese."
            ),
            "custom_steps": p("1. Open the language selector and read every option."),
            "custom_expected": p(
                "Each option carries its endonym — English, Español, Deutsch, Italiano, Français, "
                "Svenska, Türkçe, Suomi, Português, 简体中文, 繁體中文 — not an English name and "
                "not a bare language code.",
            ),
        },
        {
            "title": "The selector lists the portal's default language plus its additional ones",
            "custom_preconds": PRE_MULTI,
            "custom_steps": p(
                "1. Compare the selector options with the portal's branding in the admin.",
            ),
            "custom_expected": p(
                "The list is exactly [default language, ...additional languages], de-duplicated "
                "and with the default first. A language the admin did not enable is never offered.",
            ),
        },
        {
            "title": "DEFECT: Japanese is labelled 'NO CAPTIONS' in the language selector",
            "custom_preconds": p("A portal with Japanese enabled as an additional language."),
            "custom_steps": p("1. Open the language selector and find the Japanese option."),
            "custom_expected": p(
                "EXPECTED: the option reads 日本語.",
                "ACTUAL: LANGUAGE_LABELS maps ja to the placeholder 'NO CAPTIONS' "
                "(LanguageSelectOption.js), so attendees see 'NO CAPTIONS' where the language name "
                "belongs. The same map feeds the in-player language dropdown.",
            ),
        },
        {
            "title": "RISK: the floating language button offers every locale, not the portal's",
            "custom_preconds": PRE_MULTI + p("On a theme that renders the floating language button."),
            "custom_steps": p(
                "1. Click the floating language button.",
                "2. Compare the flags offered with the top-bar selector's options.",
            ),
            "custom_expected": p(
                "EXPECTED: both offer the same, portal-enabled languages.",
                "ACTUAL (risk): LanguageFloatBtn iterates the router's full locale list, so it "
                "offers all 12 locales regardless of branding — choosing one the portal does not "
                "support lands the attendee on untranslated content. Also confirm a flag icon "
                "exists at /icons/languages/&lt;locale&gt;.svg for every locale offered, "
                "including zh_TW.",
            ),
        },
    ]),

    ("Translated UI Strings", [
        {
            "title": "Static UI strings come from the locale's translation bundle",
            "custom_preconds": PRE_MULTI,
            "custom_steps": p(
                "1. Switch to each enabled language.",
                "2. Check the fixed chrome: top-bar defaults, Help, login/registration labels, "
                "buttons and validation messages.",
            ),
            "custom_expected": p(
                "Every string is served from public/locales/&lt;locale&gt;/common.json. No raw "
                "translation key (e.g. 'topBar.Home') is ever visible on screen.",
            ),
        },
        {
            "title": "A missing translation key falls back to English",
            "custom_preconds": PRE_MULTI,
            "custom_steps": p(
                "1. Switch to a locale whose bundle is missing keys (Finnish, Japanese, "
                "Portuguese or Swedish).",
                "2. Visit the screens that use those keys.",
            ),
            "custom_expected": p(
                "i18next's fallbackLng of 'en' supplies the English string. Nothing renders blank "
                "and no key name leaks into the UI.",
            ),
        },
        {
            "title": "Translation bundles are complete for every offered locale",
            "custom_preconds": p("Repository check against public/locales/, no portal required."),
            "custom_steps": p(
                "1. Flatten each locale's common.json and compare it with the English bundle.",
                "2. Count missing keys and values still identical to the English text.",
            ),
            "custom_expected": p(
                "EXPECTED: each locale has all 113 keys translated.",
                "ACTUAL at time of writing — de 6 missing / 16 untranslated, es 2 / 9, "
                "fi 19 / 81, fr 5 / 16, it 6 / 12, ja 24 / 78, pt 24 / 78, sv 24 / 78, "
                "tr 14 / 8, zh 6 / 12, zh_TW 10 / 9.",
                "Finnish, Japanese, Portuguese and Swedish are effectively English portals: "
                "roughly 70% of their strings are the untranslated English source. Treat this as "
                "a content gap to be signed off before those languages are offered to clients.",
            ),
        },
    ]),

    ("Per-Language Portal Content", [
        {
            "title": "Top-bar menu labels use the admin's per-language labels with a translated fallback",
            "custom_preconds": PRE_MULTI + p(
                "In the admin, Edit Menu Label has custom labels for the default language only."
            ),
            "custom_steps": p(
                "1. Open the portal in the default language and read the top bar.",
                "2. Switch to a language that has no custom labels.",
            ),
            "custom_expected": p(
                "The default language shows the admin's custom labels. The other language falls "
                "back to the translated built-in labels from common.json — never to the other "
                "language's custom text, and never blank.",
            ),
        },
        {
            "title": "Agenda and speaker entries show their per-language titles",
            "custom_preconds": PRE_MULTI + p("Agenda items translated for one additional language."),
            "custom_steps": p(
                "1. Open Agenda / Agenda &amp; Speakers in the default language.",
                "2. Switch to the translated language, then to an untranslated one.",
            ),
            "custom_expected": p(
                "Translated entries show their own title for the active locale; an entry with no "
                "translation for that locale falls back to the default-language title rather than "
                "disappearing from the agenda.",
            ),
        },
        {
            "title": "Home page media falls back to the default language's image",
            "custom_preconds": PRE_MULTI + p(
                "The home page has an image for the default language only."
            ),
            "custom_steps": p(
                "1. Open home in the default language.",
                "2. Switch to an additional language.",
            ),
            "custom_expected": p(
                "The default-language image is reused when the active language has none, so home "
                "never renders a broken or empty image slot.",
            ),
        },
        {
            "title": "Home text with no translation must not render blank",
            "custom_preconds": PRE_MULTI + p(
                "An additional language whose home fields were never filled in the admin."
            ),
            "custom_steps": p(
                "1. Switch the portal to that language and read the event title, subtitle, "
                "introduction and home button.",
            ),
            "custom_expected": p(
                "Per C425 the default-language value should be shown. RISK: the admin stores an "
                "untranslated field as an empty string rather than leaving it unset, so the portal "
                "can render an empty title/subtitle instead of falling back. Confirm the intended "
                "behaviour and that the portal never shows a blank hero.",
            ),
        },
        {
            "title": "Registration custom fields follow the active language",
            "custom_preconds": PRE_MULTI + p(
                "Custom registration fields are configured for one language only."
            ),
            "custom_steps": p(
                "1. Open registration in the language that has custom fields.",
                "2. Switch to a language that has none and submit a registration.",
            ),
            "custom_expected": p(
                "First name, last name and email are always present; the custom fields shown are "
                "those configured for the active locale, and a locale with none shows just the "
                "core fields. The registration request carries language=&lt;active locale&gt;.",
            ),
        },
        {
            "title": "Resources and the video library list only the active language's items",
            "custom_preconds": PRE_MULTI + p(
                "Resources uploaded against different languages in the admin."
            ),
            "custom_steps": p(
                "1. Open Resources and the Video Library in the default language.",
                "2. Switch to an additional language.",
            ),
            "custom_expected": p(
                "Each language shows the items filed against it. An empty list for a language "
                "renders the normal empty state rather than an error or another language's files.",
            ),
        },
    ]),

    ("Session & Player Languages", [
        {
            "title": "A session's own extra languages are reachable from the portal",
            "custom_preconds": p(
                "A session whose additional languages include one that is NOT enabled on the "
                "portal (the admin allows this deliberately)."
            ),
            "custom_steps": p(
                "1. Open that session on the portal.",
                "2. Inspect the in-player language options.",
            ),
            "custom_expected": p(
                "The extra language is offered for the session's audio/stream even though the "
                "portal chrome has no locale for it; the surrounding page stays in the portal's "
                "active locale. Confirm this is the intended split rather than a dead option.",
            ),
        },
        {
            "title": "The in-player language dropdown appears for a session with two audio languages",
            "custom_preconds": p(
                "A session with exactly ONE additional language on top of its default (two "
                "streams in total)."
            ),
            "custom_steps": p("1. Open the session and look for the in-player language control."),
            "custom_expected": p(
                "EXPECTED: the dropdown is offered, since there are two languages to choose from.",
                "ACTUAL (risk): the control is gated on additionalLanguages.length &gt; 1, so a "
                "session with a single additional language shows no selector and the second "
                "stream is unreachable. Verify against a session with two additional languages, "
                "where the control does appear.",
            ),
        },
        {
            "title": "Switching the player language swaps the stream and its per-language assets",
            "custom_preconds": p("A live or on-demand session with two or more additional languages."),
            "custom_steps": p(
                "1. Open the session and note the current language on the player toggle.",
                "2. Choose another language from the in-player dropdown.",
            ),
            "custom_expected": p(
                "The player reloads that language's primary stream URL, the active speaker "
                "headshot and any per-language slides follow, and the toggle shows the newly "
                "selected language. Playback resumes rather than erroring.",
            ),
        },
        {
            "title": "The player opens in the page's locale and falls back cleanly",
            "custom_preconds": p(
                "A session whose languages do NOT include the portal's active locale."
            ),
            "custom_steps": p(
                "1. Set the portal to a language the session does not carry.",
                "2. Open the session.",
            ),
            "custom_expected": p(
                "The player starts from the page locale where a matching stream exists; where it "
                "does not, it falls back to the English stream and then to the session's primary "
                "stream. The attendee never gets a silent or dead player.",
            ),
        },
    ]),

    ("Localization — Known Defects & Risks", [
        {
            "title": "DEFECT: a Traditional Chinese portal falls back to English",
            "custom_preconds": p("A client/portal whose default language is Traditional Chinese (zh_TW)."),
            "custom_steps": p(
                "1. Clear the portal's cookies.",
                "2. Open the portal with no locale prefix, and again at /zh_TW/&lt;portalID&gt;.",
            ),
            "custom_expected": p(
                "EXPECTED: the portal opens in Traditional Chinese.",
                "ACTUAL: getBrandingLocale lower-cases the branding language to 'zh_tw' and then "
                "tests it against SUPPORTED_LOCALES, which holds the mixed-case 'zh_TW'. The test "
                "fails and the function returns 'en', so the first-visit redirect sends the "
                "attendee to English. The same lower-casing is applied to the portal's additional "
                "languages when deciding whether a requested locale is available.",
            ),
        },
        {
            "title": "RISK: the Turkish locale is remapped to Farsi when fetching session content",
            "custom_preconds": p("A portal with Turkish enabled, showing a session."),
            "custom_steps": p(
                "1. Switch the portal to Turkish.",
                "2. Open a session and watch the session content request.",
            ),
            "custom_expected": p(
                "The session components translate locale 'tr' into language 'fa' before requesting "
                "content, so Turkish attendees are served the Farsi content slot while the rest of "
                "the page stays Turkish. Confirm whether this is a deliberate per-client "
                "arrangement; if so it needs documenting, because it makes 'tr' unusable as real "
                "Turkish.",
            ),
        },
        {
            "title": "RISK: Danish can be set in the admin but is not a portal locale",
            "custom_preconds": p("A client created with Danish as its default language."),
            "custom_steps": p(
                "1. Create the client with Danish, build a portal on it and publish.",
                "2. Open the published portal URL.",
            ),
            "custom_expected": p(
                "The portal serves 12 locales that include Turkish but NOT Danish, while the admin "
                "client dropdown offers Danish but not Turkish. A Danish portal therefore resolves "
                "to English. Either Danish is added to the portal locales or it is removed from "
                "the admin dropdown.",
            ),
        },
    ]),
]


def existing_sections(url, user, key):
    """{name: id} for the sub-sections already under 'Localization'."""
    data = call(url, user, key, f"get_sections/{PROJECT_ID}&suite_id={SUITE_ID}")
    sections = data.get("sections", data) if isinstance(data, dict) else data
    return {s["name"]: s["id"] for s in sections if s.get("parent_id") == PARENT_SECTION_ID}


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
    print(f"Project {PROJECT_ID} / suite {SUITE_ID}, under section {PARENT_SECTION_ID} 'Localization'")
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
                "parent_id": PARENT_SECTION_ID,
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
