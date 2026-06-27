# Fix Manual

## 1. Ollama — pull Qwythos 9B (Q8_0 GGUF)

Source: https://huggingface.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF

Ollama pulls HuggingFace GGUF directly with the `hf.co/<repo>:<quant>` ref.
Quant tag = the `Q8_0` file variant.

```bash
ollama pull hf.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF:Q8_0
```

Verify:

```bash
ollama list
ollama run hf.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF:Q8_0
```

Notes:
- Size ~9.8 GB (Q8_0). Needs ~10 GB free + RAM/VRAM for 9B at 8-bit (~10–12 GB).
- To use in expense stack, set in `.env`:
  `MODEL_NAME=hf.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF:Q8_0`

---

## 2. Docker — "network ... not found" on `docker compose up`

### Error

```
Error response from daemon: failed to set up container networking:
network e6e0963edc5a2b6793601919e1c8a7c1a4b759dd38176e373a11ea02b2f06ac5 not found
```

### Cause

Stale containers held a reference to an old `expense_default` network ID that
no longer exists (network was deleted/recreated out of band). Compose tried to
attach containers to the dead network ID instead of the current one.

- Old (dead) net referenced by containers: `e6e0963e…`
- Current `expense_default` net: `0c9e4a29…`

### Fix

Tear down stale containers + network, then bring up fresh:

```bash
cd /Users/rapepong/Development/personal/invest/expense
docker compose down --remove-orphans
docker compose up -d
```

`down` removes the containers bound to the dead network and drops the stale
network; `up` recreates a clean `expense_default` and reattaches.

### Verify

```bash
docker compose ps          # backend + frontend = Up
docker network ls          # expense_default present
```

### If it recurs

```bash
docker compose down --remove-orphans
docker network prune -f    # clear orphaned networks
docker compose up -d
```

Hard reset (last resort — drops volumes/data):

```bash
docker compose down -v
docker compose up -d --force-recreate
```
