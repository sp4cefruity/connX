# Could connX be an extension on Google Maps instead of a standalone app?

Researched 2026-11-11. Primary sources only; every claim has its source inline. Anything not confirmed on an owner's page is marked **UNVERIFIED**. This is engineering research, not legal advice.

## TL;DR

- **There is no official way to extend the consumer google.com/maps site or the Google Maps mobile apps.** A Chrome extension content script can technically run on maps.google.com ([Chrome content scripts](https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts)), but Google publishes no plugin API for it. I found no clause that names browser extensions. Reading or copying Maps content is restricted by the end-user terms ([Maps Additional Terms](https://www.google.com/help/terms_maps/), section 2).
- **Using Google's paid APIs does not fix the cost problem.** connX needs route geometry, and Google's terms forbid showing Routes API content on a non-Google map ([Service Specific Terms, Routes API 19.2](https://cloud.google.com/maps-platform/terms/maps-service-terms)). Using the data therefore means rebuilding the map on Google's Maps JavaScript API, with an API key and a billing-enabled project ([get-api-key](https://developers.google.com/maps/documentation/javascript/get-api-key)).
- **The zero-cost Google integration is the Maps URL hand-off.** connX computes and compares routes on its free stack, then opens Google Maps with an origin, destination and up to 9 waypoints (3 on mobile browsers). No API key is needed ([Maps URLs](https://developers.google.com/maps/documentation/urls/get-started)).
- **Recommendation: stay standalone on the free stack and add a "Open in Google Maps" hand-off.** It is about 1 to 2 days of work. A Chrome extension is a poor fit: it is fragile, has an unclear ToS position, and does not exist on phones.
- **The main product risk is not the map provider.** The weak spot is the free public routing and geocoding servers (no SLA, see README "Known issues"). Self-hosting OSRM or Valhalla would improve that more than any Google tie-in.

## 1. What connX is today

Sources are in this repo.

- **Purpose** ([README.md](../../README.md), [CONTEXT.md](../../CONTEXT.md)): the user enters Route A (their own trip) and Route B (the other person's trip) in one travel mode. connX reports where they **overlap** (about 25 m tolerance), draws a **red zone band** around B at a user-set danger distance (50 m to 1 km), and marks **encounters** (A inside the band but not overlapping). Users can also draw **red spots** (named circles, 50 m to 2 km, that A must avoid) and ask for a **recommendation** (a scored alternative for A, built from candidate detours, [ADR 0006](../adr/0006-recommend-builds-its-own-detour-candidates.md)). A comparison card shows time and distance for both routes.
- **Stack** (verified from the repo, no external source needed):
  - Routing: OpenRouteService with fallback to public OSRM, one OSRM server per mode, cached for an hour ([ADR 0005](../adr/0005-ors-routing-with-osrm-fallback-and-result-caching.md), `backend/app/routing/`).
  - Search: Photon with Nominatim fallback ([ADR 0003](../adr/0003-photon-search-with-nominatim-fallback.md)).
  - Basemap: MapLibre GL with OpenFreeMap vector tiles, retinted for light and dark themes ([ADR 0004](../adr/0004-vector-basemap-with-light-and-dark-styles.md), `frontend/lib/basemapStyle.ts`, `frontend/components/MapView.tsx`).
  - Backend: FastAPI + Shapely. All overlap, encounter, red-spot and scoring maths runs in Python (`backend/app/services/*`, `backend/.env.example`). Only red spots are stored, per anonymous cookie user.
- **What connX needs from a map provider:**
  1. Geocoding and autocomplete (text to coordinates).
  2. Route geometry for A and B, as a full polyline, not just a distance.
  3. Alternative routes or via-point routing (for recommendations).
  4. Duration and distance per route.
  5. A basemap on which to draw its own layers (overlaps, band, markers, circles).

  Items 2 and 3 are the crux. All the value comes from running geometry maths on the full polyline.
- **Red-spot data (question f):** red spots are user-drawn and stored locally. They use no third-party dataset, so there are no external data-licence constraints. The data constraints are on the map and routing providers (see section 3).

## 2. What is allowed and prohibited on Google's side

### 2a. Extending consumer Google Maps

- **Chrome extension technique.** Content scripts "run in the context of web pages" and "can read and change the page's DOM." They run in an isolated world and are matched by URL pattern ([Chrome: content scripts](https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts)). So an extension can technically inject UI into google.com/maps.
- **No official extension API.** I found no Google page that documents extending the consumer site or the mobile apps. The only documented routes are the Maps Platform products below. Absence of a page is not proof, so treat this as **UNVERIFIED as a universal negative**.
- **Consumer terms.** The [Google Maps End User Additional Terms](https://www.google.com/help/terms_maps/) (last modified January 27, 2026) say that when using Google Maps you may not:
  - "redistribute or sell any part of Google Maps or create a new product or service based on Google Maps";
  - "copy the content (unless you are otherwise permitted to do so ...)";
  - "mass download or create bulk feeds of the content";
  - "use any part of Google Maps with other people's products or services for or in connection with real-time navigation ... except through a specific Google-provided feature such as Android Auto."

  The Google [Terms of Service](https://policies.google.com/terms) also bar "using automated means to access content from any of our services in violation of the machine-readable instructions on our web pages (for example, robots.txt files ...)". An extension that only reads the visible origin and destination for the user's own use is arguably "copying" at most. Whether that breaches the terms is a legal question I cannot settle from these pages: **UNVERIFIED**. Realistic enforcement risks are Google breaking the DOM, or blocking automated reads.
- **What the page exposes.** Route geometry is not a documented, stable interface. I did not verify how the Maps page encodes the route, so the claims "geometry is not in the DOM" and "the URL carries the destination" are **UNVERIFIED**. Any extension must therefore re-derive the route itself from origin and destination, which gives connX's route (OSRM/ORS), not Google's. The two can differ.

### 2b. Official Google surfaces and cost

- **Platform terms.** Section 3.2.3 of the [Maps Platform ToS](https://cloud.google.com/maps-platform/terms) restricts:
  - **(a) No Scraping:** "not export, extract, or otherwise scrape Google Maps Content for use outside the Services", including "bulk download ... directions".
  - **(b) No Caching**, except as the Service Specific Terms allow.
  - **(c) No Creating Content From Google Maps Content.**
  - **(d) No Re-Creating Google Products**, including "a substitute of ... Google Maps".
  - **(e) No Use With Non-Google Maps:** "Customer will not use the Google Maps Core Services with or near a non-Google Map ... or (iii) link a Google Map to non-Google Maps Content or a non-Google Map."
- **Routes API specifics.** The [Service Specific Terms, section 19](https://cloud.google.com/maps-platform/terms/maps-service-terms) say:
  - 19.1: the content may be used "without a corresponding Google Map".
  - 19.2: "must not use Google Maps Content from the Routes API in conjunction with a non-Google map."
  - 19.3: only lat/lng may be cached, for up to 30 days. The Directions API (section 4) has the same pattern. Geocoding (6.2) and Places (14) also bar use with a non-Google map.
- **Consequence for connX.** The current stack (MapLibre + OpenFreeMap) is a non-Google map. Google routing or geocoding data cannot be drawn on it. To use Google routing, connX would have to move to the Maps JavaScript API for the map. Whether connX's derived outputs (overlap segments, bands) count as "content based on Google Maps Content" under 3.2.3(c) is **UNVERIFIED** and arguable, since they are computed from a Google polyline. A Google-API rebuild carries that risk.
- **Pricing.** After the March 2025 change, the $200 monthly credit was replaced by a free monthly threshold per SKU: 10,000 billable events for Essentials, 5,000 for Pro, 1,000 for Enterprise ([Pricing FAQ](https://developers.google.com/maps/billing-and-pricing/faq)). The [pricing page](https://developers.google.com/maps/billing-and-pricing/pricing) lists the 10,000 cap for Essentials Compute Routes and Essentials Places/Geocoding. Embed is "unlimited" and free there. Pro-tier routing SKUs get 5,000. Past the caps you pay per 1,000 events, so a hobby project that stays under the caps pays nothing.
  - I did not verify which tier connX's calls (alternatives, via-points, polylines) fall into, or the per-1,000 price beyond the cap: **UNVERIFIED**.
  - One compare plus a recommendation makes several routing calls (see ADR 0005), so 10,000 free events is a modest ceiling.
- **API key required, billing usually too.** "Google Maps Platform products are secured from unauthorized use by requiring API calls to include an API key." A no-billing "Maps Demo Key" exists but "is not designed for production use"; production needs "a Google Cloud project with billing enabled" ([get-api-key](https://developers.google.com/maps/documentation/javascript/get-api-key)). The user said they cannot pay, so a billing account may itself be the blocker. Whether a card is required is not stated in the pricing FAQ: **UNVERIFIED**.
- **Maps Embed API.** "All Maps Embed API requests are available at no charge with unlimited usage" ([Embed get-started](https://developers.google.com/maps/documentation/embed/get-started)). It takes a key. Directions mode takes origin, destination, mode, and "up to 20 waypoints" ([embedding-map](https://developers.google.com/maps/documentation/embed/embedding-map)). It is an iframe. It exposes no geometry and offers no overlay API on the pages I read, so connX cannot draw bands or compute overlap on it. It also cannot sit beside the MapLibre map without hitting 3.2.3(e) "with or near a non-Google Map" (whether Embed counts as a "Core Service" I did not confirm: **UNVERIFIED**).
- **Bring-your-own-key (BYOK).** Section 4.1 makes the Customer responsible for use of its own account and keys ([ToS](https://cloud.google.com/maps-platform/terms), "Account" clause). Section 3.2.2(a) requires the application's own ToS to tell users that Google Maps terms apply. Each user would need a Cloud project, billing and a key restricted to the right domain. That is heavy for end users, and I found no Google page that blesses distributing an app where users supply keys. The legal reading is **UNVERIFIED**.

### 2c. Hand-off to the Google Maps app (zero API cost)

- **Maps URLs need no key.** "You don't need a Google API key to use Maps URLs" ([Maps URLs](https://developers.google.com/maps/documentation/urls/get-started)).
- **Directions URL parameters:** `origin`, `destination`, `waypoints` (separated by `|`) and `travelmode` (`driving`, `walking`, `bicycling`, `two-wheeler`, `transit`).
- **Waypoint limits:** "Up to three are supported on mobile browsers, and up to nine elsewhere. Some Google Maps products ignore this parameter."
- **Platform behaviour:** on Android and iOS the URL opens in the Google Maps app if installed, otherwise in a browser.
- **What this means for connX:**
  - A connX route is a polyline of hundreds of points, so only a thinned set of via-points can be handed over. Google will then re-route between them and may not match connX's exact path.
  - This fits the **recommended detour** well, because connX already builds routes from via-points beside the trouble stretch (ADR 0006). Pick at most 3 to 9 via-points.
  - **Android Auto and the Navigation SDK** are not usable here. The consumer terms bar real-time navigation with Google Maps "except through a specific Google-provided feature such as Android Auto" ([Maps Additional Terms](https://www.google.com/help/terms_maps/)). The platform terms bar Directions-API-based real-time navigation that is "substantially similar" to the Android app (3.2.3(d)(iv)) and bar use in "embedded vehicle systems" (3.2.3(f)). I did not read the Navigation SDK docs: **UNVERIFIED**.

### 2d. Chrome extension feasibility

- **Web Store policies** ([program policies](https://developer.chrome.com/docs/webstore/program-policies/policies)):
  - Single purpose: "An extension must have a single purpose that is narrow and easy to understand." A route-comparison overlay is narrow enough.
  - Manifest V3 remote code: "Execution of logic from a remote source is permissible only when accomplished through a documented API." The extension's logic must ship in the package. Calling connX's backend for data is fine; downloading code to run is not.
  - Data: "Extensions may only collect, use, or transmit user data that is necessary for the extension's disclosed single purpose." Sending the user's origins and destinations to the connX backend must be disclosed.
  - Do not mislead users. The listing must not imply it is a Google product.
- **Content script limits:** content scripts cannot use `eval()` or load external scripts ([content scripts](https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts)). MapLibre would have to be bundled.
- **Overlay mechanics.** Drawing red spots on Google's canvas needs the map viewport (centre, zoom) and pixel mapping. I found no documented API for that on the consumer site, so the overlay would be a hack built on the URL's `@lat,lng,zoom` or DOM internals. This is **UNVERIFIED** and fragile by nature.
- **Mobile reach:**
  - **Chrome on Android:** I could not find an official Chrome page that says extensions are supported. The extension FAQ I checked does not mention Android. Treat as **UNVERIFIED (no official support found)**; trade-press reports of an experimental desktop-style build are not primary evidence.
  - **Firefox for Android:** "offers a subset of the WebExtensions APIs available to the desktop version of Firefox" ([Extension Workshop](https://extensionworkshop.com/documentation/develop/differences-between-desktop-and-android-extensions/)). Which add-ons it can install is not stated there: **UNVERIFIED**.
  - **Safari iOS:** web extensions are available on iOS 15 and later and are "distributed with" an app, so you need an iOS app wrapper and an Apple Developer Program membership ([Apple: Safari web extensions](https://developer.apple.com/documentation/safariservices/safari-web-extensions), [packaging](https://developer.apple.com/documentation/safariservices/packaging-a-web-extension-for-safari)). The fee is not on those pages: **UNVERIFIED**.
  - **The Google Maps mobile apps themselves cannot be extended at all** (no extension surface found).
  - Net: desktop Chrome only, in practice. The connX README already treats the phone layout as a first-class case.

### 2e. Free alternatives (for comparison)

- **OpenFreeMap tiles (already used):** "no limits on the number of map views or requests", no API key, commercial use allowed. Attribution is required ([openfreemap.org](https://openfreemap.org/)).
- **Public OSRM demo:** "Excessive use is not allowed", a valid User-Agent is required, "Access to the Demo Server shall be withdrawn at any time and without giving a reason" ([OSRM API usage policy](https://github.com/Project-OSRM/osrm-backend/wiki/Api-usage-policy)). The wiki says those terms applied to the previous demo server and the current one is documented at routing.openstreetmap.de, which I did not read: **UNVERIFIED** for routing.openstreetmap.de itself.
- **Nominatim:** maximum 1 request per second, no client-side autocomplete, identifying User-Agent, and results must be cached for bulk jobs ([OSMF Nominatim policy](https://operations.osmfoundation.org/policies/nominatim/)). That is why connX uses Photon for type-ahead.
- **OpenRouteService:** the repo's ADR 0005 states 2,000 directions per day and 40 per minute. I could not confirm those numbers on the owner's page (the plans page redirected to a login-style page that did not show them): **UNVERIFIED against a primary source**.
- **Not researched (name only):** Valhalla, GraphHopper, Mapbox free tier. No claims about them are made here.

## 3. Options

| | A. Chrome extension on google.com/maps | B. Maps Embed / Maps JS API with BYOK | C. URL hand-off hybrid (recommended add-on) | D. Keep standalone on free stack |
|---|---|---|---|---|
| **What you build** | MV3 extension, content script that reads origin/destination from the page, calls the connX backend, draws overlay | Replace MapLibre with Google Maps JS, replace routing and geocoding with Google APIs, per-user keys | "Open in Google Maps" button that builds a Maps URL from A (or the recommended detour) | Nothing new; harden what exists |
| **Rough effort** | 2 to 4 weeks for desktop only; ongoing upkeep when Google changes the page | 3 to 6 weeks plus billing and key UX; heavy rewrite | 1 to 2 days | Self-host OSRM or Valhalla: days to a week |
| **Files that change** | New `extension/` dir (manifest, content script, bundled MapLibre, popup). Backend: CORS/auth for the extension origin in `backend/app/main.py`, `auth.py` (cookie won't flow) | `frontend/components/MapView.tsx`, `lib/basemapStyle.ts`, `lib/mapTheme.ts`, `redSpotMap.ts`, `LocationField.tsx`; backend `routing/*`, `routing/photon.py`; ADRs 0002-0005 superseded | New `frontend/lib/mapsUrl.ts`, a button in `ResultsPanel.tsx` / `ComparisonSummary.tsx`; no backend change | `backend/.env.example`, `docker-compose.yml`, maybe a new ADR |
| **Feasibility** | Technically possible on desktop; overlay alignment and route extraction are fragile (UNVERIFIED mechanics) | Possible, but Google's polyline terms (3.2.3(c), 19.3 caching) make the red-zone maths legally murky | Works today: documented, key-free | Works today |
| **ToS risk** | Medium to high and unresolved: consumer terms forbid copying and building a product on Google Maps; no clause explicitly permits an extension | Medium: compliance burden on you (attribution, ToS notice, BYOK responsibility) | Low: uses documented public URLs | Low, if the OSM fair-use rules are followed |
| **Cost** | Free to run, but the route data would still come from OSRM/ORS | Free only under per-SKU caps; billing account needed for production | $0 | $0 |
| **Platform reach** | Desktop Chrome only | Web (desktop and mobile browsers) | Desktop, Android, iOS (opens the Google Maps app if installed) | Web, any device |
| **Fixes the "redundant without Google Maps" concern?** | Partly: users stay in Google Maps UI, but connX data comes from a different router, so numbers can disagree with Google | Yes in appearance, but requires the payment the user wants to avoid | Yes for navigation: connX plans, Google Maps navigates | No, but it is the only option with no dependency on Google |

## 4. Recommendation

1. **Do D + C.** Keep the standalone app. Add the Maps URL hand-off so the user can navigate with Google Maps after planning in connX. This is also the cleanest answer to "redundant without Google Maps": connX is the planner, Google Maps is the navigator.
2. **Do not build the Chrome extension** unless the user accepts desktop-only reach, a fragile page-reading dependency and an unresolved ToS position. If they still want it, build a throwaway proof of concept first and test whether the origin and destination can be read reliably.
3. **Do not move to Google APIs** unless billing is acceptable. Section 19.2 forbids mixing Routes data with the current non-Google map, so it is a full rewrite.
4. **Spend the effort on routing reliability instead** (self-hosted OSRM or Valhalla), which addresses the real "known issues" in the README.

## 5. Open questions for the user

1. What does "redundant without Google Maps" mean in practice: users want to see Google's own routes and traffic, or just to navigate in Google Maps? Hand-off (C) covers the second only.
2. Are phones a requirement? Extensions are desktop-only in practice.
3. Is a billing account acceptable at all if usage stays under the free caps, or is any card a blocker?
4. Is connX personal/portfolio-only (PRD says hosting is out of scope) or to be distributed? Distribution triggers the Chrome Web Store policies and the Maps Platform ToS.
5. Should hand-off send the user's own route A, or only the recommended detour (which already has via-points)? Does a changed route after Google re-routes between via-points matter?
6. Is Google's traffic-aware timing needed? connX deliberately ignores live traffic (ADR 0005).

## 6. Sources

Google: [Maps Platform ToS](https://cloud.google.com/maps-platform/terms), [Service Specific Terms](https://cloud.google.com/maps-platform/terms/maps-service-terms), [Maps End User Additional Terms](https://www.google.com/help/terms_maps/), [Google Terms of Service](https://policies.google.com/terms), [Pricing](https://developers.google.com/maps/billing-and-pricing/pricing), [Pricing FAQ](https://developers.google.com/maps/billing-and-pricing/faq), [API key](https://developers.google.com/maps/documentation/javascript/get-api-key), [Embed](https://developers.google.com/maps/documentation/embed/get-started), [Embed directions](https://developers.google.com/maps/documentation/embed/embedding-map), [Maps URLs](https://developers.google.com/maps/documentation/urls/get-started).
Chrome and browsers: [content scripts](https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts), [Web Store policies](https://developer.chrome.com/docs/webstore/program-policies/policies), [Firefox Android](https://extensionworkshop.com/documentation/develop/differences-between-desktop-and-android-extensions/), [Safari web extensions](https://developer.apple.com/documentation/safariservices/safari-web-extensions).
Free stack: [OpenFreeMap](https://openfreemap.org/), [OSRM usage](https://github.com/Project-OSRM/osrm-backend/wiki/Api-usage-policy), [Nominatim policy](https://operations.osmfoundation.org/policies/nominatim/).
