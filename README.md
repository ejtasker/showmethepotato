# MMX Facts 🥔

A Bluesky bot that shares facts about JAXA's MMX (Martian Moons eXploration) mission.

- **Every day** at about 09:00 Japan time, it posts a random fact.
- **Every 20 minutes**, it looks for posts saying **"show me the potato!"** or
  **"feed my Phobos-ia"**, and for posts that tag the bot, and replies to each with a fact.

It runs for free on GitHub. You don't need to keep a computer switched on.

---

## What's in this folder

| File | What it is | Do you edit it? |
|---|---|---|
| `facts.yaml` | The fact list, plus the greetings the bot uses when replying | **Yes**, this is yours |
| `images/` | Pictures for your facts | **Yes**, add pictures here |
| `bot.py` | The bot itself | No |
| `state.json` | The bot's memory of who it has replied to | No, the bot updates it |
| `requirements.txt` | The software the bot needs | No |
| `.github/workflows/` | The schedule that runs the bot | Only to change the timing |

---

## Setting it up (about 30 minutes, one time only)

### 1. Make the bot's Bluesky account

1. Sign out of Bluesky (or use a private browser window) and create a new account,
   e.g. `mmxfacts.bsky.social`.
2. Give it a profile picture, and a bio that says it's a bot and who runs it, e.g.
   *"🤖 Automated facts about JAXA's MMX mission to Phobos. Say "show me the potato!"
   or "feed my Phobos-ia" for a fact. Run by @yourhandle."*
3. Go to **Settings → Privacy and security → App passwords → Add app password**.
   Name it "GitHub bot" and copy the password it shows you (it looks like
   `abcd-efgh-ijkl-mnop`). You'll only see it once.

Never give the bot your normal password. If anything ever goes wrong, you can delete
the app password and the bot is locked out instantly.

### 2. Make a GitHub account and repository

1. Sign up at [github.com](https://github.com) if you don't have an account.
2. Click **+** (top right) → **New repository**.
3. Name it `mmxfacts`. Choose **Public**: GitHub's scheduled jobs are free and unlimited
   for public repositories. (Your password stays private either way; see step 3.)
4. Tick **Add a README file** and click **Create repository**.

### 3. Store the login details as secrets

1. In your new repository, go to **Settings → Secrets and variables → Actions**.
2. Click **New repository secret** and add:
   - Name `BSKY_HANDLE`, value `mmxfacts.bsky.social` (your bot's handle)
3. Click **New repository secret** again and add:
   - Name `BSKY_APP_PASSWORD`, value the app password from step 1

Secrets are encrypted. Nobody, including you, can read them back, even in a public repository.

### 4. Upload the bot's files

1. In the repository, click **Add file → Upload files**.
2. Drag in **everything in this folder**, including the hidden `.github` folder.
   - On a Mac, press **Cmd + Shift + .** in Finder to show hidden folders.
   - On Windows, tick **View → Hidden items** in File Explorer.
3. Click **Commit changes**.

Check that `.github/workflows/bot.yml` appears in your repository. If the `.github`
folder didn't upload, create it by hand: **Add file → Create new file**, type
`.github/workflows/bot.yml` as the name (the slashes make the folders), and paste
in the contents. Do the same for `check-facts.yml`.

### 5. Let the bot save its memory

Go to **Settings → Actions → General → Workflow permissions**, choose
**Read and write permissions**, and click **Save**. This lets the bot update
`state.json` so it never replies to the same post twice.

### 6. Test it

1. Go to the **Actions** tab. If GitHub asks, click to enable workflows.
2. Click **MMX Facts bot** on the left, then **Run workflow**.
3. Choose mode **post**, tick **Dry run**, and click the green button.
4. When it finishes (about a minute), click on the run, then **run → Run the bot**.
   You'll see the post it *would* have made.
5. Happy? Run it again with **Dry run** unticked. Your bot's first post is live! 🎉

To test replies, post "show me the potato!" from your own account, then run the
workflow with mode **replies**. Or just wait up to 20 minutes.

---

## Adding facts

Open `facts.yaml` on GitHub, click the ✏️ pencil icon, and add a new block:

```yaml
  - text: "Your new fact goes here."
```

With a link:

```yaml
  - text: "MMX is led by JAXA."
    link: https://www.mmx.jaxa.jp/en/
```

With a picture:

1. Upload the picture into the `images` folder (**Add file → Upload files**,
   then open the `images` folder first).
2. Add the fact:

```yaml
  - text: "This is what Phobos looks like up close."
    image: images/phobos.jpg
    alt: "A grey, lumpy moon covered in craters"
```

Click **Commit changes**. The **Check facts** job runs automatically. A green ✅ in the
Actions tab means all is well; a red ❌ means something needs fixing (click it to see
what, e.g. a fact that's too long or an image name with a typo).

**Tips**

- The whole post, including the link, must be under 300 characters.
- Line up `link`, `image` and `alt` exactly under `text`. Spacing matters.
- If your fact contains a colon (:) or #, keep the "double quotes" around it.
- Big pictures are shrunk automatically to fit Bluesky's limit.
- Check the image's licence. NASA images are generally public domain; JAXA's
  images have their own usage terms.
- The bot avoids repeating facts it has used recently, so a longer list means more variety.

You can also edit the greetings at the top of `facts.yaml`, e.g. add a new
line under `potato:` for another way to say "here's your potato".

---

## Changing the timing

Edit `.github/workflows/bot.yml`. The two `cron` lines control the schedule, in UTC
(Japan time minus 9 hours):

```yaml
    - cron: "7 0 * * *"      # daily fact at 09:07 Japan time
    - cron: "*/20 * * * *"   # replies every 20 minutes
```

- Twice a day (09:07 and 21:07 Japan time): `"7 0,12 * * *"`.
- If you change the daily line, change the matching `"7 0 * * *"` further down the
  file too, so the bot knows which schedule means "post a fact".

GitHub's schedules aren't exact; runs can be 5 to 15 minutes late at busy times.

---

## Good to know

- **Pausing the bot:** Actions tab → MMX Facts bot → **⋯** → **Disable workflow**.
- **Inactivity:** GitHub pauses schedules in repositories with no activity for 60 days.
  Adding a fact now and then keeps it awake. If it does pause, GitHub emails you and
  you can switch it back on in the Actions tab.
- **Safety limits:** the bot replies to at most 10 posts per run, only once per person
  per run, never to posts more than 2 days old, and never to its own posts.
- **Tags:** any post that @-mentions the bot gets a fact in reply.
