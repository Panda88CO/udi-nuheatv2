# NuHeat NodeServer Configuration (PG3 / PG3x)

This NodeServer connects Universal Devices controllers (eisy / Polisy) to **NuHeat Signature** radiant floor heating thermostats via the official NuHeat Cloud API and OAuth 2.0.

---


## 1. Custom Configuration Parameters

In your PG3/PG3x NodeServer dashboard, configure the following keys under **Configuration** -> **Custom Configuration Parameters**:

| Key | Type | Description | Default |
| :--- | :--- | :--- | :--- |
| `tz` | string | Your local tz database timezone name (Required for accurate energy log timestamps) | `America/New_York` |
| `temp_unit` | string | Temperature unit: `F` for Fahrenheit (UOM 17) or `C` for Celsius (UOM 4) | `F` |

*A complete list of timezone names can be found in the [tz database time zones list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) (e.g., `America/New_York`, `America/Chicago`, `America/Denver`, `America/Los_Angeles`).*

> [!NOTE]
> Client ID and Client Secret are managed directly in PG3's OAuth setup (similar to TeslaEVstream). They are not required as custom configuration parameters.

---

## 2. Authentication Steps

1. Configure `tz` and `temp_unit` (`F` or `C`) in **Custom Configuration Parameters** and click **Save**.
2. When the OAuth configuration is loaded in PG3, click the **Authenticate** button in the PG3 NodeServer details page.
3. Log into your **[My NuHeat](https://mynuheat.com)** account in the browser window and approve access.
4. Once authorized, the NodeServer will automatically discover your thermostats and create the corresponding nodes in your Admin Console.

---

## 3. Thermostat Operating Mode Recommendation

For the NodeServer to have full control over thermostat target temperatures:
1. On the physical thermostat screen, go to **Setup** → **Preferences**.
2. Tap **Operating Mode**.
3. Change it from **Auto** (schedule-based) to **Manual**.
4. *Note: Setting to Manual will disable internal schedules so the ISY/eisy can control setpoints directly.*

---

## 4. Discovered Nodes

For each thermostat discovered on your account, the following nodes are created:
1. **Thermostat Node** (`°F` or `°C` selected based on your `temp_unit` configuration or NuHeat account preferences).
2. **Energy Log - Day** (Daily energy usage in watt-hours).
3. **Energy Log - Week** (Weekly energy usage in watt-hours).
4. **Energy Log - Year** (Yearly energy usage in watt-hours).

