# Reel Bot (Telegram)

## 1. Telegram token
Telegram-e @BotFather -> /newbot -> token copy koro.

## 2. GitHub-e upload
Ei folder-er shob file ekta GitHub repo-te dao (phone theke GitHub app/web-e hoy).

## 3. Deploy (Render, free)
- render.com -> New -> Web Service -> repo select
- Runtime: Docker
- Environment variable: BOT_TOKEN = tomar token, PAGE_NAME = tomar page-er naam (optional)
- Create. Build hote kichu minute lage.

Free plan-e 15 min idle thakle ghumay. UptimeRobot (free) diye Render URL-e prottek 5 min ping dile jege thake.

## 4. Use
/reel  -> random tech fact reel
/reel voice=male
/reel Title | point 1 | point 2 | point 3
