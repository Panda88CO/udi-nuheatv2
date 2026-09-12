# NuHeat NodeServer Configuration (PG3 / PG3x)

This NodeServer connects Universal Devices controllers (eisy / Polisy) to **NuHeat Signature** radiant floor heating thermostats via the official NuHeat Cloud API and OAuth 2.0.

---

## 1. OAuth Setup

To link your NuHeat account, you will need OAuth credentials (**Client ID** and **Client Secret**) from NuHeat. 

When registering or requesting your OAuth client with NuHeat, provide the following application settings:

| Setting | Value |
| :--- | :--- |
| **Grant Type** | `Authorization Code` (`authorization_code`) and `Refresh Token` (`offline_access`) |
| **Return URI (Redirect URI)** | `https://my.isy.io/api/cloudlink/redirect` |
| **Authorization Endpoint** | `https://identity.mynuheat.com/connect/authorize` |
| **Token Endpoint** | `https://identity.mynuheat.com/connect/token` |
| **Scopes** | `openapi openid profile offline_access` |

> [!NOTE]
> Make sure the Redirect URI is entered exactly as `https://my.isy.io/api/cloudlink/redirect` without trailing slashes.

---

## 2. Custom Configuration Parameters

In your PG3/PG3x NodeServer dashboard, configure the following keys under **Configuration** -> **Custom Configuration Parameters**:

| Key | Type | Description | Default |
| :--- | :--- | :--- | :--- |
| `tz` | string | Your local tz database timezone name (Required for accurate energy log timestamps) | `America/New_York` |
| `temp_unit` | string | Temperature unit: `F` for Fahrenheit (UOM 17) or `C` for Celsius (UOM 4). | `F` |

*A complete list of timezone names can be found in the [tz database time zones list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) (e.g., `America/New_York`, `America/Chicago`, `America/Denver`, `America/Los_Angeles`).*

> [!NOTE]
> Client ID and Client Secret are managed directly in PG3's OAuth setup (similar to TeslaEVstream). They are not required as custom configuration parameters.

---

## 3. Authentication Steps

1. Enter your `clientId`, `clientSecret`, and `tz` in the **Custom Configuration Parameters** section and click **Save**.
2. Restart the NodeServer if it doesn't automatically restart.
3. Click the **Authenticate** button in the PG3 NodeServer details page.
4. Log into your **[My NuHeat](https://mynuheat.com)** account in the browser window and approve access.
5. Once authorized, the NodeServer will automatically discover your thermostats and create the corresponding nodes in your Admin Console.
1. Configure `tz` (and optionally `TEMP_UNIT`) in **Custom Configuration Parameters** and click **Save**.
2. When the OAuth configuration is loaded in PG3, click the **Authenticate** button in the PG3 NodeServer details page.
3. Log into your **[My NuHeat](https://mynuheat.com)** account in the browser window and approve access.
4. Once authorized, the NodeServer will automatically discover your thermostats and create the corresponding nodes in your Admin Console.

---

## 4. Thermostat Operating Mode Recommendation

For the NodeServer to have full control over thermostat target temperatures:
1. On the physical thermostat screen, go to **Setup** → **Preferences**.
2. Tap **Operating Mode**.
3. Change it from **Auto** (schedule-based) to **Manual**.
4. *Note: Setting to Manual will disable internal schedules so the ISY/eisy can control setpoints directly.*

---

## 5. Discovered Nodes

For each thermostat discovered on your account, the following nodes are created:
1. **Thermostat Node** (`°F` or `°C` automatically selected based on your NuHeat account preferences).
2. **Energy Log - Day** (Daily energy usage in watt-hours).
3. **Energy Log - Week** (Weekly energy usage in watt-hours).
4. **Energy Log - Year** (Yearly energy usage in watt-hours).
