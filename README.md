# US Stock Target Monitor - Streamlit

## Files
- `stock_monitor_web.py` - Streamlit web dashboard
- `watchlist.csv` - symbols and Entry / Breakout targets
- `requirements.txt` - Python packages for Streamlit Community Cloud

## watchlist.csv format
```csv
symbol,name,entry_price,breakout_price
NVDA,NVIDIA,180,205
TSLA,Tesla,400,480
```
A blank Entry or Breakout value is allowed; the symbol will simply be omitted from that panel.

## Deploy on Streamlit Community Cloud
1. Create a GitHub repository (private is fine if your Streamlit account can access it).
2. Upload these four files to the repository root.
3. Sign in to Streamlit Community Cloud with GitHub.
4. Create a new app and select the repository and `main` branch.
5. Set the main file path to `stock_monitor_web.py`.
6. Deploy. Streamlit will install `requirements.txt` automatically.
7. Open the generated `*.streamlit.app` URL on your phone.

## Local test
```bash
pip install -r requirements.txt
streamlit run stock_monitor_web.py
```

## Current behavior
- Auto refresh: 30 seconds
- Entry: distance sorted low to high
- Breakout / Exit: distance sorted high to low
- Entry colors: FAR `#46390D`, NEAR `#79770E`, TRIGGERED `#E02828`
- Breakout triggered: `#098105`
- Responsive layout: two columns on desktop, Streamlit stacks columns on narrow/mobile displays
- Alert log: detects target crossings while the browser session is active

## Important
This first cloud version is a dashboard, not a 24/7 background alert service. Streamlit Community Cloud apps may sleep when unused, and browser-session alert history is not permanent. A later version can add persistent storage and phone push notifications.
