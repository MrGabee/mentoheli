name: 💧 Vízművek Monitor

on:
  workflow_dispatch:
  repository_dispatch:
    types: [vizmuvek_trigger]
  schedule:
    # Biztonsági háló: ha az önindító lánc bármi okból megszakadna
    # (pl. lejárt token, GitHub API hiba), ez legkésőbb 10 percen
    # belül újraindítja a monitorozást.
    - cron: '*/10 * * * *'

concurrency:
  group: vizmuvek-monitor
  cancel-in-progress: false

jobs:
  figyel:
    runs-on: ubuntu-latest
    timeout-minutes: 4
    permissions:
      contents: write

    steps:
      - name: 📥 Kód letöltése
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.PAT_TOKEN }}

      - name: 🐍 Python beállítása
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: 📦 Függőségek telepítése
        run: pip install requests beautifulsoup4

      - name: 💧 Vízművek monitor futtatása
        env:
          EMAIL_KULDO:        ${{ secrets.EMAIL_KULDO }}
          EMAIL_JELSZO:       ${{ secrets.EMAIL_JELSZO }}
          EMAIL_CIMZETT_ARAM: ${{ secrets.EMAIL_CIMZETT_ARAM }}
          MAKE_WEBHOOK_URL:   ${{ secrets.MAKE_WEBHOOK_URL }}
        run: python vizmuvek_monitor.py

      - name: 💾 Állapot commitolása
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git stash
          git pull --rebase -X ours origin main || (git rebase --abort; git pull origin main --no-rebase -X ours)
          git stash pop || true
          [ -f vizmuvek_allapot.json ] && git add vizmuvek_allapot.json || echo "fájl nem létezik"
          git diff --staged --quiet || git commit -m "vizmuvek állapot [skip ci]"
          git push origin main || true
        env:
          GITHUB_TOKEN: ${{ secrets.PAT_TOKEN }}

      - name: 🗑️ Régi futások törlése
        if: always()
        run: |
          gh run list --workflow=vizmuvek_monitor.yml --limit 50 \
            --json databaseId,status \
            --jq '.[] | select(.status=="completed") | .databaseId' | \
            tail -n +6 | \
            xargs -I {} gh run delete {} --yes 2>/dev/null || true
        env:
          GH_TOKEN: ${{ secrets.PAT_TOKEN }}

      - name: ⏱️ Várakozás 60 másodpercet
        if: always()
        run: sleep 60

      - name: 🔄 Következő futás indítása
        if: always()
        run: |
          SIKERULT=0
          for i in 1 2 3; do
            HTTP_KOD=$(curl -s -o /tmp/dispatch_resp.txt -w "%{http_code}" -X POST \
              -H "Authorization: token ${{ secrets.PAT_TOKEN }}" \
              -H "Accept: application/vnd.github.v3+json" \
              https://api.github.com/repos/${{ github.repository }}/dispatches \
              -d '{"event_type":"vizmuvek_trigger"}')
            if [ "$HTTP_KOD" = "204" ]; then
              echo "✅ Dispatch sikeres."
              SIKERULT=1
              break
            else
              echo "⚠️ Dispatch sikertelen (HTTP $HTTP_KOD), próbálkozás $i/3..."
              cat /tmp/dispatch_resp.txt
              sleep 5
            fi
          done
          if [ "$SIKERULT" != "1" ]; then
            echo "❌ FIGYELEM: nem sikerült elindítani a következő futást! A schedule biztonsági háló legfeljebb 15 percen belül úgyis újraindítja a monitort."
          fi
