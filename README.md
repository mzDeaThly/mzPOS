# Universal POS (Flask)

- Multi-tenant shops, menu/categories with images
- Tables + QR self-ordering (public page) with categories & images
- Kitchen screen, close bill, PromptPay QR (Thai-bank compatible)
- Inventory + recipe auto deduction on bill close, Members & points
- Subscriptions (monthly/yearly) with PromptPay
- HTML receipt printing

See `app.py`, `models.py`, and `utils/promptpay.py`.


## .env setup
คัดลอก/แก้ไขไฟล์ `.env` เพื่อกำหนดค่าระบบ เช่น PromptPay ของเจ้าของระบบ, ราคาแพ็กเกจ, DATABASE_URL, SECRET_KEY
จากนั้นรันแอปได้ตามปกติ (Flask จะโหลดค่าจาก `.env` อัตโนมัติผ่าน python-dotenv)
