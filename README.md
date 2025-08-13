# twse-daily-csv

Fetch Taiwan Stock Exchange (TWSE) daily trading data (JSON API) and consolidate it into past N-year `Date,Close` CSV files.

## Features
- Support downloading multiple stock symbols in one run
- Automatically handle ROC year to Gregorian year conversion
- Robust to field name changes (e.g., "收盤價" variations)
- Default lookback is 10 years, configurable via CLI
- Retry on request failures and SSL fallback support
- Polite request intervals to avoid overloading TWSE servers

## Installation
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```bash
# Default run (0050, 00830, 00670L, last 10 years)
python twse_to_csv.py

# Specify symbols and lookback years
python twse_to_csv.py --symbols 2330 0050 --years 5
```

## Output

* Each symbol will produce a CSV named `{symbol}.csv`
* CSV columns:

```
Date,Close
2020-01-02,123.45
2020-01-03,125.67
...
```

## License

MIT License
