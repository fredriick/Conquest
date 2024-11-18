# Conquest 🎮 Crypto Battle Arena Telegram Bot

A multiplayer token-based battle game for Telegram with competitive mechanics and crypto rewards.

## 🌟 Features

- **Battle System**: Rock-Paper-Scissors style competitive gameplay
- **Token Economy**: Stake and win tokens in battles
- **Rating System**: Competitive ranking system with ELO-style ratings
- **Daily Bonuses**: Regular token rewards for active players
- **Token Swaps**: Convert game tokens to crypto (coming soon)
- **Leaderboard**: Track top players and rankings

## 🎯 Game Mechanics

### Battle Mode
- Players stake 50-500 tokens per match
- Winner takes 90% of the total pot
- Rating changes: ±25 points per match
- Rock-Paper-Scissors battle system

### Token System
- Starting balance: 100 tokens
- Minimum stake: 50 tokens
- Maximum stake: 500 tokens
- Daily bonus available
- Token-to-crypto swaps (upcoming)

## 🚀 Getting Started

### Prerequisites
- Python 3.10 or higher
- Telegram Bot Token
- Virtual Environment (recommended)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/crypto-battle-arena.git
cd crypto-battle-arena
```

2. Create and activate virtual environment:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

5. Run the bot:
```bash
python run.py
```

## 🎮 How to Play

1. Start the bot:
   - Open Telegram
   - Search for your bot
   - Send `/start` command

2. Main Commands:
   - `/start` - Initialize account and show menu
   - `/battle` - Enter Battle Mode
   - `/balance` - Check token balance
   - `/daily` - Claim daily bonus
   - `/leaderboard` - View top players
   - `/swap` - Swap tokens for crypto

3. Battle Instructions:
   - Click "⚔️ Battle Mode"
   - Choose stake amount (50-500 tokens)
   - Wait for opponent
   - Make your move (Rock/Paper/Scissors)
   - Winner takes 90% of pot

## 💾 Database Structure

### Users Table
- `id`: User's Telegram ID
- `tokens`: Current token balance
- `last_daily`: Last daily bonus claim
- `wins`: Total wins
- `losses`: Total losses
- `rating`: Player rating (default: 1000)

### Game Sessions Table
- `id`: Game session ID
- `player1_id`: First player's ID
- `player2_id`: Second player's ID
- `stake`: Battle stake amount
- `status`: Game status
- `winner_id`: Winner's ID
- `created_at`: Game creation timestamp

### Token Transactions Table
- `id`: Transaction ID
- `user_id`: User's ID
- `amount`: Transaction amount
- `transaction_type`: Type of transaction
- `timestamp`: Transaction timestamp

## 🛡️ Security Features

- Database transaction safety
- Input validation
- Error handling
- Anti-spam measures
- Token balance verification

## 🔄 Game Flow

1. User Registration
   - Automatic on first `/start`
   - Initial 100 token balance
   - Default 1000 rating

2. Matchmaking
   - Manual matching system
   - Stake amount verification
   - Player state tracking

3. Battle System
   - Simultaneous move selection
   - Automatic result calculation
   - Immediate token distribution
   - Rating updates

4. Reward Distribution
   - Winner receives 90% of pot
   - Automatic token transfer
   - Transaction logging

## 🔧 Maintenance

### Database Backup
- SQLite database file: `game.db`
- Regular backups recommended
- Transaction logging enabled

### Error Handling
- Comprehensive error catching
- User-friendly error messages
- Detailed error logging

## 📝 Future Updates

1. Advanced Features
   - Automated matchmaking
   - Tournament mode
   - Achievement system
   - More game modes

2. Technical Improvements
   - PostgreSQL migration
   - Enhanced anti-cheat
   - Performance optimization
   - API rate limiting

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built with python-telegram-bot
- Inspired by classic battle games
- Community feedback and support
