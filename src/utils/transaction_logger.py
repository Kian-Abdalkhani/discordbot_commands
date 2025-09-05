import sqlite3
import aiosqlite
import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from src.config.settings import (
    TRANSACTION_LOGGING_ENABLED, 
    TRANSACTION_NICKNAME_TRACKING,
    TRANSACTION_TYPES
)

logger = logging.getLogger(__name__)

class TransactionLogger:
    """Logs all currency transactions to SQLite database for tracking and analysis"""
    
    def __init__(self):
        self.db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "transactions.db"
        )
        
    async def initialize(self):
        """Initialize the database and create tables if they don't exist"""
        if not TRANSACTION_LOGGING_ENABLED:
            logger.info("Transaction logging is disabled in configuration")
            return
            
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            async with aiosqlite.connect(self.db_path) as db:
                # Create user_info table for nickname tracking
                if TRANSACTION_NICKNAME_TRACKING:
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS user_info (
                            user_id TEXT PRIMARY KEY,
                            display_name TEXT NOT NULL,
                            mention TEXT NOT NULL,
                            last_updated DATETIME NOT NULL
                        )
                    """)
                
                # Create enhanced transactions table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        command TEXT NOT NULL,
                        amount REAL NOT NULL,
                        balance_before REAL NOT NULL,
                        balance_after REAL NOT NULL,
                        profit_loss REAL DEFAULT 0.0,
                        transaction_type TEXT DEFAULT 'currency',
                        tax_category TEXT DEFAULT NULL,
                        metadata TEXT
                    )
                """)
                
                # Check if we need to add new columns to existing transactions table
                await self._migrate_existing_table(db)
                
                # Create indexes for better query performance (after migration ensures columns exist)
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_user_id ON transactions(user_id)
                """)
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_timestamp ON transactions(timestamp)
                """)
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_command ON transactions(command)
                """)
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_transaction_type ON transactions(transaction_type)
                """)
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_profit_loss ON transactions(profit_loss)
                """)
                
                await db.commit()
                
            logger.info(f"Transaction logging database initialized at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Error initializing transaction database: {e}")
            raise
    
    async def _migrate_existing_table(self, db):
        """Add new columns to existing transactions table if they don't exist"""
        try:
            # Check if transactions table exists first
            cursor = await db.execute("""
                SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'
            """)
            table_exists = await cursor.fetchone()
            
            if not table_exists:
                logger.info("Transactions table doesn't exist yet, skipping migration")
                return
            
            # Check existing columns
            cursor = await db.execute("PRAGMA table_info(transactions)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            logger.info(f"Existing columns in transactions table: {column_names}")
            
            # Add missing columns one by one with individual error handling
            if 'profit_loss' not in column_names:
                try:
                    await db.execute("ALTER TABLE transactions ADD COLUMN profit_loss REAL DEFAULT 0.0")
                    logger.info("Added profit_loss column to transactions table")
                except Exception as e:
                    logger.warning(f"Failed to add profit_loss column: {e}")
                    
            if 'transaction_type' not in column_names:
                try:
                    await db.execute("ALTER TABLE transactions ADD COLUMN transaction_type TEXT DEFAULT 'currency'")
                    logger.info("Added transaction_type column to transactions table")
                except Exception as e:
                    logger.warning(f"Failed to add transaction_type column: {e}")
                    
            if 'tax_category' not in column_names:
                try:
                    await db.execute("ALTER TABLE transactions ADD COLUMN tax_category TEXT DEFAULT NULL")
                    logger.info("Added tax_category column to transactions table")
                except Exception as e:
                    logger.warning(f"Failed to add tax_category column: {e}")
                
        except Exception as e:
            logger.warning(f"Error during table migration: {e}")
    
    async def log_transaction(
        self,
        user_id: str,
        command: str,
        amount: float,
        balance_before: float,
        balance_after: float,
        profit_loss: float = 0.0,
        transaction_type: str = "currency",
        tax_category: Optional[str] = None,
        metadata: Optional[Dict[Any, Any]] = None,
        display_name: Optional[str] = None,
        mention: Optional[str] = None
    ):
        """
        Log a currency transaction to the database
        
        Args:
            user_id: Discord user ID as string
            command: The command or action that triggered this transaction
            amount: Amount of currency changed (positive for additions, negative for subtractions)
            balance_before: User's balance before the transaction
            balance_after: User's balance after the transaction
            profit_loss: Actual profit or loss from this transaction (0 for currency operations)
            transaction_type: Type of transaction (currency, gambling, investment, fee)
            tax_category: Optional tax category for this transaction
            metadata: Optional dictionary with additional context (bet details, game results, etc.)
            display_name: Current display name of the user
            mention: Discord mention format for the user
        """
        if not TRANSACTION_LOGGING_ENABLED:
            return
            
        try:
            timestamp = datetime.now()
            metadata_json = json.dumps(metadata) if metadata else None
            
            # Validate transaction type
            if transaction_type not in TRANSACTION_TYPES.values():
                logger.warning(f"Invalid transaction type '{transaction_type}', defaulting to 'currency'")
                transaction_type = "currency"
            
            async with aiosqlite.connect(self.db_path) as db:
                # Update user info if nickname tracking is enabled and info is provided
                if TRANSACTION_NICKNAME_TRACKING and display_name and mention:
                    await self._update_user_info(db, user_id, display_name, mention, timestamp)
                
                # Insert transaction
                await db.execute("""
                    INSERT INTO transactions (
                        user_id, timestamp, command, amount, 
                        balance_before, balance_after, profit_loss,
                        transaction_type, tax_category, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, timestamp, command, amount,
                    balance_before, balance_after, profit_loss,
                    transaction_type, tax_category, metadata_json
                ))
                await db.commit()
                
            logger.debug(f"Logged transaction: user={user_id}, command={command}, amount={amount}, profit_loss={profit_loss}, type={transaction_type}")
            
        except Exception as e:
            logger.error(f"Error logging transaction for user {user_id}: {e}")
            # Don't raise - we don't want transaction logging failures to break currency operations
    
    async def _update_user_info(self, db, user_id: str, display_name: str, mention: str, timestamp: datetime):
        """Update user info in the user_info table"""
        try:
            await db.execute("""
                INSERT OR REPLACE INTO user_info (user_id, display_name, mention, last_updated)
                VALUES (?, ?, ?, ?)
            """, (user_id, display_name, mention, timestamp))
        except Exception as e:
            logger.warning(f"Error updating user info for {user_id}: {e}")
    
    async def get_user_info(self, user_id: str) -> Optional[Dict[str, str]]:
        """Get user info from user_info table"""
        if not TRANSACTION_NICKNAME_TRACKING or not TRANSACTION_LOGGING_ENABLED:
            return None
            
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT display_name, mention, last_updated
                    FROM user_info
                    WHERE user_id = ?
                """, (user_id,))
                row = await cursor.fetchone()
                
                if row:
                    return {
                        "display_name": row[0],
                        "mention": row[1],
                        "last_updated": row[2]
                    }
                return None
                
        except Exception as e:
            logger.error(f"Error getting user info for {user_id}: {e}")
            return None
    
    async def get_user_transactions(
        self, 
        user_id: str, 
        limit: int = 100,
        command_filter: Optional[str] = None,
        transaction_type_filter: Optional[str] = None
    ):
        """
        Get recent transactions for a specific user
        
        Args:
            user_id: Discord user ID as string
            limit: Maximum number of transactions to return
            command_filter: Optional command name to filter by
            transaction_type_filter: Optional transaction type to filter by
            
        Returns:
            List of transaction dictionaries
        """
        if not TRANSACTION_LOGGING_ENABLED:
            return []
            
        try:
            async with aiosqlite.connect(self.db_path) as db:
                where_clauses = ["user_id = ?"]
                params = [user_id]
                
                if command_filter:
                    where_clauses.append("command = ?")
                    params.append(command_filter)
                
                if transaction_type_filter:
                    where_clauses.append("transaction_type = ?")
                    params.append(transaction_type_filter)
                
                params.append(limit)
                
                query = f"""
                    SELECT * FROM transactions 
                    WHERE {' AND '.join(where_clauses)}
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """
                
                cursor = await db.execute(query, params)
                rows = await cursor.fetchall()
                
                # Get column info to handle both old and new schema
                cursor = await db.execute("PRAGMA table_info(transactions)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                # Convert to list of dictionaries
                transactions = []
                for row in rows:
                    transaction = {
                        'id': row[0],
                        'user_id': row[1],
                        'timestamp': row[2],
                        'command': row[3],
                        'amount': row[4],
                        'balance_before': row[5],
                        'balance_after': row[6],
                    }
                    
                    # Handle new columns if they exist
                    if 'profit_loss' in column_names:
                        transaction['profit_loss'] = row[7] if len(row) > 7 else 0.0
                        transaction['transaction_type'] = row[8] if len(row) > 8 else 'currency'
                        transaction['tax_category'] = row[9] if len(row) > 9 else None
                        transaction['metadata'] = json.loads(row[10]) if len(row) > 10 and row[10] else None
                    else:
                        # Old schema
                        transaction['profit_loss'] = 0.0
                        transaction['transaction_type'] = 'currency'
                        transaction['tax_category'] = None
                        transaction['metadata'] = json.loads(row[7]) if len(row) > 7 and row[7] else None
                    
                    transactions.append(transaction)
                
                return transactions
                
        except Exception as e:
            logger.error(f"Error getting transactions for user {user_id}: {e}")
            return []
    
    async def get_transactions_by_timeframe(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[str] = None,
        transaction_type_filter: Optional[str] = None
    ):
        """
        Get transactions within a specific timeframe
        
        Args:
            start_date: Start of timeframe
            end_date: End of timeframe  
            user_id: Optional user ID to filter by
            transaction_type_filter: Optional transaction type to filter by
            
        Returns:
            List of transaction dictionaries
        """
        if not TRANSACTION_LOGGING_ENABLED:
            return []
            
        try:
            async with aiosqlite.connect(self.db_path) as db:
                where_clauses = ["timestamp BETWEEN ? AND ?"]
                params = [start_date, end_date]
                
                if user_id:
                    where_clauses.append("user_id = ?")
                    params.append(user_id)
                    
                if transaction_type_filter:
                    where_clauses.append("transaction_type = ?")
                    params.append(transaction_type_filter)
                
                query = f"""
                    SELECT * FROM transactions 
                    WHERE {' AND '.join(where_clauses)}
                    ORDER BY timestamp DESC
                """
                
                cursor = await db.execute(query, params)
                rows = await cursor.fetchall()
                
                # Get column info to handle both old and new schema
                cursor = await db.execute("PRAGMA table_info(transactions)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                # Convert to list of dictionaries
                transactions = []
                for row in rows:
                    transaction = {
                        'id': row[0],
                        'user_id': row[1], 
                        'timestamp': row[2],
                        'command': row[3],
                        'amount': row[4],
                        'balance_before': row[5],
                        'balance_after': row[6],
                    }
                    
                    # Handle new columns if they exist
                    if 'profit_loss' in column_names:
                        transaction['profit_loss'] = row[7] if len(row) > 7 else 0.0
                        transaction['transaction_type'] = row[8] if len(row) > 8 else 'currency'
                        transaction['tax_category'] = row[9] if len(row) > 9 else None
                        transaction['metadata'] = json.loads(row[10]) if len(row) > 10 and row[10] else None
                    else:
                        # Old schema
                        transaction['profit_loss'] = 0.0
                        transaction['transaction_type'] = 'currency'
                        transaction['tax_category'] = None
                        transaction['metadata'] = json.loads(row[7]) if len(row) > 7 and row[7] else None
                    
                    transactions.append(transaction)
                
                return transactions
                
        except Exception as e:
            logger.error(f"Error getting transactions by timeframe: {e}")
            return []
    
    async def get_profit_loss_summary(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transaction_type: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Get profit/loss summary for a user within a timeframe
        
        Args:
            user_id: Discord user ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            transaction_type: Optional transaction type filter
            
        Returns:
            Dictionary with profit/loss summary
        """
        if not TRANSACTION_LOGGING_ENABLED:
            return {"total_profit": 0.0, "total_loss": 0.0, "net_profit": 0.0}
            
        try:
            async with aiosqlite.connect(self.db_path) as db:
                where_clauses = ["user_id = ?"]
                params = [user_id]
                
                if start_date:
                    where_clauses.append("timestamp >= ?")
                    params.append(start_date)
                    
                if end_date:
                    where_clauses.append("timestamp <= ?")
                    params.append(end_date)
                    
                if transaction_type:
                    where_clauses.append("transaction_type = ?")
                    params.append(transaction_type)
                
                query = f"""
                    SELECT 
                        SUM(CASE WHEN profit_loss > 0 THEN profit_loss ELSE 0 END) as total_profit,
                        SUM(CASE WHEN profit_loss < 0 THEN ABS(profit_loss) ELSE 0 END) as total_loss,
                        SUM(profit_loss) as net_profit
                    FROM transactions 
                    WHERE {' AND '.join(where_clauses)}
                """
                
                cursor = await db.execute(query, params)
                row = await cursor.fetchone()
                
                if row:
                    return {
                        "total_profit": row[0] or 0.0,
                        "total_loss": row[1] or 0.0,
                        "net_profit": row[2] or 0.0
                    }
                
                return {"total_profit": 0.0, "total_loss": 0.0, "net_profit": 0.0}
                
        except Exception as e:
            logger.error(f"Error getting profit/loss summary for user {user_id}: {e}")
            return {"total_profit": 0.0, "total_loss": 0.0, "net_profit": 0.0}