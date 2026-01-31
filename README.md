# QuaiScan - Blockchain Analytics Dashboard

A production-grade hackathon project for visualizing Quai Network blockchain data using QUAI Scan APIs and Supabase.

## Features

- Real-time blockchain analytics dashboard
- Wallet activity monitoring
- Latest blocks and transactions visualization
- Network statistics and insights
- Clean, judge-friendly interface inspired by Etherscan

## Tech Stack

**Backend:**
- Python Flask
- Requests for API calls
- Supabase integration

**Frontend:**
- Jinja2 templates
- Tailwind CSS (CDN)
- Vanilla JavaScript (minimal)

**APIs:**
- QUAI Scan APIs (Etherscan-compatible)
- Supabase PostgreSQL

## Setup

1. **Clone and install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   Copy `.env` file and fill in your credentials:
   ```
   QUAI_API_KEY=your_quaiscan_api_key
   SUPABASE_URL=your_supabase_project_url  
   SUPABASE_KEY=your_supabase_anon_key
   ```

3. **Set up Supabase tables:**
   Run these SQL commands in your Supabase SQL editor:
   ```sql
   CREATE TABLE IF NOT EXISTS wallets (
       id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
       address TEXT UNIQUE NOT NULL,
       balance NUMERIC,
       last_updated TIMESTAMP WITH TIME ZONE
   );
   
   CREATE TABLE IF NOT EXISTS transactions (
       id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
       wallet_address TEXT,
       tx_hash TEXT UNIQUE NOT NULL,
       from_address TEXT,
       to_address TEXT,
       value NUMERIC,
       gas_used NUMERIC,
       timestamp TIMESTAMP WITH TIME ZONE,
       direction TEXT CHECK (direction IN ('incoming', 'outgoing'))
   );
   
   CREATE TABLE IF NOT EXISTS blocks (
       block_number NUMERIC PRIMARY KEY,
       tx_count NUMERIC,
       gas_used NUMERIC,
       timestamp TIMESTAMP WITH TIME ZONE
   );
   ```

4. **Run the application:**
   ```bash
   python app.py
   ```

5. **Access the dashboard:**
   Open http://localhost:5000 in your browser

## Reference Data

- Reference Wallet: `0x002624Fa55DFf0ca53aF9166B4d44c16a294C4e0`
- API Base URL: `https://api.quaiscan.io/api`

## Project Structure

```
├── app.py                 # Main Flask application
├── templates/
│   └── index.html        # Main dashboard template
├── services/
│   ├── quai_api.py       # Quai API integration
│   └── db.py            # Supabase database service
├── static/               # Static assets (if needed)
├── .env                 # Environment variables
└── requirements.txt      # Python dependencies
```

## Hackathon Notes

- Clean, professional UI design
- Error handling with graceful fallbacks
- Network status monitoring
- Judge-friendly insights and statistics
- Production-ready code structure

Built for the Quai Network hackathon competition.