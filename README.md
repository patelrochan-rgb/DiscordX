# @DeItaone → Discord (free scheduled monitor)

This is a small GitHub Actions project that polls the FxEmbed/FxTwitter RSS feed every five minutes and forwards new feed entries to a Discord webhook.

## Important limitations

- **Not guaranteed real-time:** GitHub scheduled workflows can be delayed. Five minutes is the minimum supported schedule interval, not a guaranteed delivery SLA.
- **Third-party feed dependency:** This uses `https://fxtwitter.com/DeItaone/feed.xml`, not the official X API. The feed can change, be rate-limited, become unavailable, or stop returning recent posts.
- **Original-post filtering is best-effort:** The feed documentation says timeline feeds may include originals and reposts. This script skips entries only when the feed explicitly marks them as replies/reposts, or the text begins with `RT @`. If the feed does not expose a reply/repost marker, it cannot reliably distinguish every reply or repost. Verify the feed format before relying on the filter.
- **Public repository:** Do not put the Discord webhook URL in any file. It is stored as a GitHub Actions secret. `state.json` contains only a post ID and is committed to the public repository.
- **Free-tier conditions:** GitHub documents standard GitHub-hosted runner usage as free for public repositories. This setup is designed to use a short standard Ubuntu job.

## Setup

### 1. Create a Discord webhook

1. Open Discord and go to the target channel.
2. Select **Edit Channel → Integrations → Webhooks**.
3. Select **New Webhook**, give it a name such as `X Alerts`, and choose the target channel.
4. Select **Copy Webhook URL**.
5. Keep the URL private. Anyone who has it can post to that channel.

### 2. Create a public GitHub repository

1. Sign in at https://github.com/.
2. Select **New repository**.
3. Name it `deitaone-discord-monitor`.
4. Choose **Public**.
5. Create the repository. Do not add a README or other files if you are uploading this package as-is.

### 3. Upload the project files

Upload these files and preserve the folder structure:

```text
deitaone-discord-monitor/
├── .github/
│   └── workflows/
│       └── monitor.yml
├── monitor.py
└── state.json   (created automatically after the first run)
```

The ZIP contains `monitor.py` and `.github/workflows/monitor.yml`. GitHub will create `state.json` after the first successful baseline run.

### 4. Add the webhook as a GitHub secret

1. In your repository, open **Settings → Secrets and variables → Actions**.
2. Select **New repository secret**.
3. Name: `DISCORD_WEBHOOK_URL`
4. Secret: paste the Discord webhook URL.
5. Save.

Never commit the webhook URL to the repository or paste it into a public issue.

### 5. Enable Actions write access

1. Open **Settings → Actions → General**.
2. Under **Workflow permissions**, choose **Read and write permissions**.
3. Save.

This lets the workflow commit the last-seen post ID to `state.json`, preventing duplicate alerts.

### 6. Enable and run the workflow

1. Open the **Actions** tab.
2. If GitHub asks, enable workflows.
3. Select **Monitor DeItaone and forward original posts**.
4. Select **Run workflow** once.
5. The first run only records the newest item as a baseline; it does not send old posts.
6. Check the run log. Later scheduled runs check for new entries every five minutes.

### 7. Test safely

The easiest test is to wait for a new post by the monitored account and inspect the Actions run and Discord channel. You can also temporarily change the baseline behavior in `monitor.py` for a controlled test, but restore it afterwards.

## Changing the account

Edit `X_HANDLE: DeItaone` in `.github/workflows/monitor.yml` and replace it with the handle without `@`.

## Troubleshooting

- **No workflow runs:** Check that the workflow file is on the repository's default branch and Actions are enabled.
- **Push rejected:** Recheck Settings → Actions → General → Workflow permissions → Read and write permissions.
- **Discord receives nothing:** Recreate the webhook and update the repository secret. Never print the secret in logs.
- **Feed fetch fails:** Open `https://fxtwitter.com/DeItaone/feed.xml` in a browser. If it no longer loads, the third-party feed is unavailable; this is not an X-official service.
- **Duplicates:** Check that `state.json` is being committed and the workflow has write permission.
- **Missed posts:** The feed may only expose a limited recent window; a long outage can cause missed entries.

## Sources

- GitHub schedule syntax: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub Actions billing: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- FxEmbed RSS/Atom feed guide: https://docs.fxembed.com/guide/advanced/rss-atom-feeds/
