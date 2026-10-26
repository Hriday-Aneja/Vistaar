# Notes (merged from the first Vistaar prototype)

## Cold start (what a brand-new shop sees)
- Swap Engine needs another Vistaar shop within the radius with stock and sales entered. Otherwise it shows the empty-state message from `/api/swaps/suggestions`.
- Udhaar risk needs several shops sharing a customer. With too little data it says "not enough data", never a default "Low".
- Pulse needs about 14 days of the shop's own sales plus neighbouring shops.
- Bulk-buy needs at least `K_ANONYMITY_MIN` shops in the cohort before a pooled number is shown. Distributor quotes are seed data until real distributors or owner-entered quotes exist.
- The event calendar (heatwave, cricket, weddings) is demo data. It needs an owner or a real weather/events source.
- Forecasts depend on owners logging sales. Plan a quick daily "aaj ki bikri" entry.
- The Fair-Price Radar benchmark needs at least 5 past orders per product.

## Done since the first prototype
- Phone numbers are hashed with HMAC using a secret outside the database (`VISTAAR_PHONE_SECRET`).
- `shops.is_demo` is a real column; demo and real shops never mix.
- Swap matching is a global min-cost-flow, not a per-shop greedy pick.

## Before a public launch
- Real private set intersection (or federated scoring) for the udhaar network. Today it is keyed hash + bucketed noise.
- DPDP Act: customer consent, privacy notice, deletion on request.
- Phone OTP verification and login rate limiting.
- Postgres backups, HTTPS.
- Real WhatsApp Business account for reminders (today: simulated channel).
- Label all simulated data in the UI (`Sale.is_simulated` exists).
- Pool members must opt in. In the demo, nearby shops are assumed to have joined the pool.
