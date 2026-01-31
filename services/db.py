import os
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
from supabase import create_client, Client
import uuid

from .quai_api import QuaiAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            logger.warning("Supabase credentials not found in environment variables")
            self.supabase = None
        else:
            try:
                # Try Python client first
                self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
                logger.info("Connected to Supabase successfully")
            except Exception as e:
                logger.error(f"Python client failed: {str(e)}")
                # Fall back to REST API directly
                try:
                    import requests
                    self.rest_client = requests.Session()
                    self.rest_client.headers.update({
                        'apikey': self.supabase_key,
                        'Authorization': f'Bearer {self.supabase_key}'
                    })
                    logger.info("Using REST API fallback for Supabase")
                    self.supabase = None  # Mark Python client as unavailable
                except Exception as rest_e:
                    logger.error(f"REST API fallback failed: {rest_e}")
                    self.supabase = None
        
        self.quai_api = QuaiAPI()
        
        # Reference wallet for initial data
        self.reference_wallet = "0x002624Fa55DFf0ca53aF9166B4d44c16a294C4e0"
        
        # Initialize fallback storage
        self._fallback_blocks = []
        self._fallback_transactions = []

    def _initialize_tables_if_needed(self):
        """Create tables if they don't exist"""
        if not self.supabase:
            return False
            
        try:
            # Create wallets table
            self.supabase.rpc('create_wallets_table_if_not_exists').execute()
            
            # Create transactions table
            self.supabase.rpc('create_transactions_table_if_not_exists').execute()
            
            # Create blocks table
            self.supabase.rpc('create_blocks_table_if_not_exists').execute()
            
            return True
        except Exception as e:
            logger.error(f"Table initialization failed: {str(e)}")
            return False

    def update_wallet_data(self, address: str) -> bool:
        """Update wallet balance and transactions"""
        if not self.supabase:
            return False
            
        try:
            # Get balance
            balance = self.quai_api.get_wallet_balance(address)
            if balance is None:
                return False
            
            # Update wallet
            wallet_data = {
                'address': address,
                'balance': int(balance),
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            
            # Upsert wallet
            self.supabase.from_('wallets').upsert(wallet_data).execute()
            
            # Get transactions
            txs = self.quai_api.get_wallet_transactions(address, offset=50)
            if txs:
                self._store_transactions(address, txs)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update wallet {address}: {str(e)}")
            return False

    def _store_transactions(self, wallet_address: str, transactions: List[Dict]):
        """Store transactions in database"""
        try:
            stored_txs = []
            for tx in transactions:
                # Determine direction
                direction = 'incoming' if tx.get('to', '').lower() == wallet_address.lower() else 'outgoing'
                
                # Parse timestamp (QUAI timestamps are in seconds)
                timestamp_int = int(tx.get('timeStamp', '0'))
                timestamp = datetime.utcfromtimestamp(timestamp_int).isoformat()
                
                # Parse value
                value_hex = tx.get('value', '0x0')
                try:
                    value_int = int(value_hex, 16) if value_hex.startswith('0x') else int(value_hex)
                except (ValueError, TypeError):
                    value_int = 0
                
                tx_data = {
                    'id': str(uuid.uuid4()),
                    'wallet_address': wallet_address,
                    'tx_hash': tx.get('hash', ''),
                    'from_address': tx.get('from', ''),
                    'to_address': tx.get('to', ''),
                    'value': value_int,
                    'gas_used': int(tx.get('gasUsed', '0'), 16) if tx.get('gasUsed') else 0,
                    'timestamp': timestamp,
                    'direction': direction,
                    'block_number': int(tx.get('blockNumber', '0x0'), 16) if tx.get('blockNumber') else None
                }
                
                if self.supabase:
                    # Upsert transaction
                    self.supabase.from_('transactions').upsert(tx_data).execute()
                else:
                    # Store in memory for fallback
                    stored_txs.append(tx_data)
                
            # Store transactions for fallback if no Supabase
            if not self.supabase and stored_txs:
                if not hasattr(self, '_fallback_transactions'):
                    self._fallback_transactions = []
                self._fallback_transactions.extend(stored_txs)
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to store transactions: {str(e)}")
            return False

    def update_latest_blocks(self, count: int = 10) -> bool:
        """Update latest blocks"""
        try:
            # Get latest block number
            latest_block_num = self.quai_api.get_latest_block_number()
            if latest_block_num is None:
                logger.warning("Could not fetch latest block number")
                return False
            
            blocks_data = []
            # Get details for latest blocks
            for i in range(count):
                block_num = latest_block_num - i
                block_details = self.quai_api.get_block_details(block_num)
                
                if block_details:
                    # Parse timestamp (handle hex format - QUAI timestamps are in SECONDS)
                    # QUAI API puts timestamp in woHeader.timestamp
                    wo_header = block_details.get('woHeader', {})
                    timestamp_hex = wo_header.get('timestamp', '0x0')
                    try:
                        timestamp_int = int(timestamp_hex, 16)
                        # QUAI timestamps are in seconds, not milliseconds
                        timestamp = datetime.utcfromtimestamp(timestamp_int).isoformat()
                    except (ValueError, TypeError):
                        timestamp = datetime.now(timezone.utc).isoformat()
                    
                    block_data = {
                        'block_number': block_num,
                        'tx_count': len(block_details.get('transactions', [])),
                        'gas_used': int(block_details.get('gasUsed', '0x0'), 16) if block_details.get('gasUsed') else 0,
                        'timestamp': timestamp
                    }
                    
                    if self.supabase:
                        # Upsert block
                        self.supabase.from_('blocks').upsert(block_data).execute()
                    else:
                        # Store in memory for fallback
                        blocks_data.append(block_data)
            
            # Store blocks data for fallback if no Supabase
            if not self.supabase and blocks_data:
                self._fallback_blocks = blocks_data
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update blocks: {str(e)}")
            return False
            
        try:
            # Get latest block number
            latest_block_num = self.quai_api.get_latest_block_number()
            if latest_block_num is None:
                return False
            
            # Get details for latest blocks
            for i in range(count):
                block_num = latest_block_num - i
                block_details = self.quai_api.get_block_details(block_num)
                
                if block_details:
                    block_data = {
                        'block_number': block_num,
                        'tx_count': len(block_details.get('transactions', [])),
                        'gas_used': int(block_details.get('gasUsed', '0x0'), 16),
                        'timestamp': datetime.fromtimestamp(int(block_details.get('timestamp', '0'), 16), timezone.utc).isoformat()
                    }
                    
                    # Upsert block
                    self.supabase.from_('blocks').upsert(block_data).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update blocks: {str(e)}")
            return False

    def _rest_get_latest_blocks(self, limit: int = 10) -> List[Dict]:
        """Get latest blocks using REST API fallback"""
        if not hasattr(self, 'rest_client'):
            return []
            
        try:
            url = f"{self.supabase_url}/rest/v1/blocks"
            params = {'select': '*', 'order': 'block_number.desc', 'limit': limit}
            response = self.rest_client.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json() or []
        except Exception as e:
            logger.error(f"REST API blocks fetch failed: {str(e)}")
            return []

    def get_latest_blocks(self, limit: int = 10) -> List[Dict]:
        """Get latest blocks from database or fallback"""
        if self.supabase:
            try:
                result = self.supabase.from_('blocks').select('*').order('block_number', desc=True).limit(limit).execute()
                return result.data or []
            except Exception as e:
                logger.error(f"Supabase blocks fetch failed: {str(e)}")
        
        # Try REST API fallback
        rest_blocks = self._rest_get_latest_blocks(limit)
        if rest_blocks:
            return rest_blocks
        
        # Return fallback data if available, otherwise try to fetch live
        if hasattr(self, '_fallback_blocks') and self._fallback_blocks:
            return sorted(self._fallback_blocks, key=lambda x: x['block_number'], reverse=True)[:limit]
        
        # Fallback: fetch live data
        try:
            latest_block_num = self.quai_api.get_latest_block_number()
            if latest_block_num:
                blocks = []
                for i in range(max(limit, 10)):  # Ensure at least 10 blocks for gas chart
                    block_num = latest_block_num - i
                    block_details = self.quai_api.get_block_details(block_num)
                    
                    if block_details:
                        # Parse timestamp from woHeader (QUAI API puts timestamp there)
                        wo_header = block_details.get('woHeader', {})
                        timestamp_hex = wo_header.get('timestamp', '0x0')
                        try:
                            timestamp_int = int(timestamp_hex, 16)
                            # QUAI timestamps are in seconds, not milliseconds
                            timestamp = datetime.utcfromtimestamp(timestamp_int).isoformat()
                        except (ValueError, TypeError):
                            timestamp = datetime.now(timezone.utc).isoformat()
                        
                        # Parse gas_used correctly
                        gas_used_hex = block_details.get('gasUsed', '0x0')
                        try:
                            gas_used = int(gas_used_hex, 16)
                        except (ValueError, TypeError):
                            gas_used = 0
                        
                        blocks.append({
                            'block_number': block_num,
                            'tx_count': len(block_details.get('transactions', [])),
                            'gas_used': gas_used,
                            'timestamp': timestamp
                        })
                
                if blocks:
                    return blocks
        except Exception as e:
            logger.error(f"Live block fetch failed: {str(e)}")
        
        # Final fallback: empty list
        return []

    def _rest_get_latest_transactions(self, limit: int = 10) -> List[Dict]:
        """Get latest transactions using REST API fallback"""
        if not hasattr(self, 'rest_client'):
            return []
            
        try:
            url = f"{self.supabase_url}/rest/v1/transactions"
            params = {'select': '*', 'order': 'timestamp.desc', 'limit': limit}
            response = self.rest_client.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json() or []
        except Exception as e:
            logger.error(f"REST API transactions fetch failed: {str(e)}")
            return []

    def get_latest_transactions(self, limit: int = 10) -> List[Dict]:
        """Get latest transactions from database or fallback"""
        if self.supabase:
            try:
                result = self.supabase.from_('transactions').select('*').order('timestamp', desc=True).limit(limit).execute()
                return result.data or []
            except Exception as e:
                logger.error(f"Supabase transactions fetch failed: {str(e)}")
        
        # Try REST API fallback
        rest_transactions = self._rest_get_latest_transactions(limit)
        if rest_transactions:
            return rest_transactions
        
        # Return fallback data if available, otherwise try to fetch live
        if hasattr(self, '_fallback_transactions') and self._fallback_transactions:
            return sorted(self._fallback_transactions, key=lambda x: x['timestamp'], reverse=True)[:limit]
        
        # Fallback: fetch live data from recent blocks - Enhanced for charts
        try:
            latest_block_num = self.quai_api.get_latest_block_number()
            if not latest_block_num:
                return []
            
            transactions = []
            blocks_to_check = min(100, max(limit * 10, 50))  # Check more blocks for better chart data
            
            for i in range(blocks_to_check):
               block_num = latest_block_num - i
               block_details = self.quai_api.get_block_details(block_num)
               
               if block_details and 'transactions' in block_details:
                   for tx in block_details['transactions']:
                       # Only include transactions with actual data
                       if tx.get('hash') and tx.get('from') and tx.get('to'):
                           # Parse timestamp from woHeader (QUAI timestamps are in seconds)
                           wo_header = block_details.get('woHeader', {})
                           timestamp_hex = wo_header.get('timestamp', '0x0')
                           try:
                               timestamp_int = int(timestamp_hex, 16)
                               timestamp = datetime.utcfromtimestamp(timestamp_int).isoformat()
                           except (ValueError, TypeError):
                               timestamp = datetime.now(timezone.utc).isoformat()
                           
                           # Parse value
                           value_hex = tx.get('value', '0x0')
                           try:
                               value_int = int(value_hex, 16) if value_hex.startswith('0x') else int(value_hex)
                           except (ValueError, TypeError):
                               value_int = 0
                           
                           normalized_tx = {
                               'tx_hash': tx.get('hash', ''),
                               'from_address': tx.get('from', ''),
                               'to_address': tx.get('to', ''),
                               'value': value_int,
                               'direction': 'outgoing',  # Default direction
                               'block_number': block_num,
                               'timestamp': timestamp
                           }
                           
                           transactions.append(normalized_tx)
                           
                           if len(transactions) >= limit:
                               break
               
               if len(transactions) >= limit:
                   break
            
            if transactions:
                return transactions
                     
        except Exception as e:
            logger.error(f"Live transaction fetch failed: {str(e)}")
        
        # Final fallback: empty list
        return []

    def get_network_stats(self) -> Dict:
        """Get network statistics"""
        try:
            # Try to get live data first
            latest_block_num = self.quai_api.get_latest_block_number()
            
            if latest_block_num:
                total_blocks = latest_block_num
                
                # Get recent transactions count
                transactions = self.get_latest_transactions(limit=50)
                total_transactions = len(transactions)
                
                # Get unique addresses from recent transactions
                addresses = set()
                for tx in transactions:
                    if tx.get('from_address'):
                        addresses.add(tx.get('from_address'))
                    if tx.get('to_address'):
                        addresses.add(tx.get('to_address'))
                active_addresses = len(addresses)
                
                return {
                    'total_blocks': total_blocks,
                    'total_transactions': total_transactions,
                    'active_addresses': active_addresses,
                    'network_status': 'Healthy'
                }
            
        except Exception as e:
            logger.error(f"Live stats fetch failed: {str(e)}")
        
        # Fallback to database or mock data
        if not self.supabase:
            return {
                'total_blocks': 0,
                'total_transactions': 0,
                'active_addresses': 0,
                'network_status': 'API Offline'
            }
            
        try:
            # Get total blocks
            blocks_result = self.supabase.from_('blocks').select('block_number').execute()
            total_blocks = len(blocks_result.data or [])
            
            # Get total transactions
            txs_result = self.supabase.from_('transactions').select('id').execute()
            total_transactions = len(txs_result.data or [])
            
            # Get active addresses (unique wallet addresses)
            wallets_result = self.supabase.from_('wallets').select('address').execute()
            active_addresses = len(wallets_result.data or [])
            
            return {
                'total_blocks': total_blocks,
                'total_transactions': total_transactions,
                'active_addresses': active_addresses,
                'network_status': 'Healthy' if total_blocks > 0 else 'Syncing'
            }
            
        except Exception as e:
            logger.error(f"Failed to get network stats: {str(e)}")
            return {
                'total_blocks': 0,
                'total_transactions': 0,
                'active_addresses': 0,
                'network_status': 'Error'
            }

    def sync_reference_data(self):
        """Sync initial data using reference wallet"""
        try:
            # Update reference wallet
            self.update_wallet_data(self.reference_wallet)
            
            # Update latest blocks
            self.update_latest_blocks()
            
            logger.info("Reference data sync completed")
            
        except Exception as e:
            logger.error(f"Reference data sync failed: {str(e)}")