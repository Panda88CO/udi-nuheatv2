# NuHeat Signature NodeServer

A Polyglot v3 (PG3 / PG3x) NodeServer for integrating **NuHeat Signature** radiant floor heating thermostats with Universal Devices controllers (eisy / Polisy / IoX).

---

## Requirements

- Universal Devices controller (**eisy** or **Polisy**) running **PG3** or **PG3x**
- One or more **NuHeat Signature** WiFi floor heating thermostats
- Active **[My NuHeat](https://mynuheat.com)** account
- NuHeat API OAuth credentials (**Client ID** & **Client Secret**)

---

## Installation

1. Open your PG3/PG3x dashboard.
2. Go to the **NodeServer Store**.
3. Locate **NuHeat** and click **Install** (or install from your GitHub repository URL).


## Configuration

In the PG3 dashboard under the NodeServer's **Configuration** tab, add the following **Custom Configuration Parameters**:

| Key | Type | Description | Default |
| :--- | :--- | :--- | :--- |
| `clientId` | string | Your NuHeat OAuth Client ID (if not provided via PG3 OAuth setup) | *(none)* |
| `clientSecret` | string | Your NuHeat OAuth Client Secret (if not provided via PG3 OAuth setup) | *(none)* |
| `tz` | string | Your local tz database timezone name *(Required for energy logs)* | `America/New_York` |
| `temp_unit` | string | Temperature unit: `F` for Fahrenheit or `C` for Celsius | `F` |

*Refer to the [tz database time zones list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) to find your timezone string (e.g., `America/New_York`, `America/Chicago`, `America/Denver`, `America/Los_Angeles`).*

> [!NOTE]
> `clientId` and `clientSecret` can be configured either via PG3's OAuth setup or entered in **Custom Configuration Parameters** (`clientId` and `clientSecret`).

---

## First-Time Setup & Authentication

1. **Authenticate**: Click the **Authenticate** button on the NodeServer details page in the PG3 dashboard.
2. **Log In**: A browser window will open to the NuHeat login page. Sign into your My NuHeat account and grant access.
3. **Discovery**: Once authentication completes, the NodeServer automatically discovers your connected thermostats and creates all device nodes in your Admin Console.

---

## Setting Operating Mode & Setpoint

The thermostat uses a single consolidated command, **`SET_MODE`**, which accepts up to 3 parameters:
- **Mode (`mode`)**:
  - `1` = **Auto** (Follow internal schedule): Temperature and hold duration are ignored. Setpoint (`CLISPH`) and Hold End Time (`GV4`) display as `Invalid` in the Admin Console.
  - `2` = **Hold** (Temporary Hold): Sets target temperature (`temp`) and temporary hold duration in minutes (`hold`). The NodeServer sets `GV4` to the hold expiration timestamp (Unix epoch timestamp, UOM 151).
  - `3` = **Permanent Hold** (Manual): Sets target temperature (`temp`) permanently until changed. Hold duration is ignored and `GV4` displays as `Permanent Hold`.
- **Temperature (`temp`)**: Target heating setpoint in configured scale (°F or °C). Ignored in Auto mode.
- **Hold Minutes (`hold`)**: Duration in minutes (0–1440) for temporary hold. Ignored in Auto and Permanent Hold modes.

---

## Features & Discovered Nodes

The NodeServer automatically detects your account's preferred temperature scale (°F or °C) and creates the following nodes:

- **Controller Node**:
  - **Drivers**:
    - **NodeServer Online (`ST`)**: Indicates whether the NodeServer process is running and connected (Online / Offline, UOM 2).
    - **Last Update (`TIME`)**: Unix epoch timestamp (UOM 151) of the last successful communication/poll with the controller.
  - **Heartbeat (`DON` / `DOF`)**: Emits alternating `DON` and `DOF` control events on each short poll for ISY watchdog / heartbeat monitoring programs.
  - **Commands**:
    - **Update (`UPDATE`)**: Immediately forces an update across all nodes and queries fresh energy metrics (executes long poll).

- **Thermostat Node (`°F` or `°C`)**:
  - **Temperature & Setpoint**: Reports current temperature (`ST`) and target setpoint (`CLISPH` — displays `Invalid` in Auto mode).
  - **Operating Mode (`CLIMD`)**: Auto, Hold, or Permanent Hold.
  - **Heat State (`CLIHCS`)**: Idle or Heating.
  - **Hold End Time (`GV4`)**: Displays the hold expiration timestamp (Unix epoch timestamp, UOM 151) when on Hold; displays `Permanent Hold` in Permanent Hold mode, and `Invalid` in Auto mode.
  - **Online Status (`GV5`)**: Thermostat connection status (Online / Offline, UOM 2).
  - **Last Update (`TIME`)**: Unix epoch timestamp (UOM 151) of the last data refresh for this thermostat.
  - **Commands**:
    - **Set Mode (`SET_MODE`)**: Interactive GUI command with inputs for Mode (Auto, Hold, Permanent Hold), Temperature, and Hold Minutes.
    - **Query (`QUERY`)**: Queries current state from the NuHeat cloud.
  - **Energy Metrics (UOM 33 / kWh)**:
    - **Daily Energy** (`GV0`): Energy used today in kWh.
    - **Last 7 Days Energy** (`GV1`): Energy used over the past 7 days in kWh.
    - **Monthly Energy** (`GV2`): Month-to-date energy usage in kWh.
    - **Yearly Energy** (`GV3`): Year-to-date energy usage in kWh.

---

## Polling

- **Short Poll (default 300s)**: Queries thermostat status, temperature, mode, and heating activity.
- **Long Poll (default 1800s)**: Updates energy usage metrics.

---

## Limitations

- Internal thermostat scheduling is not edited through the NodeServer (use ISY programs instead).
