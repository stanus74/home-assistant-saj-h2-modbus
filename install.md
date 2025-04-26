## 🧪 Installation Guide: SAJ H2 Modbus

### To use version 2.1, a new installation is required
### If you have already installed 2.0.2-beta, you can update.

### 🔄 Step-by-step: Migrate from `saj_modbus` to `saj_h2_modbus`

1. **Deactivate the Old Integration**
   - Go to **Settings > Devices & Services**.
   - Find **SAJ Modbus**.
   - Click on it and **disable** the integration.

2. **Remove the Old Integration**
   - Still in **Devices & Services**, click **“Delete”** to fully remove `saj_modbus`.

3. **Remove it from HACS**
   - Go to **HACS > Integrations**.
   - Find **SAJ Modbus**.
   - Click the **three dots (⋮)** on the right, then **“Remove”**.

4. **Restart Home Assistant**
   - Go to **Settings > System > Restart**.
   - Wait until Home Assistant is fully back up.

5. **Install the New Integration via HACS**
   - Go to **HACS > Integrations**.
   - Click the **three dots (⋮)** at the top-right.
   - Choose **“Custom repositories”**.
   - Enter this GitHub URL:  
     👉 `https://github.com/stanus74/home-assistant-saj-h2-modbus`
   - Set category to **“Integration”**, then click **Add**.
   - Now install **SAJ H2 Modbus** from the HACS list.

6. **Update and Restart Again**
   - Let HACS finish installation.
   - Go to **Settings > System > Restart** once more.

7. **Set Up the New Integration**
   - After restart, go to **Settings > Devices & Services**.
   - Click **“+ Add Integration”**, search for **SAJ H2 Modbus**.
   - Follow the setup wizard (host, port, etc.).
