# 📚 Brodsky Book Club Bot

A Telegram bot for collaborative book voting using Google Sheets.

## Features

✨ **Smart Book Selection**
- Randomly selects 5 unread books from your Google Sheets
- Tracks which books have been voted on
- Automatically restarts cycle when all books are used
- Prioritizes previously voted books in new cycles

🗳️ **Advanced Voting**
- Creates 24-hour Telegram polls
- Multiple-choice voting (members can vote for multiple books)
- See who voted for what
- Re-voting allowed
- Automatic vote collection after 24 hours

📊 **Vote Management**
- Accumulates votes across cycles
- Updates Google Sheets in real-time
- Shows top 5 books by votes
- Persistent vote tracking

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Google Sheets API
1. Create a Google Cloud project
2. Enable Google Sheets API
3. Create a service account and download JSON credentials
4. Share your Google Sheet with the service account email
5. Save the JSON file as `brodsky-498313-541be19ee54f.json`

### 3. Set Environment Variables (.env)
```
BOT_TOKEN=your_telegram_bot_token
CHAT_ID=your_telegram_chat_id
SPREADSHEET_ID=your_google_sheet_id
GOOGLE_CREDS_FILE=brodsky-498313-541be19ee54f.json
```

### 4. Prepare Google Sheet
Required columns:
- **Title** - Book title
- **Author** - Author name
- **Description** - Book description
- **Genre** - Genre
- **Pages** - Number of pages
- **Votes** - Vote count (starts at 0)
- **CycleUsed** - Internal tracking (leave empty)

Example:
| Title | Author | Description | Genre | Pages | Votes | CycleUsed |
|-------|--------|-------------|-------|-------|-------|-----------|
| 1984 | George Orwell | Dystopian novel | Sci-Fi | 328 | 0 | |

## Usage

### Commands

**`/start`** - Show welcome message and available commands

**`/voting`** - Create a new 24-hour poll
- Selects 5 random unread books
- Creates Telegram poll
- Automatically collects votes after 24 hours
- Updates Google Sheet with results

**`/top`** - Show top 5 books by votes
- Displays ranking with vote counts
- Updated in real-time

**`/help`** - Show help message

## How It Works

1. **Poll Creation** (`/voting`)
   - Bot selects 5 random unread books
   - Creates a Telegram poll with 24-hour duration
   - Allows multiple selections

2. **Vote Collection** (automatic after 24 hours)
   - Bot retrieves poll results
   - Updates Google Sheet with vote counts
   - Marks books as used in current cycle

3. **Cycle Management**
   - When all books have been voted, cycle restarts
   - Previously voted books get prioritized based on votes
   - Vote counts accumulate across cycles

4. **Ranking** (`/top`)
   - Shows top 5 books sorted by total votes
   - Updates as new votes are collected

## Running the Bot

### Locally
```bash
python main.py
```

### With Docker
```bash
docker-compose up
```

The bot runs continuously and:
- Listens for `/voting` commands
- Checks for poll completions every minute
- Updates Google Sheet with results
- Responds to `/top` queries

## Project Structure

- `bot.py` - Main bot logic and handlers
- `main.py` - Entry point
- `config.py` - Configuration loading
- `sheets.py` - Google Sheets integration
- `poll_manager.py` - Poll tracking database
- `ranking.py` - Ranking calculations
- `requirements.txt` - Python dependencies
- `schema.md` - Google Sheet schema

## Database

The bot uses SQLite (`polls.db`) to track:
- Poll IDs
- Associated books
- Creation/expiration times
- Poll status

## Notes

- Votes are accumulated across multiple cycles
- Books reset when all have been voted
- The bot checks for poll results every minute
- Poll results update Google Sheets automatically
- Top 5 is calculated from total accumulated votes

## Troubleshooting

**Bot not responding?**
- Check BOT_TOKEN in .env
- Verify bot is running: `python main.py`
- Check logs for errors

**Votes not updating?**
- Ensure Google Sheets API is enabled
- Verify service account has sheet access
- Check GOOGLE_CREDS_FILE path
- Review bot logs for API errors

**Polls not created?**
- Ensure CHAT_ID is correct
- Check spreadsheet has books
- Verify columns match schema.md

## License

Project for Brodsky Book Club
