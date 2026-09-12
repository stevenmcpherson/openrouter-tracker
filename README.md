# OpenRouter Tracker

A macOS menu bar app that tracks your [OpenRouter](https://openrouter.ai) API credit balance and per-key usage in real time.

## What It Shows

- **Menu bar:** Remaining account credits (e.g., `OR $42.50`) with color-coded status
- **Dropdown table:** All API keys with daily spend, remaining balance, monthly limit, and all-time usage
- **Per-key progress bars** with color indicators (🟢 <50%, 🟡 50-80%, 🔴 >80%)
- **Account-wide balance** with progress bar at the bottom

```
   Key                  Daily      Rem      Limit   All-time
🟢  project-alpha        $0.00   $30.00     $30.00      $0.78
🟢  chatbot-dev          $0.00   $30.00     $30.00      $0.00
🟢  production-api       $0.00  $199.75    $200.00      $5.86
🟡  research-bot         $0.00    $9.82     $10.00      $3.17
🔴  main-app             $1.06  $299.01    $300.00    $219.46

✅  Balance  $42.50
████████████████████░░░░░  91% used of $500.00
```

## How It Works

The app uses an OpenRouter **provisioning key** to auto-discover all API keys on your account via `GET /api/v1/keys`. One call gets every key's usage, limit, and monthly spend. A second call to `GET /api/v1/credits` gets the account-wide balance.

Snapshots are stored in a local SQLite database (`~/.openrouter-tracker/usage.db`) for future trend analysis.

## Setup

### 1. Install rumps

```bash
pip install rumps
```

### 2. Get a provisioning key

1. Go to [https://openrouter.ai/keys](https://openrouter.ai/keys)
2. Click **Create Key**
3. Select **Provisioning Key** (not a regular API key)
4. Name it whatever you like
5. Copy the key

### 3. Configure

```bash
mkdir -p ~/.openrouter-tracker
cat > ~/.openrouter-tracker/config.json << 'EOF'
{
  "poll_interval_seconds": 300,
  "low_credit_threshold": 10.0,
  "provisioning_key": "sk-or-v1-your-provisioning-key-here"
}
EOF
```

### 4. Run

```bash
git clone https://github.com/stevenmcpherson/openrouter-tracker.git
cd openrouter-tracker
python3 tracker.py
```

You should see `OR $XX.XX` appear in your menu bar.

## Configuration

`~/.openrouter-tracker/config.json`:

| Field | Default | Description |
|---|---|---|
| `poll_interval_seconds` | 300 | How often to refresh (5 minutes) |
| `low_credit_threshold` | 10.0 | Dollar amount that triggers red status |
| `provisioning_key` | "" | OpenRouter provisioning key for key auto-discovery |

## Menu Bar Status Indicators

| Icon | Meaning |
|---|---|
| `OR $42.50` | Normal — credits above 3× threshold |
| `OR 🟡 $9.50` | Warning — credits between threshold and 3× threshold |
| `OR 🔴 $4.00` | Critical — credits at or below threshold |

## Files

```
openrouter-tracker/
├── tracker.py          # Menu bar app (rumps) — UI, timer, menu rendering
├── api_client.py       # OpenRouter API calls (credits, key listing)
├── config.py           # Config + key management
├── storage.py          # SQLite snapshot storage for trend history
├── requirements.txt    # rumps
└── README.md
```

App data is stored in `~/.openrouter-tracker/`:

| File | Purpose |
|---|---|
| `config.json` | Provisioning key, poll interval, thresholds |
| `usage.db` | SQLite snapshots (auto-pruned after 90 days) |

## Requirements

- macOS (uses NSStatusBar via rumps)
- Python 3.8+
- `pip install rumps`

## License

MIT
