# Siniristi integration

The supplied handoff and reference components are in this directory. The app
imports `siniristi.css` from `app/globals.css`; the existing home classes and both
sports-page CSS modules use its tokens. Existing copy, API calls, filters,
forecasts, and scenario calculations are retained. Backend files are unchanged.

## Fonts and themes

- Plus Jakarta Sans (variable 400–800) and IBM Plex Mono (500/600) are self-hosted
  through Fontsource packages and `next/font/local`; builds and page loads do not
  request Google Fonts. The reference CSS's remote import was replaced accordingly.
- The server supplies `data-theme="light"` as the fallback. A blocking inline head
  script chooses a valid saved override or the system preference before body paint.
- The moon/sun button switches light/dark and remembers the choice under
  `siniristi-theme`. The monitor button restores system mode. System changes apply
  live in system mode; explicit choices remain fixed. Tabs synchronize changes.
- Storage denial does not prevent theme switching for the current tab.
- Surface/background color transitions were removed so text and surfaces change
  together when switching themes. Reduced-motion preferences are respected.

## Accessibility adjustments

- Text and controls use the supplied semantic tokens in both themes. Dark team
  tint opacity is 0.08 instead of 0.12 to retain AA contrast for negative values
  on highlighted rows; other brand colors retain the supplied values.
- Demo and AI badges remain distinct. The yellow team accent is used for identity.
  A separate scrim token supplies the story overlay.
- Controls have 44px targets. At 390px, cards become one column, filters stack,
  and wide tables stay inside keyboard-focusable, named scroll regions.
- Story dialogs focus the close control, retain keyboard focus, close with Escape,
  and restore focus to the opening button.

## Verification

Run from `frontend/`:

```sh
npm install
npm run lint
npm run build
```

Browser validation used Chromium and axe WCAG A/AA checks on all three routes and
the story dialog, in light/dark at 1440px and 390px. Theme checks covered system
changes, saved overrides, reload, cross-tab synchronization, unavailable storage,
and correct initial theme with hydration bundles blocked. Existing forecast,
scenario, show-more, retry, navigation, and mobile interactions were also checked.
Automated accessibility checks supplement manual visual and keyboard inspection;
they do not constitute a full accessibility certification.
