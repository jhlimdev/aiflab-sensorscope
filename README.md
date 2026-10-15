# Real-Time Anomaly Detection and Monitoring System Based on Industrial Equipment Sensor Data

## Overview

**AIFLab SensorScope** is an open-source application for monitoring temperature, vibration, and current from industrial equipment sensors. It includes a three-machine sensor simulator, a FastAPI service, a Chart.js dashboard, and SQLite storage for measurements and anomaly events.

Anomalies are detected using absolute z-scores against a fixed baseline estimated from separate synthetic reference data. The included demo uses synthetic data for research and education; performance on physical industrial equipment has not been evaluated.

## Software requirements

### Hardware requirements

A standard computer and a web browser are sufficient for the included demo. A GPU and physical sensors are not required.

### Software requirements

- Python 3.12 or later
- Tested on macOS with Python 3.12 and Linux CI with Python 3.12/3.13
- Docker with Compose v2, if using the container setup

### Python dependencies

The main dependencies are listed below. All runtime versions are pinned in [requirements.txt](requirements.txt).

```text
FastAPI == 0.143.1
Uvicorn == 0.54.0
Pydantic == 2.14.1
```

## Installation guide

Run the following commands on macOS or Linux:

```bash
git clone https://github.com/jhlimdev/aiflab-sensorscope.git
cd aiflab-sensorscope
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows setup and additional configuration are described in the [Korean user guide](docs/USER_GUIDE.ko.md).

## Demo and instructions for use

Start the server from the repository folder:

```bash
python -m uvicorn sensorscope.main:app --host 127.0.0.1 --port 8000
```

Alternatively, run `docker compose up --build -d --wait` with Docker.

Open <http://127.0.0.1:8000> in a browser. Select a machine and sensor, then click **이상 주입** to introduce a temporary change. The dashboard updates every second and displays detected anomalies in the event log. Records are retained in SQLite across server restarts.

Example JSON and CSV inputs are available in [examples/](examples/). To submit them through the API, disable the simulator with `SS_SIMULATOR=false`; see the [user guide](docs/USER_GUIDE.ko.md) for the full procedure. API documentation is available at <http://127.0.0.1:8000/docs> while the server is running.

[Dashboard screenshot](docs/images/dashboard.png) · [Test and verification results](docs/VERIFICATION.md)

## License

Released under the [MIT License](LICENSE). Bundled library notices are provided in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
