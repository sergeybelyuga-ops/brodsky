import gspread
from google.oauth2.service_account import Credentials
from config import SPREADSHEET_ID, GOOGLE_CREDS_FILE
import random
import logging

logger = logging.getLogger(__name__)

def sheet():
    try:
        creds = Credentials.from_service_account_file(
            GOOGLE_CREDS_FILE,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        gc = gspread.authorize(creds)
        return gc.open_by_key(SPREADSHEET_ID).sheet1
    except Exception as e:
        logger.error(f"Error connecting to Google Sheets: {e}", exc_info=True)
        raise

def get_all_books():
    """Get all books from the sheet"""
    return sheet().get_all_records()

def get_unread_books(count=5):
    """Select random unread books (Votes == 0 or empty)"""
    books = get_all_books()
    unread = [b for b in books if not b.get('Votes') or b.get('Votes') == '' or int(b.get('Votes', '') or 0) == 0]
    
    if len(unread) < count:
        # If not enough unread, reset all and try again
        reset_cycle()
        unread = get_all_books()
    
    return random.sample(unread, min(count, len(unread)))

def reset_cycle():
    """Reset CycleUsed when all books have been voted"""
    ws = sheet()
    all_records = ws.get_all_records()
    for idx, book in enumerate(all_records, start=2):
        ws.update_cell(idx, ws.find('CycleUsed').col, '')

def get_book_by_title(title):
    """Get book row by title"""
    books = get_all_books()
    for book in books:
        if book.get('Title') == title:
            return book
    return None

def get_book_row_index(title):
    """Get the row index of a book by title - search in Title column"""
    try:
        ws = sheet()
        # Get all records to find the book
        all_records = ws.get_all_records()
        for idx, book in enumerate(all_records, start=2):  # Start at row 2 (row 1 is header)
            if book.get('Title') == title:
                logger.debug(f"Found '{title}' at row {idx}")
                return idx
        
        logger.warning(f"⚠️ Book '{title}' not found in spreadsheet")
        return None
            
    except Exception as e:
        logger.error(f"❌ Error finding book row for '{title}': {e}", exc_info=True)
        return None

def update_votes(title, votes):
    """Update votes for a book"""
    try:
        ws = sheet()
        row_idx = get_book_row_index(title)
        if not row_idx:
            logger.error(f"❌ Book '{title}' not found in spreadsheet")
            return False
        
        # Find the Votes column
        votes_col = ws.find('Votes')
        if not votes_col:
            logger.error("❌ 'Votes' column not found in spreadsheet")
            return False
        
        # Get current votes
        votes_cell = ws.cell(row_idx, votes_col.col)
        current_votes = int(votes_cell.value or 0) if votes_cell.value and str(votes_cell.value).strip() != '' else 0
        new_votes = current_votes + votes
        
        # Update the cell
        ws.update_cell(row_idx, votes_col.col, str(new_votes))
        logger.info(f"✅ Updated {title}: {current_votes} + {votes} = {new_votes} votes")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error updating votes for {title}: {e}", exc_info=True)
        return False

def mark_book_as_used(title):
    """Mark a book as used in current cycle"""
    try:
        ws = sheet()
        row_idx = get_book_row_index(title)
        if not row_idx:
            logger.error(f"❌ Book '{title}' not found for marking as used")
            return False
        
        cycle_col = ws.find('CycleUsed')
        if not cycle_col:
            logger.error("❌ 'CycleUsed' column not found in spreadsheet")
            return False
        
        ws.update_cell(row_idx, cycle_col.col, 'Yes')
        logger.info(f"✅ Marked {title} as used in current cycle")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error marking {title} as used: {e}", exc_info=True)
        return False

def get_top_books(count=5):
    """Get top books by votes"""
    books = get_all_books()
    books.sort(key=lambda x: int(x.get('Votes', '') or 0), reverse=True)
    return books[:count]

