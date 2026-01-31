import requests
import os
from typing import Dict, List, Optional
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QuaiAPI:
    def __init__(self):
        self.api_key = os.getenv('QUAI_API_KEY')  # Reference wallet address
        self.rpc_url = "https://rpc.quai.network/cyprus1"
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'QuaiScan-Dashboard/1.0'
        })

    def _make_rpc_request(self, method: str, params: List = None) -> Optional[Dict]:
        """Make JSON-RPC request with error handling"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params or [],
                "id": 1
            }
            
            response = self.session.post(self.rpc_url, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'error' in data:
                logger.error(f"RPC Error: {data['error']}")
                return None
                
            return data.get('result')
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            return None
        except ValueError as e:
            logger.error(f"JSON decode failed: {str(e)}")
            return None

    def get_wallet_balance(self, address: str) -> Optional[str]:
        """Get wallet balance in wei"""
        result = self._make_rpc_request("eth_getBalance", [address, "latest"])
        return result

    def get_wallet_transactions(self, address: str, page: int = 1, offset: int = 10) -> Optional[List[Dict]]:
        """Get wallet transactions using alternative approach via blocks"""
        # Since standard txlist API may not be available, we'll get transactions from recent blocks
        # This is a simplified approach for demo purposes
        latest_block = self.get_latest_block_number()
        if not latest_block:
            return None
            
        transactions = []
        blocks_to_check = min(offset * 10, 100)  # Check last 100 blocks max
        
        for i in range(blocks_to_check):
            block_num = latest_block - i
            block_details = self.get_block_details(block_num)
            
            if block_details and 'transactions' in block_details:
                for tx in block_details['transactions']:
                    if tx.get('from', '').lower() == address.lower() or tx.get('to', '').lower() == address.lower():
                        # Add block number and timestamp to transaction
                        tx['blockNumber'] = hex(block_num)
                        tx['timeStamp'] = str(int(block_details.get('timestamp', '0x0'), 16))
                        transactions.append(tx)
                        
                        if len(transactions) >= offset:
                            return transactions
                            
        return transactions if transactions else None

    def get_latest_block_number(self) -> Optional[int]:
        """Get latest block number"""
        result = self._make_rpc_request("eth_blockNumber")
        
        if result:
            try:
                return int(result, 16)
            except ValueError:
                return None
        return None

    def get_block_details(self, block_number: int) -> Optional[Dict]:
        """Get block details by number"""
        result = self._make_rpc_request("eth_getBlockByNumber", [hex(block_number), True])
        return result

    def get_transaction_details(self, tx_hash: str) -> Optional[Dict]:
        """Get transaction details"""
        result = self._make_rpc_request("eth_getTransactionByHash", [tx_hash])
        return result

    def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict]:
        """Get transaction receipt"""
        result = self._make_rpc_request("eth_getTransactionReceipt", [tx_hash])
        return result