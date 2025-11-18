## ⚠️ Important Notice – New InverterCard Version


To avoid inconsistent system states caused by using the **InverterCard simultaneously in a browser and the Home Assistant smartphone app**, the card has been reworked.

### 🔁 Cache Notice – Required After Updating the InverterCard:

##### 📱 **For Home Assistant App Users (Smartphones):**

The app uses an internal browser engine that caches JavaScript files.
➡️ You **must clear the app’s data and cache** via your **phone settings**:
Go to *Apps → Home Assistant → Storage → Clear Cache and Data*.
⚠️ You will need to **log in again** afterwards.
Skipping this step may result in a broken or outdated InverterCard!

##### 🖥️ **For Browser Users (Desktop or Mobile):**

1. Press **F12** (opens Developer Tools)
2. Go to the **“Network” tab**
3. Enable **“Disable cache”**
4. Reload the page with **F5**

✅ Make sure the **correct InverterCard version number** appears in the card header.
❌ If it doesn't, you're still using a cached (old) version.

---

<img width="608" height="542" alt="Bildschirmfoto_20251118_175352" src="https://github.com/user-attachments/assets/1c8c39db-8a64-4c01-ac32-ead87eac7624" />
