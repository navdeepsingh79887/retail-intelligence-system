# Retail Intelligence System
 
![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![ML](https://img.shields.io/badge/ML-RandomForest-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)
 
## Overview
 
An AI-powered Retail Intelligence System built for B.Tech Major Project at Sri Sri University. It integrates data engineering, machine learning, and automated decision mechanisms to support intelligent inventory management across six retail stores in East India.
 
The system handles a synthetic retail dataset of 21,000+ records across 12 tables, exposes 22 REST API endpoints, and uses a RandomForest model with 14 engineered features to forecast demand.
 
---
 
## System Architecture
 
The system follows an 8-layer architecture:
 
| Layer | Technology | Responsibility |
|-------|-----------|---------------|
| Infrastructure | Docker, Docker Compose | Container orchestration, networking |
| Data Engineering | Python, Pandas, SQLAlchemy | Data ingestion, cleaning, transformation |
| Database | PostgreSQL 15 | Data warehouse, relational integrity |
| API | FastAPI, SQLAlchemy Async | REST endpoints, request handling |
| Analytics | SQL, Python | Trend detection, demand spikes, festival analysis |
| Forecasting | RandomForest, Scikit-Learn | Demand prediction, feature engineering |
| Decision Engine | Python Business Logic | Restock decisions, stockout detection, expiry alerts |
| Agent | Python Automation | Supplier notifications, restock order generation |
 
---
 
## Features
 
- **Data Warehouse** — 11-table PostgreSQL schema (star schema design) with 21,000+ records
- **Data Ingestion Pipeline** — 12 dedicated ingestion scripts with cleaning, validation, and upsert
- **Trend Detection** — Category and store revenue trends with 5-level classification (SPIKE → CRASH)
- **Demand Spike Detection** — Z-score based anomaly detection with configurable threshold
- **Festival Analytics** — Upcoming festivals, top product recommendations, revenue uplift analysis
- **Taste Analysis** — Store preferences, seasonal mix, payment modes, customer type breakdown
- **ML Demand Forecasting** — RandomForest with 14 features (lag, rolling averages, weather, festival)
- **Decision Engine** — Restock, stockout, expiry, and margin decision endpoints
- **Automation Agents** — Restock agent, notification agent, supplier grouping agent
- **Multi-channel Notifications** — Email, SMS, Telegram, WhatsApp (configurable)
- **Dockerized** — Full Docker Compose setup with health checks and private networking
---
 
## Database Schema
 
12 tables following a retail data warehouse design:
 
| Table | Type | Records | Description |
|-------|------|---------|-------------|
| brand | Dimension | 64 | Product brands with country and active status |
| category | Dimension | 37 | Categories with self-referential parent hierarchy |
| supplier | Dimension | 65 | Suppliers with location and lead time |
| store | Dimension | 6 | Retail stores across East India |
| customer | Dimension | 935 | Customers with SHA256 phone hashes |
| date | Dimension | 365 | Full 2025 calendar with season and holiday flags |
| festival | Dimension | 34 | Indian festivals with demand multipliers |
| festival_products | Junction | 102 | Festival to product many-to-many links |
| external_factors | Fact | 365 | Daily weather and context flags |
| product | Dimension | 4999 | Full FMCG product catalog |
| inventory | Fact | 14206 | Daily stock levels per product per store |
| transaction | Fact | 1500 | Sales transactions Dec 2025 – Feb 2026 |
 
---
 
## ML Forecasting Model
 
**Algorithm:** RandomForest Regressor (100 estimators, max_depth=10)
 
**14 Features Used:**
 
| Feature | Type | Business Rationale |
|---------|------|--------------------|
| lag_7d_qty | Lag | Weekly demand cycle |
| lag_14d_qty | Lag | Bi-weekly pattern |
| lag_30d_qty | Lag | Monthly cycle |
| rolling_7d_avg | Rolling | Short-term trend |
| rolling_30d_avg | Rolling | Medium-term trend |
| day_of_week | Calendar | Weekday vs weekend |
| is_weekend | Calendar | Higher weekend footfall |
| season_code | Calendar | Seasonal demand variation |
| month_number | Calendar | Monthly seasonality |
| is_festival | External | Festival demand boost |
| is_public_holiday | External | Holiday footfall effect |
| temperature_c | Weather | Seasonal product demand |
| rainfall_mm | Weather | Store footfall impact |
| humidity_pct | Weather | Secondary weather signal |
 
**Evaluation Metrics:** MAE, RMSE, MAPE
 
---
 
## Project Structure
 
```
retail-intelligence-system/
├── app/
│   ├── main.py                  # FastAPI entry point
│   ├── core/                    # Config, DB, logging, security
│   ├── models/                  # SQLAlchemy ORM models (11 tables)
│   ├── schemas/                 # Pydantic validation schemas
│   ├── ingestion/               # 12 data ingestion scripts
│   ├── services/                # Core business logic
│   ├── analytics/               # Trend, festival, taste, spike detection
│   ├── forecasting/             # RandomForest pipeline
│   ├── decision_engine/         # Restock & pricing decisions
│   ├── agents/                  # Autonomous orchestration agents
│   ├── notifications/           # Email, SMS, Telegram, WhatsApp
│   ├── integrations/            # n8n, webhooks, supplier APIs
│   └── routes/                  # 22 API endpoints
├── scheduler/                   # Background job automation
├── tests/                       # Unit tests
├── scripts/                     # Seed data, reports, retraining
├── migrations/                  # Alembic DB migrations
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── docs/
│   └── screenshots/             # API output screenshots
├── .env.example                 # Environment variable template
├── requirements.txt
└── README.md
```
 
---
 
## API Endpoints (22 total)
 
| Router | Endpoint | Description |
|--------|----------|-------------|
| Health | `GET /health` | System health check |
| Analytics | `GET /api/analytics/trends/categories` | Category revenue trends |
| Analytics | `GET /api/analytics/trends/stores` | Store revenue trends |
| Analytics | `GET /api/analytics/spikes` | Z-score demand spike detection |
| Analytics | `GET /api/analytics/festivals/upcoming` | Upcoming festival alerts |
| Analytics | `GET /api/analytics/festivals/products` | Festival product recommendations |
| Analytics | `GET /api/analytics/taste` | Store taste profiling |
| Analytics | `GET /api/analytics/taste/seasonal` | Seasonal category revenue ranking |
| Forecast | `POST /api/forecast/train` | Train RandomForest model |
| Forecast | `GET /api/forecast/model-info` | Model metrics and feature importance |
| Forecast | `GET /api/forecast/predict` | Generate demand predictions |
| Forecast | `GET /api/forecast/top-products` | Top demand products |
| Decisions | `GET /api/decisions/restock` | Restock recommendations |
| Decisions | `GET /api/decisions/stockouts` | Stockout detection |
| Decisions | `GET /api/decisions/expiry-alerts` | Expiry alerts with discount action |
| Decisions | `GET /api/decisions/low-margin` | Low margin product detection |
| Agents | `POST /api/agents/restock/run` | Run restock agent (top N products) |
| Agents | `POST /api/agents/restock/notify` | Trigger restock notification agent |
| Agents | `POST /api/agents/expiry/notify` | Trigger expiry notification agent |
 
Full interactive docs at `http://localhost:8000/docs` (Swagger UI).
 
---
 
## Sample Outputs
 
All outputs below are from live API responses running via Docker on localhost.
 
---
 
### ML Forecasting
 
<p align="center">
  <table>
    <tr>
      <td align="center">
        <img src="docs/screenshots/01_model_info_api.png" width="480"/><br/>
        <b>Model Info — GET /api/forecast/model-info</b><br/>
        <sub>MAE: 1.085 | RMSE: 1.288 | Top feature: is_weekend (0.4164)</sub>
      </td>
      <td align="center">
        <img src="docs/screenshots/02_forecast_train_api.png" width="480"/><br/>
        <b>Forecast Train — POST /api/forecast/train</b><br/>
        <sub>Status: success | 14 features used | Model persisted to disk</sub>
      </td>
    </tr>
  </table>
</p>
---
 
### Inventory & Restock Agent
 
<p align="center">
  <table>
    <tr>
      <td align="center">
        <img src="docs/screenshots/03_inventory_restock_api.png" width="480"/><br/>
        <b>Inventory Restock — GET /api/decisions/restock</b><br/>
        <sub>🔴 CRITICAL | Tata Tea Gold | Stock: 257 | Reorder: 1170 | Deadline: 2026-04-28</sub>
      </td>
      <td align="center">
        <img src="docs/screenshots/04_restock_agent_run.png" width="480"/><br/>
        <b>Restock Agent Run — POST /api/agents/restock/run</b><br/>
        <sub>Store: BBS-01 | Orders: 10 | Critical: 10 | Value: ₹31,76,263.62</sub>
      </td>
    </tr>
    <tr>
      <td align="center">
        <img src="docs/screenshots/05_restock_notify_agent.png" width="480"/><br/>
        <b>Restock Notify — POST /api/agents/restock/notify</b><br/>
        <sub>44 products at risk | 50 orders | ₹1,01,66,375 | WhatsApp + Telegram</sub>
      </td>
      <td align="center">
        <img src="docs/screenshots/06_expiry_notify_agent.png" width="480"/><br/>
        <b>Expiry Notify — POST /api/agents/expiry/notify</b><br/>
        <sub>🔴 131 products expire in 7 days | ₹85,02,313 at risk | Discount: 40–50%</sub>
      </td>
    </tr>
  </table>
</p>
---
 
### Decision Engine
 
<p align="center">
  <table>
    <tr>
      <td align="center">
        <img src="docs/screenshots/07_decisions_low_margin.png" width="480"/><br/>
        <b>Low Margin — GET /api/decisions/low-margin</b><br/>
        <sub>🔴 Olive Oil | Margin: -106.94% | Selling below cost | Action: Renegotiate</sub>
      </td>
      <td align="center">
        <img src="docs/screenshots/08_decisions_expiry_alerts.png" width="480"/><br/>
        <b>Expiry Alerts — GET /api/decisions/expiry-alerts</b><br/>
        <sub>Liquid Detergent | 5 days left | Clearance: ₹113.3 | Discount: 45% | IMMEDIATE</sub>
      </td>
    </tr>
    <tr>
      <td colspan="2" align="center">
        <img src="docs/screenshots/09_decisions_stockouts.png" width="480"/><br/>
        <b>Stockout Detection — GET /api/decisions/stockouts</b><br/>
        <sub>Atta | BBS-01 | Stock: 22 | Safety stock: 30 | Supplier: Ms. Kavya Mehta | Lead: 5 days</sub>
      </td>
    </tr>
  </table>
</p>
---
 
### Analytics
 
<p align="center">
  <table>
    <tr>
      <td align="center">
        <img src="docs/screenshots/10_analytics_seasonal_1.png" width="480"/><br/>
        <b>Seasonal Analytics — GET /api/analytics/taste/seasonal</b><br/>
        <sub>Winter #1: Oils — 142 units | ₹1,10,656 | #2: Packaged Foods | #3: Cleaning</sub>
      </td>
      <td align="center">
        <img src="docs/screenshots/11_analytics_seasonal_2.png" width="480"/><br/>
        <b>Seasonal Analytics (continued)</b><br/>
        <sub>#4: Breakfast — 219 units | ₹59,719 | Seasonal demand ranking per category</sub>
      </td>
    </tr>
  </table>
</p>
---
 
## Setup & Run
 
### Using Docker (Recommended)
 
```bash
# 1. Clone the repo
git clone https://github.com/navdeepsingh79887/retail-intelligence-system.git
cd retail-intelligence-system
 
# 2. Copy env file and fill in your values
cp .env.example .env
 
# 3. Start all services
cd docker
docker-compose up --build
```
 
API live at: `http://localhost:8000`  
Swagger docs at: `http://localhost:8000/docs`
 
### Local Setup (Without Docker)
 
```bash
python -m venv venv
venv\Scripts\activate        # Windows
 
pip install -r requirements.txt
uvicorn app.main:app --reload
```
 
> Set `ENV=local` in your `.env` file for local PostgreSQL connection.
 
---
 
## Environment Variables
 
```bash
cp .env.example .env
```
 
| Variable | Description |
|----------|-------------|
| `ENV` | `docker` or `local` |
| `DATABASE_URL_LOCAL` | PostgreSQL URL for local setup |
| `DATABASE_URL_DOCKER` | PostgreSQL URL inside Docker |
 

 
---
 
## Tech Stack
 
| Layer | Technology |
|-------|-----------|
| API Framework | FastAPI + Uvicorn |
| Database | PostgreSQL 15 + SQLAlchemy |
| Migrations | Alembic |
| ML | Scikit-learn (RandomForest) + Joblib |
| Data Processing | Pandas + NumPy |
| Containerization | Docker + Docker Compose |
| Notifications | SMTP, Twilio, Telegram, WhatsApp |
| Automation | n8n Webhooks |
 
---
 
## Academic Details
 
| Field | Details |
|-------|---------|
| University | Sri Sri University, Cuttack, Odisha |
| Program | B.Tech Computer Science |
| Project Type | Major Project |
| Domain | Retail Intelligence, ML, Data Engineering |
 
---
 
## License
 
This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.