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
| `tz` | string | Your local tz database timezone name *(Required for energy logs)* | `America/New_York` |
| `temp_unit` | string | Temperature unit: `F` for Fahrenheit or `C` for Celsius | `F` |

*Refer to the [tz database time zones list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) to find your timezone string (e.g., `America/New_York`, `America/Chicago`, `America/Denver`, `America/Los_Angeles`).*

> [!NOTE]
> `clientId` and `clientSecret` are managed directly via PG3's OAuth setup (similar to TeslaEVstream). They are not required in Custom Configuration Parameters.

---

## First-Time Setup & Authentication

1. **Authenticate**: Click the **Authenticate** button on the NodeServer details page in the PG3 dashboard.
2. **Log In**: A browser window will open to the NuHeat login page. Sign into your My NuHeat account and grant access.
3. **Discovery**: Once authentication completes, the NodeServer will automatically discover your connected thermostats and create all device nodes in your Admin Console. You can also trigger discovery manually by clicking **Discover** on the Controller node.

---

## Thermostat Operating Mode

For the NodeServer to have full setpoint control without conflicting with built-in schedules:
1. On the physical thermostat screen, tap **Setup** → **Preferences**.
2. Tap **Operating Mode** at the bottom of the screen.
3. Change the selection from **Auto** to **Manual**.
4. *(Note: Manual mode disables internal cloud/app schedules so that your ISY/eisy programs have exclusive control).*

---

## Features & Discovered Nodes

The NodeServer automatically detects your account's preferred temperature scale (°F or °C) and creates the following nodes for each thermostat:

- **Controller Node**: Manages connection, authentication status, and discovery.
- **Thermostat Node (`°F` or `°C`)**:
  - Reports current floor temperature and target setpoint.
  - Reports heating status (idle / heating).
  - Set target heating temperature directly from programs and Admin Console.
- **Energy Log Nodes**:
  - **Energy Log - Day**: Daily power consumption (watt-hours).
  - **Energy Log - Week**: Weekly power consumption (watt-hours).
  - **Energy Log - Year**: Yearly power consumption (watt-hours).

---

## Polling

- **Short Poll (default 300s)**: Queries thermostat status, temperature, and heating activity.
- **Long Poll (default 1800s)**: Updates energy usage metrics.

---

## Limitations

- Internal thermostat scheduling is not edited through the NodeServer (use ISY programs instead).
- Mode changes (e.g. Away mode) are currently managed via the NuHeat app or physical thermostat.
