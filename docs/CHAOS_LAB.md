# Fake Provider Chaos Lab

Use the fake provider to test routing behavior without AMD or Fireworks credits.

## Help

```bash
python3 -m router.dev.fake_provider --help
```

## Local happy path

```bash
python3 -m router.dev.fake_provider --port 8000 --response "4"
```

Then:

```bash
ROUTER_MODE=local \
LOCAL_BASE_URL=http://127.0.0.1:8000/v1 \
LOCAL_MODEL=fake-local \
python3 -m router ask "What is 2+2?"
```

## Hybrid with fake Fireworks

Terminal 1:

```bash
python3 -m router.dev.fake_provider --port 8000 --responses-file local-sequence.txt
```

Terminal 2:

```bash
python3 -m router.dev.fake_provider --port 8001 --scenario fireworks-approve
```

Terminal 3:

```bash
ROUTER_MODE=hybrid \
LOCAL_BASE_URL=http://127.0.0.1:8000/v1 \
LOCAL_MODEL=fake-local \
FIREWORKS_BASE_URL=http://127.0.0.1:8001/v1 \
FIREWORKS_MODEL=fake-fireworks \
FIREWORKS_API_KEY=fake-key \
python3 -m router ask "What is 2+2?" --json
```

## Chaos profiles

- Slow provider: `--delay-s 3`
- HTTP failure: `--status 500`
- Invalid JSON: `--invalid-json`
- High token usage: `--prompt-tokens 1000 --completion-tokens 400`
- Fireworks approve: `--scenario fireworks-approve`
- Fireworks replace: `--scenario fireworks-replace`

## Safety

The fake provider never needs real API keys. Use placeholder values only.
