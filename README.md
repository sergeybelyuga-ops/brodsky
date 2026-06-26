# 📚 Brodsky Book Club Bot

A Telegram bot for collaborative book voting powered by Google Sheets.

## Features

### ✨ Book Voting

* Randomly selects 5 unread books from your Google Sheet
* Tracks which books have already participated in a voting cycle
* Starts a new voting cycle once all books have been included at least once

### ✨ Advanced Voting Rounds

To better identify the books that interest readers the most, the second and subsequent voting rounds follow different rules:

* Books with the highest vote counts are prioritized
* Each user can vote for only one book per poll
* Vote totals accumulate across multiple voting cycles

### ✨ Helps Choose the Next Book to Read

* Displays the Top 5 highest-ranked books
* Shows overall club statistics directly in Telegram
* Completed books can be marked as **Completed** in Google Sheets and excluded from future voting

---

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Google Sheets API

1. Create a Google Cloud project
2. Enable the Google Sheets API
3. Create a Service Account
4. Download the JSON credentials file
5. Share your Google Sheet with the Service Account email address
6. Save the credentials file as:

```text
brodsky-498313-541be19ee54f.json
```

### 3. Configure Environment Variables

Create a `.env` file:

```env
BOT_TOKEN=your_telegram_bot_token
CHAT_ID=your_telegram_chat_id
SPREADSHEET_ID=your_google_sheet_id
GOOGLE_CREDS_FILE=brodsky-498313-541be19ee54f.json
```

### 4. Prepare the Google Sheet

Required columns:

* **Title** — Book title
* **Author** — Author name
* **Description** — Short book description
* **Genre** — Book genre
* **Pages** — Number of pages
* **Votes** — Total vote count (starts at 0)
* **CycleUsed** — Internal cycle tracking (leave empty)
* **Status** — Optional status (e.g., Completed)

Example:

| Title | Author        | Description     | Genre  | Pages | Votes | CycleUsed | Status |
| ----- | ------------- | --------------- | ------ | ----- | ----- | --------- | ------ |
| 1984  | George Orwell | Dystopian novel | Sci-Fi | 328   | 0     | 0         |        |

---

## Usage

### Available Commands

### `/start`

Displays a welcome message and available commands.

### `/voting`

Creates a new time-limited poll.

What happens:

* Selects 5 eligible books
* Creates a Telegram poll
* Tracks voting progress
* Automatically processes results when the poll expires
* Updates vote counts in Google Sheets

### `/autoschedule YYYY-MM-DD HH:MM INTERVAL_HOURS`

Enables automatic recurring poll creation.

What happens:

* Saves scheduler configuration in SQLite
* Creates the first automatic poll at the configured start date/time
* Creates the next polls every `INTERVAL_HOURS`
* Uses the same interval as poll lifetime

Example:

```text
/autoschedule 2026-07-01 20:00 72
```

### `/autostop`

Disables automatic poll creation.

What happens:

* Stops future automatic poll creation
* Keeps existing active polls running normally
* Preserves scheduler configuration in SQLite

### `/autostatus`

Shows automatic scheduler status.

Output examples:

```text
Automatic poll creation: Enabled

Next poll:
2026-07-04 20:00

Interval:
72 hours

Poll lifetime:
72 hours
```

or

```text
Automatic poll creation: Disabled
```

### `/top`

Displays the 5 highest-ranked books based on accumulated votes.

### `/stat`

Displays a concise summary of the current club state.

What it includes:

* Total books in the library
* Number of completed books
* First-cycle progress for books with `Cycles = 0`
* How many first-cycle books have already appeared in a poll
* How many first-cycle books are still waiting for their first poll

### `/help`

Displays help information and command descriptions.

---

## How It Works

### 1. Poll Creation (`/voting`)

The bot:

* Selects 5 books from the spreadsheet
* Creates a Telegram poll with a 24-hour duration
* Allows users to vote

### 2. Vote Collection

After the poll expires:

* The bot retrieves the final vote counts
* Updates the corresponding books in Google Sheets
* Marks books as used in the current cycle

### 3. Cycle Management

The bot ensures all books get exposure before repeating selections.

Rules:

* Books are selected until all books have participated in a voting cycle
* Once all books have been used, a new cycle begins
* Books with higher rankings receive higher priority in future rounds
* Vote totals accumulate across cycles

### 4. Rankings (`/top`)

The bot:

* Sorts books by total votes
* Displays the Top 5 books
* Updates rankings automatically after each completed poll

---

## Running the Bot

### Run Locally

```bash
python main.py
```

### Run with Docker

```bash
docker-compose up
```

The bot will:

* Listen for `/voting` commands
* Monitor active polls
* Process completed polls
* Update Google Sheets
* Respond to `/top` requests

---

## Project Structure

```text
bot.py            # Telegram handlers and commands
main.py           # Application entry point
config.py         # Environment configuration
sheets.py         # Google Sheets integration
poll_manager.py   # SQLite poll management
ranking.py        # Ranking calculations
requirements.txt  # Python dependencies
polls.db          # SQLite database
```

---

## Database

The bot uses SQLite (`polls.db`) to store:

* Poll IDs
* Associated books
* Chat IDs
* Creation timestamps
* Expiration timestamps
* Poll status
* Automatic poll scheduler state (`poll_schedule` table)

This allows the bot to recover poll information after a restart.

---

## Troubleshooting

### Bot Is Not Responding

Check:

* BOT_TOKEN is correct
* The bot is running:

```bash
python main.py
```

* Logs do not contain errors

### Votes Are Not Updating

Check:

* Google Sheets API is enabled
* Service Account has access to the spreadsheet
* GOOGLE_CREDS_FILE path is correct
* Application logs for API errors

Important:

If nobody votes in a poll, Telegram may not send vote updates, and all books in that poll may remain unchanged.

### Polls Are Not Created

Check:

* CHAT_ID is correct
* The spreadsheet contains eligible books
* Column names match the required schema

### Google Sheets Updates Fail

Check:

* Spreadsheet permissions
* Service Account email access
* Credentials file validity
* Internet connectivity

---

## License

This project was created for the "Dead poets society" and is intended for educational and community use.
