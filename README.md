# Real-Time Quant Analytics Platform

A high-performance, local quant trading dashboard for real-time statistical arbitrage monitoring.
Built with Python, Streamlit, SQLite, and AsyncIO.

## 🚀 Quick Start

1.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the Dashboard**
    ```bash
    streamlit run app.py
    ```
    *The application will automatically connect to Binance Futures WebSocket, normalize ticks, and begin computing live analytics.*

## 🏗️ Architecture

The system is designed as a Producer-Consumer application with a shared state manager.
![Architecture  Diagram](/architeture.png)

### Components
1.  **Ingestion (`src/ingestion.py`)**: AsyncIO client connecting to `wss://fstream.binance.com`. Handles connection resilience.
2.  **Stream Manager (`src/stream_manager.py`)**: Singleton orchestrator. Runs the background ingestion thread. Maintains `deque` ring buffers for Ticks (last 2000) and Bars (last 24hrs) to ensure O(1) access for the UI.
3.  **Resampler (`src/resampling.py`)**: Aggregates ticks into 1s, 1m, 5m bars, aligning to clock boundaries.
4.  **Database (`src/database.py`)**: Zero-config SQLite storage. Persists all raw ticks and consolidated bars for historical analysis.
5.  **Analytics (`src/analytics.py`)**: Numba/Pandas optimized math for Z-Score, OLS Hedge Ratio, and ADF Stationarity tests.

## 🧮 Analytics Methodology

### Spread & Z-Score
We use a standard cointegration approach:
$$ Spread_t = Price_{1,t} - \beta \times Price_{2,t} $$
$$ Z_t = \frac{Spread_t - \mu_{spread}}{\sigma_{spread}} $$

Where $\mu$ and $\sigma$ are rolling mean/std over the defined window (default 20).

### OLS Hedge Ratio
When enabled, $\beta$ is dynamically calculated using Ordinary Least Squares on the rolling window:
$$ Y = \beta X + \alpha + \epsilon $$

### Stationarity (ADF)
The Augmented Dickey-Fuller test checks if the spread is mean-reverting (Stationary). A p-value < 0.05 suggests a valid arb opportunity.

## ⚖️ Design Trade-offs

*   **SQLite vs TimescaleDB**: SQLite was chosen for portability and zero setup. For high-frequency production, TimescaleDB or KDB+ would be preferred.
*   **Streamlit vs React**: Streamlit allows rapid prototyping of data apps in pure Python. The trade-off is the "rerun" model which can feel clunky compared to a reactive JS frontend, but we mitigated this with high-frequency polling.
*   **In-Memory vs DB Reads**: We cache active windows in RAM (`deque`). Reading from SQLite for every UI update would introduce unacceptable IO latency.

## 🔮 Scaling & Future Work

To scale this to 100+ pairs or HFT speeds:
1.  **Separate Processes**: Decouple Ingestion from Dashboard using Redis Pub/Sub or ZeroMQ.
2.  **Faster Storage**: Move `ticks` to QuestDB or partitioned Parquet files.
3.  **Event-Driven**: Replace polling with Websockets to the frontend (FastAPI + React).

---
*Built by Rushabh Rode*
