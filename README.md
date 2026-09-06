<<<<<<< HEAD
# Radha Krishan Hostel Website

Next.js starter website for Radha Krishan Hostel, Jaipur.

## Run
npm install
npm run dev

## Notes
- Registration section removed.
- 31 rooms: Basement 7, 1st 8, 2nd 8, 3rd 8.
- Occupancy values in app/page.js are demo values and should later be connected to MySQL.
- Replace gallery placeholders with real hostel photos.
- WhatsApp number: +91 7427 824 942.

## Password reset email
Set these environment variables before starting Flask. For Gmail, use a Google App Password, not the normal account password:

```powershell
$env:SMTP_HOST = "smtp.gmail.com"
$env:SMTP_PORT = "587"
$env:SMTP_USERNAME = "your-gmail-address@gmail.com"
$env:SMTP_PASSWORD = "your-16-character-app-password"
python app.py
```

For SMTP providers using SSL on port 465, also set `$env:SMTP_USE_SSL = "1"`.
=======
# Radha-Krishna-Hostel_New
>>>>>>> 2104a2da62eb55610275fd87a715049f18d8c1bd
