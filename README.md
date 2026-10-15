# Rally · Table tennis coaching

React + TypeScript + Vite prototype for a university table tennis club.

## Run

```sh
npm install
npm run dev
```

Open the local URL printed by Vite. `npm run build` type-checks and builds production assets; `npm test` checks scheduling rules.

## Included

- Login form with name, Instagram / Discord / phone, password, and player / coach / both roles.
- Monthly calendar, today highlighting, month navigation, and colored coach availability.
- Expandable coach sections with 15-minute slots, booking confirmation, booked states, and cancellation.
- Role-based navigation. Coaches manage their own schedule; dual-role members can switch views.
- Monday, Tuesday, Thursday 6:30–9 PM availability editor with week navigation, click/drag selection, keyboard selection, and booked-slot protection.
- Seeded John and Joe availability and browser persistence.

## Prototype boundaries

This is a frontend prototype, not production authentication. Passwords are only validated for length and are never stored. Profile identity is derived from the selected contact method and contact entry. Schedules and bookings persist in localStorage on this browser; there is no cross-device synchronization or server-enforced authorization. Role selection is for trying workflows. Replace these boundaries with backend authentication, verified coach permissions, and transactional booking APIs before real club use. Equipment, 30-minute sessions, payment information, and messaging integrations are future additions.

Dates and times use the browser's local timezone. Sample availability covers about three months ahead of initial load. To reset sample data, remove `rally-slots-v1` from browser localStorage.
