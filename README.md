# QWOP Python

## Running the Game

To start the Athletics.html file on a local server:

```bash
cd legacy && python3 -m http.server 8000
```

Then open your browser and navigate to `http://localhost:8000/Athletics.html`

## Behavior Matching (Python vs Reference)

Scripts in `scripts/` compare qwop-python with the qwop-wr reference env:

```bash
# Python-only (no browser)
python scripts/compare_trajectories.py --trace scripts/traces/basic_noop.json --python-only

# Full comparison (requires Chrome + chromedriver)
export CHROME_PATH=/path/to/chrome
export CHROMEDRIVER_PATH=/path/to/chromedriver
python scripts/compare_trajectories.py --trace scripts/traces/basic_noop.json
```

Generate traces: `python scripts/generate_trace.py --pattern noop -o scripts/traces/my_trace.json`

Run model on Python env (no browser):
```bash
cd /Users/b407404/qwop-python
python scripts/run_model_python.py /path/to/qwop-wr/data/DQNfD-Stage1-vzqtwzx4/model.zip -o scripts/traces/dqnfd_python_trace.json --seed 42
```

Record from trained agent (Python 3.10+, Chrome + chromedriver):
```bash
cd /path/to/qwop-wr
python3.10 /path/to/qwop-python/scripts/record_agent_trace.py data/DQNfD-Stage1-vzqtwzx4/model.zip -o ../qwop-python/scripts/traces/dqnfd_trace.json --seed 42
```
