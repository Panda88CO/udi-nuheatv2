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

## 3. Operating Mode & Setpoint Control
 
The thermostat uses a single consolidated command, **`SET_MODE`**, with up to 3 parameters:
- **Mode (`mode`)**:
  - `1` = **Auto**: Follows internal schedule. Temperature and hold minutes are ignored. Setpoint (`CLISPH`) and Hold Minutes (`GV4`) display as `Invalid`.
  - `2` = **Hold**: Temporary hold using target `temp` and `hold` duration in minutes. Counts down remaining minutes on `GV4`.
  - `3` = **Permanent Hold**: Manual hold using target `temp` indefinitely. Hold minutes is ignored and `GV4` displays as `Permanent Hold`.
- **Temperature (`temp`)**: Target setpoint in °F or °C (ignored in Auto).
- **Hold Minutes (`hold`)**: Duration in minutes 0–1440 (ignored in Auto and Permanent Hold).

---

## 4. Discovered Nodes

For each thermostat discovered on your account, a single unified primary node is created:
1. **Controller Node**:
   - **Status Drivers**:
     - NodeServer Online (`ST` — Online / Offline, UOM 2)
     - Last Update (`TIME` — timestamp, UOM 151)
   - **Heartbeat**: Toggles `DON` / `DOF` on each short poll.
   - **Commands**:
     - **Update (`UPDATE`)**: Immediately force updates all nodes and energy logs.

2. **Thermostat Node** (`°F` or `°C` selected based on your `temp_unit` configuration or NuHeat account preferences).
   - **Status Drivers**:
     - Current Temperature (`ST`)
     - Heat Setpoint (`CLISPH` — displays `Invalid` [-1] in Auto mode)
     - Operating Mode (`CLIMD` — Auto, Hold, Permanent Hold)
     - Heat State (`CLIHCS` — Idle, Heating)
     - Hold Minutes (`GV4` — displays remaining minutes on Hold; displays `Permanent Hold` [-2] in Permanent Hold, and `Invalid` [-1] in Auto mode)
     - Online Status (`GV5` — Online / Offline, UOM 2)
     - Last Update (`TIME` — timestamp, UOM 151)
     - Daily Energy (`GV0` — kWh, UOM 33)
     - Last 7 Days Energy (`GV1` — kWh, UOM 33)
     - Monthly Energy (`GV2` — kWh, UOM 33)
     - Yearly Energy (`GV3` — kWh, UOM 33)
   - **Commands**:
     - **Set Mode (`SET_MODE`)**: Interactive GUI command with inputs for Mode (Auto, Hold, Permanent Hold), Temperature, and Hold Minutes.
     - **Query (`QUERY`)**: Query thermostat status.
