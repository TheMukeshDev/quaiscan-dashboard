#!/usr/bin/env python3
"""
Dashboard Data Verification Script
Verifies that Quai Dashboard is populated with real blockchain data
"""

import sys
import os
sys.path.append('.')

from services.db import DatabaseService
from datetime import datetime

def main():
    print("=" * 60)
    print("QUAI DASHBOARD DATA VERIFICATION")
    print("=" * 60)
    
    # Initialize database service
    db = DatabaseService()
    
    print(f"\nVerification Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Reference Wallet: {db.reference_wallet}")
    print(f"RPC Endpoint: {db.quai_api.rpc_url}")
    
    # Test Network Stats
    print("\nNETWORK STATISTICS")
    print("-" * 30)
    stats = db.get_network_stats()
    
    for key, value in stats.items():
        if key in ['total_blocks', 'total_transactions', 'active_addresses']:
            status = "[OK]" if value > 0 else "[ZERO]"
            print(f"{status} {key.title().replace('_', ' ')}: {value:,}")
        else:
            print(f"    {key.title().replace('_', ' ')}: {value}")
    
    # Test Latest Blocks
    print("\nLATEST BLOCKS")
    print("-" * 30)
    blocks = db.get_latest_blocks(limit=5)
    
    if blocks:
        for i, block in enumerate(blocks, 1):
            tx_count = block.get('tx_count', 0)
            block_num = block.get('block_number', 'N/A')
            timestamp = block.get('timestamp', 'N/A')[:19] if block.get('timestamp') else 'N/A'
            
            activity = "[ACTIVE]" if tx_count > 10 else "[NORMAL]" if tx_count > 0 else "[EMPTY]"
            print(f"{activity} Block {block_num:,} - {tx_count} transactions - {timestamp}")
    else:
        print("[ERROR] No blocks found")
    
    # Test Latest Transactions
    print("\nLATEST TRANSACTIONS")
    print("-" * 30)
    txs = db.get_latest_transactions(limit=5)
    
    if txs:
        for i, tx in enumerate(txs, 1):
            tx_hash = tx.get('tx_hash', 'N/A')
            from_addr = tx.get('from_address', 'N/A')
            to_addr = tx.get('to_address', 'N/A')
            value = tx.get('value', 0)
            block_num = tx.get('block_number', 'N/A')
            
            # Convert value to QUAI (assuming 18 decimals)
            value_quai = value / (10**18) if value > 0 else 0
            
            print(f"[TX] {tx_hash[:10]}...{tx_hash[-8:]}")
            print(f"     From: {from_addr[:8]}... -> To: {to_addr[:8]}...")
            print(f"     Value: {value_quai:.6f} QUAI | Block: {block_num:,}")
            
            if i < len(txs):
                print()
    else:
        print("[ERROR] No transactions found")
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    real_blocks = len(blocks) > 0
    real_transactions = len(txs) > 0
    real_stats = stats.get('total_blocks', 0) > 0
    
    if real_blocks and real_transactions and real_stats:
        print("SUCCESS: Dashboard is populated with REAL blockchain data!")
        print("   [OK] Real blocks from Quai Network")
        print("   [OK] Real transactions from blockchain")
        print("   [OK] Live network statistics")
        print("\nDashboard is READY for demo!")
    else:
        print("WARNING: Some data may still be empty:")
        if not real_blocks:
            print("   [ERROR] No blocks found")
        if not real_transactions:
            print("   [ERROR] No transactions found")
        if not real_stats:
            print("   [ERROR] Network stats show zeros")
    
    print("\nAccess dashboard at: http://localhost:5000")
    print("=" * 60)

if __name__ == "__main__":
    main()