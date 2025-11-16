# Changelog (v2.6.4)

## ⚠️ Important Notice – New InverterCard Version


### To avoid inconsistent system states caused by using the **InverterCard simultaneously in a browser and the Home Assistant smartphone app**, the card has been reworked.

### 🔁 Cache Notice – Required After Updating the InverterCard:

##### 📱 **For Home Assistant App Users (Smartphones):**

The app uses an internal browser engine that caches JavaScript files.
➡️ You **must clear the app’s data and cache** via your **phone settings**:
Go to *Apps → Home Assistant → Storage → Clear Cache and Data*.
⚠️ You will need to **log in again** afterwards.
**Skipping this step may result in a broken or outdated InverterCard!**

##### 🖥️ **For Browser Users (Desktop or Mobile):**

1. Press **F12** (opens Developer Tools)
2. Go to the **“Network” tab**
3. Enable **“Disable cache”**
4. Reload the page with **F5**

✅ Make sure the **correct InverterCard version number** appears in the card header.
**❌ If it doesn't, you're still using a cached (old) version.**

---

#### 🔧 New Behavior:

* Values for time and power must always be set (overwrite default).

* These are also written without activating/deactivating the charge/discharge button.

### Discharging Switch State Fix


- **Discharging Switch showed incorrect state**: The switch displayed "ON" when only register 0x3605 (Discharge Slots Bitmask) was set, but AppMode (register 0x3647) was still at 0
  - `switch.py`: `is_on` property now checks BOTH registers (discharging_enabled > 0 AND AppMode == 1)
  - Removed blocking `asyncio.run_coroutine_threadsafe()` calls → Reads directly from cache (synchronous, fast)
  - No more "took 1.001 seconds" warnings




