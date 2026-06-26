import gspread
from google.oauth2.service_account import Credentials
from config import SPREADSHEET_ID, GOOGLE_CREDS_FILE
import random
import logging

logger = logging.getLogger(__name__)


class SheetStatsError(Exception):
    pass

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


def _parse_cycle_value(value):
    if value is None:
        return 0

    raw_value = str(value).strip()
    if raw_value == '':
        return 0

    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        raise SheetStatsError(
            f"Invalid cycle value: {value}"
        ) from exc


def _is_completed_book(book):
    completed_value = book.get('Completed')
    if completed_value is not None:
        normalized = str(completed_value).strip().lower()
        return normalized in {'true', '1', 'yes'}

    status_value = str(book.get('Status', '')).strip().lower()
    return status_value == 'completed'


def _has_votes_value(book):
    votes_value = book.get('Votes')
    return votes_value is not None and str(votes_value).strip() != ''


def _build_cycle_stats(books, cycle_number):
    already_voted = 0

    for book in books:
        cycle_value = book.get('Cycles')
        if cycle_value is None:
            continue

        cycle_value = _parse_cycle_value(book.get('Cycles'))
        if cycle_value <= cycle_number:
            continue
        
        already_voted += 1

    return {
        'cycle_number': cycle_number,
        'already_voted': already_voted,
    }


def get_book_club_stats():
    """Return aggregate statistics for the book club."""
    try:
        ws = sheet()
        headers = [str(header).strip() for header in ws.row_values(1)]

        if not headers:
            raise SheetStatsError("Spreadsheet is empty")

        required_columns = {'Votes', 'Cycles'}
        missing_columns = [
            column for column in required_columns
            if column not in headers
        ]

        if 'Completed' not in headers and 'Status' not in headers:
            missing_columns.append('Completed or Status')

        if missing_columns:
            raise SheetStatsError(
                "Missing required columns: " + ", ".join(missing_columns)
            )

        books = ws.get_all_records()
        total_books = len(books)

        if total_books == 0:
            raise SheetStatsError("Spreadsheet does not contain any books")

        completed_books = 0
        cycle_values = []

        for book in books:
            if _is_completed_book(book):
                completed_books += 1

            cycle_value = _parse_cycle_value(book.get('Cycles'))
            cycle_values.append(cycle_value)

        current_cycle_number = max(cycle_values, default=0)
        first_cycle_stats = _build_cycle_stats(books, 0)
        current_cycle_stats = _build_cycle_stats(books, current_cycle_number-1)

        return {
            'total_books': total_books,
            'completed_books': completed_books,
            'current_cycle_number': current_cycle_number,
            'first_cycle_voted': first_cycle_stats['already_voted'],
            'first_cycle_waiting': total_books - first_cycle_stats['already_voted'],
            'current_cycle_voted': current_cycle_stats['already_voted'],
            'current_cycle_waiting': total_books - current_cycle_stats['already_voted'],
        }

    except SheetStatsError:
        raise
    except Exception as exc:
        logger.error("Error calculating book club stats", exc_info=True)
        raise SheetStatsError(
            "Failed to read statistics from Google Sheets"
        ) from exc

def get_unread_books(count):
    """Select random unread books for the poll, prioritizing books that have not been voted in the current cycle."""
    books = get_all_books()
    current_cycle = min((int(b.get('Cycles', 0) or 0) for b in books), default=0)
    not_completed_books = [b for b in books if b.get('Status') != "Completed"]
    not_voted_books = [b for b in not_completed_books if int(b.get('Cycles', 0) or 0) <= current_cycle]
    
    if current_cycle == 0:
        # If it's the first cycle, allow all unread books
        return random.sample(not_voted_books, min(count, len(not_voted_books)))
    else:
        # For subsequent cycles, sorting books by rating and return the top ones that haven't been voted yet
        not_voted_books.sort(key=lambda x: int(x.get('Votes', 0) or 0), reverse=True)
        return not_voted_books[:count]


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
        mark_book_as_used(title)  # Mark the book as used in the current cycle
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
        
        cycle_col = ws.find('Cycles')
        if not cycle_col:
            logger.error("❌ 'Cycles' column not found in spreadsheet")
            return False
        
        cycle_cell = ws.cell(row_idx, cycle_col.col)

        current_cycle = int(cycle_cell.value or 0) if cycle_cell.value and str(cycle_cell.value).strip() != '' else 0
        new_cycle = current_cycle + 1

        # Update the cell
        ws.update_cell(row_idx, cycle_col.col, str(new_cycle))

        logger.info(f"✅ Marked {title} as used in current cycle")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error marking {title} as used: {e}", exc_info=True)
        return False

def get_top_books(count=5):
    """Get top books by votes"""
    books = get_all_books()
    books.sort(key=lambda x: int(x.get('Votes', '') or 0), reverse=True)
    not_completed_books = [b for b in books if b.get('Status') != "Completed"]
 
    return not_completed_books[:count]

