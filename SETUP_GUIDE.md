# Complete Setup Guide for Chibi Discord Bot

**A step-by-step guide for beginners with no prior experience**

This guide will walk you through setting up Chibi, an AI-powered Discord quiz bot with Google Sheets integration, from scratch. No prior knowledge of Discord bots or Google Cloud required!

## 📋 Table of Contents

1. [What You'll Need](#what-youll-need)
2. [Part 1: Discord Bot Setup](#part-1-discord-bot-setup)
3. [Part 2: Google Cloud Setup](#part-2-google-cloud-setup)
4. [Part 3: Local Setup](#part-3-local-setup)
5. [Part 4: First Run](#part-4-first-run)
6. [Part 5: Testing](#part-5-testing)
7. [Troubleshooting](#troubleshooting)

---

## What You'll Need

Before starting, make sure you have:

- [ ] A computer with macOS, Linux, or Windows
- [ ] Internet connection
- [ ] A Discord account (free)
- [ ] A Google account (free)
- [ ] About 30-45 minutes of time

**Technical requirements:**
- Python 3.10 or higher
- Basic familiarity with running terminal/command line commands
- A text editor (VS Code, Sublime Text, or any editor you prefer)

---

## Part 1: Discord Bot Setup

### What is a Discord Bot?

A Discord bot is a program that can automatically respond to messages, manage channels, and interact with users in a Discord server. Think of it as a helpful assistant that lives in your Discord server.

### Step 1.1: Create a Discord Application

1. **Go to Discord Developer Portal**
   - Open your web browser
   - Visit: https://discord.com/developers/applications
   - Click the blue **"New Application"** button in the top-right corner

2. **Name Your Application**
   - Enter a name (e.g., "Chibi Bot" or "Quiz Bot")
   - Check the box to agree to Discord's Terms of Service
   - Click **"Create"**

3. **Find Your Application ID** (optional, for reference)
   - You'll see your application dashboard
   - Copy the "APPLICATION ID" shown under your app name (you won't need this now, but keep track of it)

### Step 1.2: Create the Bot User

1. **Go to the Bot Section**
   - On the left sidebar, click **"Bot"**
   - Click the **"Add Bot"** button
   - Click **"Yes, do it!"** to confirm

2. **Get Your Bot Token** (IMPORTANT!)
   - Under the bot's username, you'll see **"TOKEN"**
   - Click **"Reset Token"** (or "Copy" if you see it)
   - Click **"Yes, do it!"** to confirm
   - **COPY THIS TOKEN** and save it somewhere safe (like a password manager)
   - ⚠️ **NEVER share this token publicly!** It's like a password for your bot

3. **Enable Important Bot Settings**
   - Scroll down to **"Privileged Gateway Intents"**
   - Toggle ON the following:
     - ✅ **PRESENCE INTENT**
     - ✅ **SERVER MEMBERS INTENT**
     - ✅ **MESSAGE CONTENT INTENT**
   - These allow your bot to read messages and user information
   - Click **"Save Changes"** at the bottom

### Step 1.3: Invite the Bot to Your Server

1. **Generate an Invite Link**
   - On the left sidebar, click **"OAuth2"** → **"URL Generator"**
   - Under **"SCOPES"**, check:
     - ✅ `bot`
     - ✅ `applications.commands`
   - Under **"BOT PERMISSIONS"**, check these at minimum:
     - ✅ Read Messages/View Channels
     - ✅ Send Messages
     - ✅ Manage Messages
     - ✅ Embed Links
     - ✅ Attach Files
     - ✅ Read Message History
     - ✅ Add Reactions
     - ✅ Use Slash Commands
   - Scroll down and **copy the generated URL**

2. **Invite the Bot**
   - Paste the URL in your browser
   - Select the Discord server where you want to add the bot
   - Click **"Authorize"**
   - Complete the CAPTCHA if prompted
   - You should see a confirmation that the bot joined your server!

3. **Find Your Server and Channel IDs**

   **First, enable Developer Mode in Discord:**
   - Open Discord (desktop app or browser)
   - Click the ⚙️ gear icon (User Settings) at the bottom left
   - Scroll down to **"Advanced"** in the left sidebar
   - Toggle on **"Developer Mode"**
   - Close the settings

   **Now you can copy IDs by right-clicking:**

   **Server ID** (optional, not needed for bot):
   - Right-click on your server name in the left sidebar
   - Click **"Copy Server ID"** at the bottom
   - Paste it somewhere safe (e.g., a notepad)

   **Admin Channel ID** (where attendance codes are displayed):
   - Right-click on the channel you want for admin commands
   - Click **"Copy Channel ID"**
   - Save this - you'll use it as `ADMIN_CHANNEL_ID` in `.env`
   - **Tip**: Create a private channel called `#admin-bot` for this

   **Attendance Channel ID** (where students submit `/here` codes):
   - Right-click on the channel where students should submit attendance
   - Click **"Copy Channel ID"**
   - Save this - you'll use it as `ATTENDANCE_CHANNEL_ID` in `.env`
   - **Tip**: Use a public channel like `#attendance` or `#general`

   **What do these IDs look like?**
   - Channel IDs are long numbers like: `123456789012345678`
   - If you see something like that, you did it right!

---

## Part 2: Google Cloud Setup

### What is Google Cloud?

Google Cloud is Google's platform for running applications and storing data. We'll use it to allow the bot to export quiz data to Google Sheets (like Excel, but online).

### Step 2.1: Create a Google Cloud Project

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/
   - Sign in with your Google account

2. **Create a New Project**
   - At the top of the page, click the project dropdown (says "Select a project")
   - Click **"New Project"**
   - Enter a project name (e.g., "Chibi Bot")
   - Click **"Create"**
   - Wait for the project to be created (takes ~30 seconds)
   - Select your new project from the dropdown

### Step 2.2: Enable Required APIs

**What are APIs?** APIs are like doorways that let your bot communicate with Google Sheets and Google Drive.

1. **Enable Google Sheets API**
   - In the search bar at the top, type "Google Sheets API"
   - Click on **"Google Sheets API"** in the results
   - Click the blue **"ENABLE"** button
   - Wait for it to enable (~10 seconds)

2. **Enable Google Drive API**
   - Click the back arrow or search again
   - Search for "Google Drive API"
   - Click on **"Google Drive API"**
   - Click the blue **"ENABLE"** button
   - Wait for it to enable

3. **Wait for Changes to Propagate**
   - After enabling both APIs, wait **1-2 minutes**
   - This gives Google time to activate everything

### Step 2.3: Create OAuth Credentials

**What is OAuth?** OAuth is a secure way for the bot to access your Google account without knowing your password. You'll grant permission once, and the bot can then access Google Sheets on your behalf.

1. **Go to Credentials Page**
   - In the left sidebar, click **"APIs & Services"** → **"Credentials"**
   - Or search for "Credentials" in the top search bar

2. **Configure OAuth Consent Screen** (Required first time)
   - Click **"CONFIGURE CONSENT SCREEN"**
   - Choose **"External"** (this is fine for personal use)
   - Click **"CREATE"**

   Fill in the form:
   - **App name**: Chibi Bot
   - **User support email**: Your email address
   - **Developer contact email**: Your email address
   - Leave everything else blank
   - Click **"SAVE AND CONTINUE"**

   Skip the next screens:
   - **Scopes**: Click **"SAVE AND CONTINUE"**
   - **Test users**: Click **"SAVE AND CONTINUE"**
   - **Summary**: Click **"BACK TO DASHBOARD"**

3. **Create OAuth Client ID**
   - Go back to **"Credentials"** in the left sidebar
   - Click **"+ CREATE CREDENTIALS"** at the top
   - Select **"OAuth client ID"**

   Configure the OAuth client:
   - **Application type**: Select **"Desktop app"**
   - **Name**: Chibi Bot (or any name)
   - Click **"CREATE"**

4. **Download Credentials**
   - A popup appears with your client ID and secret
   - Click **"DOWNLOAD JSON"** (the download icon)
   - Save this file - you'll need it soon!
   - Click **"OK"** to close the popup

---

## Part 3: Local Setup

### Step 3.1: Install Prerequisites

1. **Install Python** (if not already installed)
   - Check if you have Python: Open Terminal/Command Prompt and run:
     ```bash
     python3 --version
     ```
   - If you see "Python 3.10" or higher, you're good!
   - If not, download from: https://www.python.org/downloads/
   - Install and verify again

2. **Install Git** (if not already installed)
   - Check if you have Git:
     ```bash
     git --version
     ```
   - If not, download from: https://git-scm.com/downloads

### Step 3.2: Clone the Repository

**What is cloning?** Cloning means downloading a copy of the code from the internet to your computer.

1. **Open Terminal/Command Prompt**
   - macOS: Press `Cmd + Space`, type "Terminal", press Enter
   - Windows: Press `Win + R`, type "cmd", press Enter

2. **Navigate to Where You Want the Project**
   ```bash
   cd ~/Documents  # or wherever you want to put the project
   ```

3. **Clone the Main Repository**
   ```bash
   git clone https://github.com/skojaku/discord-qa-agent.git
   cd discord-qa-agent
   ```

4. **Clone the Required Sub-repository**
   ```bash
   git clone https://github.com/skojaku/llm-quiz.git
   ```

### Step 3.3: Install Python Dependencies

**What are dependencies?** These are other pieces of software that the bot needs to run.

```bash
uv pip install -r requirements.txt
```

This will take 2-5 minutes. You'll see a lot of text scroll by - this is normal!

**Note:** We're using `uv` instead of plain `pip` because it's much faster and handles dependencies better.

### Step 3.4: Set Up Credentials

1. **Copy the OAuth Credentials File**
   - Remember the JSON file you downloaded from Google Cloud?
   - Rename it to: `google_oauth_credentials.json`
   - Move it into the `credentials/` folder in your project

2. **Create Environment File**
   - In the project root, copy the example file:
     ```bash
     cp .env.example .env
     ```
   - Open `.env` in your text editor
   - Fill in the values (use the IDs you copied in Part 1, Step 3):
     ```
     DISCORD_TOKEN=paste_your_bot_token_here
     ADMIN_CHANNEL_ID=123456789012345678  # Replace with your admin channel ID
     ATTENDANCE_CHANNEL_ID=987654321098765432  # Replace with your attendance channel ID
     OPENROUTER_API_KEY=  # Optional - leave blank for now
     NL_ROUTING_CHANNELS=  # Optional - leave blank for now
     ```
   - **Important**:
     - `DISCORD_TOKEN` - The bot token you copied in Part 1
     - `ADMIN_CHANNEL_ID` - Where attendance codes appear (admins only)
     - `ATTENDANCE_CHANNEL_ID` - Where students submit `/here` commands
   - Save the file

### Step 3.5: Configure the Bot

1. **Review config.yaml**
   - Open `config.yaml` in your text editor
   - The defaults should work, but you can customize:
     - `llm.primary.model` - The AI model to use (default: llama3.2)
     - `mastery.min_attempts_for_mastery` - Quizzes needed to master a concept (default: 3)
   - Look for the `backup` section and verify:
     ```yaml
     backup:
       credentials_file: "credentials/google_oauth_credentials.json"
       token_file: "credentials/token.json"
       folder_name: "Chibi Bot Exports"  # Where exports go in Google Drive
     ```

2. **Review course.yaml** (Optional for now)
   - This file defines your course content
   - You can customize it later
   - The default example content will work for testing

### Step 3.6: Set Up Ollama (Local AI)

**What is Ollama?** Ollama runs AI models on your computer (instead of using cloud APIs). This is free but requires a decent computer.

**Skip this if you prefer to use OpenRouter (cloud AI) instead.**

1. **Install Ollama**
   - Visit: https://ollama.com/download
   - Download and install for your operating system

2. **Pull an AI Model**
   ```bash
   ollama pull llama3.2
   ```
   This downloads the AI model (~2GB). Takes 5-10 minutes depending on internet speed.

3. **Verify Ollama is Running**
   ```bash
   ollama list
   ```
   You should see `llama3.2` in the list.

**Alternative: Use OpenRouter (Cloud AI)**
- If you prefer cloud-based AI, sign up at: https://openrouter.ai/
- Get your API key
- Add it to `.env` as `OPENROUTER_API_KEY=your_key_here`
- The bot will automatically use it as a fallback if Ollama isn't available

---

## Part 4: First Run

### Step 4.1: Start the Bot

1. **Open Terminal in Your Project Directory**
   ```bash
   cd ~/Documents/discord-qa-agent  # adjust path if needed
   ```

2. **Run the Bot**
   ```bash
   uv run python main.py
   ```

3. **Watch the Logs**
   You should see messages like:
   ```
   2025-01-19 10:00:00 - chibi.bot - INFO - Setting up Chibi bot...
   2025-01-19 10:00:01 - chibi.bot - INFO - Database connected
   2025-01-19 10:00:01 - chibi.bot - INFO - Attendance session manager initialized
   2025-01-19 10:00:02 - chibi.bot - INFO - Cogs loaded
   2025-01-19 10:00:03 - discord.client - INFO - Logged in as ChibiBot#1234
   ```

4. **Check Discord**
   - Go to your Discord server
   - You should see your bot is now **Online** (green dot)
   - Congratulations! 🎉

### Step 4.2: First-Time Google OAuth Authorization

**When you first use a Google Sheets command, you'll need to authorize access:**

1. **In Discord, run a backup command** (as an admin):
   ```
   /export-progress
   ```

2. **Check your terminal** - you'll see a message:
   ```
   Please visit this URL to authorize the application:
   https://accounts.google.com/o/oauth2/auth?client_id=...
   ```

3. **Open the URL in your browser**
   - Click the link or copy-paste it
   - Log in to your Google account if needed
   - Click **"Advanced"** → **"Go to Chibi Bot (unsafe)"**
     - Don't worry - this warning appears because the app is in development mode
     - Your bot is safe since you created it!
   - Click **"Allow"** to grant permissions

4. **Return to the Terminal**
   - The bot will automatically detect authorization
   - You'll see: "Authentication successful! You may close this browser window."
   - From now on, you won't need to do this again (token is saved)

---

## Part 5: Testing

### Test Student Commands

In any channel, try these commands:

1. **View Available Modules**
   ```
   /modules
   ```
   You should see a list of course modules.

2. **Take a Quiz**
   ```
   /quiz
   ```
   The bot will generate a quiz question for you!

3. **Check Your Progress**
   ```
   /status
   ```
   Shows your learning progress.

### Test Admin Commands

In your admin channel (or any channel if you have admin permissions):

1. **View Admin Help**
   ```
   /admin-help
   ```
   Shows all available admin commands.

2. **List Students**
   ```
   /admin-students
   ```
   Shows all registered students (might be empty at first).

3. **Export to Google Sheets**
   ```
   /export-progress
   ```
   Creates a Google Sheets backup of all student data.
   You'll get a clickable link to the spreadsheet!

### Test Attendance (Optional)

1. **Start an Attendance Session**
   ```
   /admin-open-attendance
   ```
   The bot will post a rotating code in the admin channel.
   Students can submit with `/here <code>` in the attendance channel.

2. **Close the Session**
   ```
   /admin-close-attendance
   ```
   Saves all attendance records.

3. **Export Attendance**
   ```
   /admin-export-attendance
   ```
   Downloads a CSV file with attendance records.

---

## Troubleshooting

### Bot Won't Start

**Error: "ModuleNotFoundError: No module named 'discord'"**
- **Solution**: Install dependencies again:
  ```bash
  uv pip install -r requirements.txt
  ```

**Error: "discord.errors.LoginFailure: Improper token has been passed"**
- **Solution**: Check your `.env` file and make sure `DISCORD_TOKEN` is correct
- Go back to Discord Developer Portal → Bot → Reset Token and get a new one

**Error: "FileNotFoundError: [Errno 2] No such file or directory: 'config.yaml'"**
- **Solution**: Make sure you're running the bot from the project directory:
  ```bash
  cd discord-qa-agent
  uv run python main.py
  ```

### Bot is Online but Doesn't Respond

**Commands don't appear in Discord**
- **Solution**: Check if commands are synced:
  - Open `config.yaml`
  - Find `sync_commands_on_startup: true` (should be true)
  - Restart the bot
  - Wait 1-2 minutes for Discord to sync
  - Type `/` in Discord and you should see commands appear

**Bot doesn't respond to @mentions**
- **Solution**: Check Message Content Intent:
  - Go to Discord Developer Portal → Bot
  - Make sure "MESSAGE CONTENT INTENT" is enabled
  - Restart the bot

### Google Sheets Issues

**Error: "Failed to export progress to Google Sheets"**
- **Solution**: Check your credentials:
  - Make sure `credentials/google_oauth_credentials.json` exists
  - Run the bot again and complete OAuth authorization
  - Check that Google Sheets API and Google Drive API are enabled

**Error: "google.auth.exceptions.RefreshError"**
- **Solution**: Delete the token and re-authorize:
  ```bash
  rm credentials/token.json
  ```
  Then run `/export-progress` again and complete OAuth flow.

**Exported sheets don't appear in my Drive**
- **Solution**: Check the folder name:
  - Look in your Google Drive for a folder named "Chibi Bot Exports"
  - If you can't find it, search for the spreadsheet by name (starts with "Chibi_Progress_Export_")

### Database Issues

**Error: "Database is locked"**
- **Solution**: Only run one instance of the bot at a time
- If the bot crashed, delete the lock file:
  ```bash
  rm data/chibi.db-shm data/chibi.db-wal
  ```

### Ollama Issues

**Error: "Failed to connect to Ollama"**
- **Solution**: Make sure Ollama is running:
  ```bash
  ollama serve
  ```
  Run this in a separate terminal window and leave it running.

**Bot responses are very slow**
- **Solution**:
  - Local AI models need a decent computer (8GB+ RAM)
  - Try a smaller model: `ollama pull llama3.2:1b`
  - Or use OpenRouter (cloud) instead by adding API key to `.env`

---

## Next Steps

Once everything is working:

1. **Customize Your Course Content**
   - Edit `course.yaml` to add your modules, concepts, and content URLs
   - See `prompts/generate_course_yaml.md` for a template

2. **Set Up Automatic Syncing**
   - Consider scheduling regular exports to Google Sheets
   - Use `/export-progress` weekly to backup student data

3. **Explore Advanced Features**
   - Natural language routing (set `NL_ROUTING_CHANNELS` in `.env`)
   - LLM Quiz Challenge (`/llm-quiz`)
   - Guidance system (`/guidance`)

4. **Read the Documentation**
   - Check `README.md` for feature details
   - Browse `docs/` for testing guides and technical details

---

## Getting Help

If you're stuck:

1. **Check the Logs**
   - The terminal shows detailed error messages
   - Read them carefully - they often tell you exactly what's wrong

2. **Review This Guide**
   - Make sure you completed every step
   - Pay special attention to the ✅ checkboxes

3. **Check Configuration Files**
   - `.env` - Make sure all tokens and IDs are correct
   - `config.yaml` - Make sure paths are correct
   - `course.yaml` - Make sure format is valid YAML

4. **Ask for Help**
   - File an issue on GitHub: https://github.com/skojaku/discord-qa-agent/issues
   - Include:
     - What you were trying to do
     - The exact error message
     - Relevant logs from the terminal (remove any sensitive tokens!)

---

## Security Reminders

⚠️ **Never share these publicly:**
- Discord bot token (`.env` → `DISCORD_TOKEN`)
- Google OAuth credentials (`credentials/google_oauth_credentials.json`)
- Google OAuth token (`credentials/token.json`)
- OpenRouter API key (if using)

✅ **Safe to share:**
- `config.yaml` (general settings)
- `course.yaml` (course content)
- Error messages (after removing tokens)

---

## Congratulations! 🎉

You've successfully set up Chibi Discord Bot! Your students can now:
- Take AI-generated quizzes
- Track their learning progress
- Challenge the AI with custom questions
- Submit attendance

And you can:
- Monitor student progress
- Export data to Google Sheets
- Manage quizzes and attendance
- Track mastery levels

Happy teaching! 📚
