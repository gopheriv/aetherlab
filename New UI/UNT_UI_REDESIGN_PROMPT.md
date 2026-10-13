# UNT Study App — Complete UI Redesign Prompt

Redesign the existing application into a polished, student-first UNT (ҰБТ) study experience. Inspect the repository and current application before changing anything. Preserve existing data, workflows, exam rules, localization, and working features; map navigation to real routes and functionality. Build the redesign into the current app rather than producing a disconnected mockup. Use reusable components and centralized design tokens, and update every existing screen that students can reach.

## Visual direction

Create an inviting, mature study environment that supports long sessions and makes the next useful action obvious. Use the supplied reference images as mood and color inspiration, not as compositions to copy:

- `C:\Users\sunak\Downloads\WhatsApp Image 2026-10-08 at 21.54.30.jpeg`
- `C:\Users\sunak\Downloads\WhatsApp Image 2026-10-08 at 21.55.21 (1).jpeg`
- `C:\Users\sunak\Downloads\WhatsApp Image 2026-10-08 at 21.55.21.jpeg`
- `C:\Users\sunak\Downloads\WhatsApp Image 2026-10-08 at 21.54.30 (1).jpeg`
- `C:\Users\sunak\Downloads\WhatsApp Image 2026-10-08 at 21.55.20 (1).jpeg`
- `C:\Users\sunak\Downloads\WhatsApp Image 2026-10-08 at 21.55.20.jpeg`

Build a bright study studio with a cool white background, white panels, charcoal text, and violet primary actions. Use mint, lavender and apricot topic surfaces. Make the change structural: compact navigation, a split learning dashboard, searchable topic cards, and separate practice and timed-mock choices.

- Window: `#F7F8FC`; panels and navigation: `#FFFFFF`
- Inputs: `#F6F5FA`; borders: `#E6E4EF`; stronger borders: `#D0CDDF`
- Main text: `#252333`; secondary: `#615D75`; muted: `#746E83`
- Primary violet: `#7655D9`; hover: `#6443C7`; pressed: `#5432B0`; button text: white
- Topic surfaces: lavender `#EEE8FC`, mint `#E5F3EC`, apricot `#FFF0E1`
- Success: `#16866B`; warning: `#B5732F`; error: `#CC4E6C`

Use readable foregrounds on every accent surface, including buttons and icons. Verify text contrast rather than relying on color alone.
## Product structure and navigation

Use a 92px desktop navigation rail with an icon above a short localized label. Place the PhysLab wordmark, page breadcrumb, subject badge, language selector and settings in a 68px top bar. Include Home, Subjects, Practice, Mock Exams, Progress, and Profile only when each has a real route and existing functionality. Add a restrained top bar for the page title, language selection, and notifications where supported. On narrow screens, use a compact bottom navigation for the most important real destinations; adapt cards and columns naturally for phones, tablets, and wide screens. Never leave visible controls dead-ended or invent nonexistent account flows.

Preserve and verify Kazakh and Russian localization. Labels must not clip or break layouts. Give every screen one clear primary action, with distinct hover, focus, pressed, disabled, loading, empty, and error states. Ensure keyboard navigation, comfortable touch targets, accessible text-and-icon status cues, and 150–200ms transitions that respect reduced-motion preferences.

## Core student journeys

1. **Home:** Show a personal greeting, one prominent Continue studying action, a compact progress overview, and a practical daily plan. Include current subjects, recent real results, and recommended next topics. Use a spacious main column with a smaller supporting column on desktop. Avoid competing cards and unsupported readiness predictions.
2. **Subjects:** Organize subjects and topics into clear groups. Show honest completion and progress, distinguish completed/current/upcoming topics, and make the next lesson easy to find and continue.
3. **Practice:** Create a focused question view with readable prompts, generous spacing, accessible answer choices, question progress, and previous/next controls. Preserve support for formulas and images. Make selected, correct, incorrect, and unanswered states unmistakable through labels or icons as well as color.
4. **Mock exams:** Make exam choice and instructions easy to scan. During an exam, prioritize the question, timer, and navigator; distinguish answered, unanswered, and flagged questions. Add a review step before submission. Preserve configured exam rules, timing, and scoring.
5. **Results and progress:** Lead with the score, then show subject performance, history, and specific topics to review. Pair charts with readable labels and next actions. Use existing saved data honestly and label any demo content clearly.
6. **Profile and settings:** Group only settings the application already supports, including personal details, subject preferences, study goals, language, and application options.

## Implementation and verification

Centralize colors, spacing, typography, radii, focus, and component states in design tokens. Replace inconsistent legacy styling throughout all existing student-facing screens. Keep data connected to the real application and preserve persistence. Reuse existing components where sound; refactor duplicated UI where that improves consistency without breaking behavior.

Run the relevant tests and static checks. Exercise the principal journeys: open Home, continue to a subject/topic, start and answer practice questions, take or review a mock exam where supported, and inspect saved results. Check narrow and wide layouts supported by the actual platform, keyboard use, localization, text overflow, and accessibility contrast. Fix defects found during review. Finish with a concise report of screens changed, checks run, and any platform or feature limits that remain.

Avoid excessive gradients, glass effects, oversized decorative art, heavy shadows, crowded dashboards, unnecessary animation, fake data presented as real, and any control that appears functional but is not.
