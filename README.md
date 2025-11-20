# Naksir Autonomous – Tickets Frontend

Static frontend that surfaces AI-generisane tikete preko GitHub Pages feed-a i pruža neon dark UI prilagođen futbalskim 2+ tiketima.

## Kako koristiti
- Otvori `public/index.html` u browseru ili pokreni lokalni server: `python -m http.server 8000 -d public` i idi na `http://localhost:8000`.
- Početni ekran ima Legal/Privacy/Terms linkove, Telegram CTA i dugme **Naksir Ultimate 2+ Tickets**.
- Klik na dugme učitava tikete sa `https://darkotosic.github.io/naksir-autonomous/tickets.json` i prikazuje ih u neon tamnoj temi.

## Struktura
- `public/index.html` – kompletan UI i JavaScript za preuzimanje i prikaz tiketa sa remote JSON feed-a.
- `public/tickets.json` – lokalni primer / fallback fajl (nije neophodan u produkciji jer se koristi remote URL).

## Razvojne napomene
- Tema koristi neon zelenu i tamni mod sa blagim outglow efektima. Pri ažuriranju UI elemenata zadrži ovu estetiku.
- Importi se ne umotavaju u try/catch blokove.
