import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
from dotenv import load_dotenv
import logging
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict

# Load environment variables and setup logging
load_dotenv()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Database functions
def setup_database():
    # Delete existing database if it exists
    try:
        os.remove('game.db')
    except OSError:
        pass

    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY,
                  tokens INTEGER DEFAULT 100,
                  last_daily TEXT DEFAULT '',
                  wins INTEGER DEFAULT 0,
                  losses INTEGER DEFAULT 0,
                  rating INTEGER DEFAULT 1000,
                  character_class TEXT,
                  referral_code TEXT,
                  referrals INTEGER DEFAULT 0,
                  used_referral INTEGER DEFAULT 0)''')
    
    # Game sessions table
    c.execute('''CREATE TABLE IF NOT EXISTS game_sessions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  player1_id INTEGER,
                  player2_id INTEGER,
                  stake INTEGER,
                  status TEXT,
                  winner_id INTEGER,
                  created_at TEXT,
                  FOREIGN KEY (player1_id) REFERENCES users (id),
                  FOREIGN KEY (player2_id) REFERENCES users (id))''')
    
    # Token transactions table
    c.execute('''CREATE TABLE IF NOT EXISTS token_transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  amount INTEGER,
                  transaction_type TEXT,
                  timestamp TEXT,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    c.execute("SELECT id, tokens, last_daily, wins, losses, rating, character_class, referral_code, referrals, used_referral FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    if user is None:
        return None
    return {
        "id": user[0],
        "tokens": user[1],
        "last_daily": user[2],
        "wins": user[3],
        "losses": user[4],
        "rating": user[5],
        "character_class": user[6],
        "referral_code": user[7],
        "referrals": user[8],
        "used_referral": user[9]
    }

def update_user_data(user_id, tokens, last_daily=None, wins=None, losses=None, rating=None, character_class=None, referrals=None, used_referral=None):
    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    if last_daily and wins and losses and rating:
        c.execute("UPDATE users SET tokens=?, last_daily=?, wins=?, losses=?, rating=? WHERE id=?", (tokens, last_daily, wins, losses, rating, user_id))
    elif last_daily:
        c.execute("UPDATE users SET tokens=?, last_daily=? WHERE id=?", (tokens, last_daily, user_id))
    elif character_class:
        c.execute("UPDATE users SET tokens=?, character_class=? WHERE id=?", (tokens, character_class, user_id))
    elif referrals is not None:
        c.execute("UPDATE users SET tokens=?, referrals=? WHERE id=?", (tokens, referrals, user_id))
    elif used_referral is not None:
        c.execute("UPDATE users SET tokens=?, used_referral=? WHERE id=?", (tokens, used_referral, user_id))
    else:
        c.execute("UPDATE users SET tokens=? WHERE id=?", (tokens, user_id))
    conn.commit()
    conn.close()

def create_user(user_id, tokens):
    try:
        conn = sqlite3.connect('game.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (id, tokens, last_daily, wins, losses, rating) VALUES (?, ?, '', 0, 0, 1000)", 
                 (user_id, tokens))
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False

# Character Classes and Special Events System
CHARACTER_CLASSES = {
    'warrior': {
        'name': '⚔️ Warrior',
        'description': 'Bonus token rewards from battles',
        'perk': lambda reward: int(reward * 1.2),  # 20% more tokens
        'cost': 1000
    },
    'mage': {
        'name': '🔮 Mage',
        'description': 'Reduced power-up costs',
        'perk': lambda cost: int(cost * 0.8),  # 20% cheaper power-ups
        'cost': 1000
    },
    'rogue': {
        'name': '🗡️ Rogue',
        'description': 'Chance to steal extra tokens',
        'perk': lambda stake: random.randint(0, int(stake * 0.1)),  # Up to 10% extra tokens
        'cost': 1000
    }
}

SPECIAL_EVENTS = {
    'double_rewards': {
        'name': '💰 Double Rewards Weekend',
        'description': 'All battle rewards are doubled',
        'modifier': lambda reward: reward * 2,
        'duration': timedelta(days=2)
    },
    'power_hour': {
        'name': '⚡ Power Hour',
        'description': 'Power-ups are 50% off',
        'modifier': lambda cost: cost // 2,
        'duration': timedelta(hours=1)
    },
    'tournament_frenzy': {
        'name': '🏆 Tournament Frenzy',
        'description': 'Tournament entry fees reduced by 50%',
        'modifier': lambda fee: fee // 2,
        'duration': timedelta(hours=3)
    }
}

# Referral System
REFERRAL_REWARDS = {
    'referrer': 200,  # Tokens for referring
    'referee': 100    # Tokens for being referred
}

def show_character_classes(update: Update, context: CallbackContext) -> None:
    """Show available character classes and allow purchase."""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    if not user_data:
        update.message.reply_text("❌ Please start the bot first with /start")
        return
    
    message = "🎭 Character Classes:\n\n"
    keyboard = []
    
    current_class = user_data.get('character_class', None)
    
    for class_id, char_class in CHARACTER_CLASSES.items():
        status = "✅ Selected" if class_id == current_class else f"💰 Cost: {char_class['cost']} tokens"
        message += f"{char_class['name']}\n"
        message += f"   {char_class['description']}\n"
        message += f"   {status}\n\n"
        
        if class_id != current_class:
            keyboard.append([InlineKeyboardButton(
                f"Select {char_class['name']} ({char_class['cost']} tokens)",
                callback_data=f"select_class_{class_id}"
            )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(message, reply_markup=reply_markup)

def handle_class_selection(update: Update, context: CallbackContext) -> None:
    """Handle character class selection."""
    query = update.callback_query
    query.answer()
    
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    if not user_data:
        query.edit_message_text("❌ Please start the bot first with /start")
        return
    
    class_id = query.data.split('_')[-1]  # Get the last part after splitting
    char_class = CHARACTER_CLASSES.get(class_id)
    
    if not char_class:
        query.edit_message_text("❌ Invalid character class!")
        return
    
    if user_data['tokens'] < char_class['cost']:
        query.edit_message_text(f"❌ Not enough tokens! You need {char_class['cost']} tokens.")
        return
    
    # Update user's tokens and character class
    cursor = get_db().cursor()
    cursor.execute(
        "UPDATE users SET tokens = ?, character_class = ? WHERE id = ?",
        (user_data['tokens'] - char_class['cost'], class_id, user_id)
    )
    get_db().commit()
    
    message = (
        f"✨ Character class selected!\n\n"
        f"{char_class['name']}\n"
        f"{char_class['description']}\n"
        f"Use your new powers wisely!"
    )
    query.edit_message_text(message, reply_markup=get_main_menu_keyboard())

def start_special_event() -> None:
    """Start a random special event."""
    event_id = random.choice(list(SPECIAL_EVENTS.keys()))
    event = SPECIAL_EVENTS[event_id]
    
    active_events[event_id] = {
        'name': event['name'],
        'description': event['description'],
        'end_time': datetime.now() + event['duration'],
        'modifier': event['modifier']
    }
    
    # Notify all users about the event
    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users")
    users = c.fetchall()
    conn.close()
    
    message = (
        f"🎉 Special Event Started!\n\n"
        f"{event['name']}\n"
        f"{event['description']}\n"
        f"Duration: {event['duration']}"
    )
    
    for user_id in users:
        try:
            context.bot.send_message(user_id[0], message)
        except:
            continue

def check_active_events() -> dict:
    """Check and clean up expired events."""
    current_time = datetime.now()
    expired = []
    
    for event_id, event in active_events.items():
        if current_time > event['end_time']:
            expired.append(event_id)
    
    for event_id in expired:
        del active_events[event_id]
    
    return active_events

def apply_event_modifiers(value: int, event_type: str) -> int:
    """Apply active event modifiers to a value."""
    events = check_active_events()
    modified_value = value
    
    for event in events.values():
        if event_type in event['name'].lower():
            modified_value = event['modifier'](modified_value)
    
    return modified_value

def generate_referral_code(user_id: int) -> str:
    """Generate a unique referral code for a user."""
    return f"REF{user_id}{random.randint(1000, 9999)}"

def show_referral_info(update: Update, context: CallbackContext) -> None:
    """Show user's referral code and statistics."""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    if not user_data:
        update.message.reply_text("❌ Please start the bot first with /start")
        return
    
    referral_code = user_data.get('referral_code')
    if not referral_code:
        referral_code = generate_referral_code(user_id)
        conn = sqlite3.connect('game.db')
        c = conn.cursor()
        c.execute(
            "UPDATE users SET referral_code = ? WHERE id = ?",
            (referral_code, user_id)
        )
        conn.commit()
        conn.close()
        
        # Update user_data with new referral code
        user_data['referral_code'] = referral_code
    
    referrals = user_data.get('referrals', 0)
    total_rewards = referrals * REFERRAL_REWARDS['referrer']
    
    message = (
        f"👥 Your Referral Information\n\n"
        f"Referral Code: {referral_code}\n"
        f"Total Referrals: {referrals}\n"
        f"Total Rewards Earned: {total_rewards} tokens\n\n"
        f"Share your referral code with friends!\n"
        f"They'll receive {REFERRAL_REWARDS['referee']} tokens\n"
        f"You'll receive {REFERRAL_REWARDS['referrer']} tokens"
    )
    
    update.message.reply_text(message, reply_markup=get_main_menu_keyboard())

def handle_referral_code(update: Update, context: CallbackContext) -> None:
    """Handle referral code redemption."""
    if len(context.args) != 1:
        update.message.reply_text(
            "❌ Please provide a referral code.\n"
            "Usage: /referral REF12345"
        )
        return
    
    referral_code = context.args[0]
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    if not user_data:
        update.message.reply_text("❌ Please start the bot first with /start")
        return
    
    if user_data.get('used_referral'):
        update.message.reply_text("❌ You have already used a referral code!")
        return
    
    # Find referrer
    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE referral_code = ?", (referral_code,))
    referrer = c.fetchone()
    
    if not referrer or referrer[0] == user_id:
        update.message.reply_text("❌ Invalid referral code!")
        return
    
    # Update referrer
    referrer_data = get_user_data(referrer[0])
    update_user_data(
        referrer[0],
        referrer_data['tokens'] + REFERRAL_REWARDS['referrer'],
        referrals=referrer_data.get('referrals', 0) + 1
    )
    
    # Update referee
    update_user_data(
        user_id,
        user_data['tokens'] + REFERRAL_REWARDS['referee'],
        used_referral=True
    )
    
    update.message.reply_text(
        f"✨ Referral code redeemed!\n"
        f"You received {REFERRAL_REWARDS['referee']} tokens!"
    )

# Game state management
active_matches = {}
matchmaking_queue = []
player_states = defaultdict(dict)
active_tournaments = {}
tournament_queue = []
active_events = {}

def get_main_menu_keyboard():
    keyboard = [
        [KeyboardButton("⚔️ Battle Mode"), KeyboardButton("💰 Check Balance")],
        [KeyboardButton("🎁 Daily Bonus"), KeyboardButton("🏆 Leaderboard")],
        [KeyboardButton("💱 Swap Tokens"), KeyboardButton("🏆 Tournament Mode")],
        [KeyboardButton("🎭 Character Classes"), KeyboardButton("👥 Referral Info")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    user_id = user.id
    user_data = get_user_data(user_id)
    if not user_data:
        create_user(user_id, 100)
        user_data = get_user_data(user_id)
    
    welcome_message = (
        f"🎉 Welcome to the Crypto Battle Arena, {user.mention_html()}! 🎉\n\n"
        f"You currently have {user_data['tokens']} tokens.\n"
        f"Stats: Wins: {user_data['wins']} | Losses: {user_data['losses']} | Rating: {user_data['rating']}\n\n"
        "What would you like to do? Use the menu below or type a command:\n"
        "/battle - Enter Battle Mode\n"
        "/balance - Check your balance\n"
        "/daily - Claim daily bonus\n"
        "/leaderboard - View top players\n"
        "/swap - Swap tokens for crypto\n"
        "/tournament - Create or join a tournament\n"
        "/referral - Redeem a referral code\n"
        "/classes - View character classes\n"
        "/referralinfo - View your referral information"
    )
    update.message.reply_html(welcome_message, reply_markup=get_main_menu_keyboard())

def handle_menu_choice(update: Update, context: CallbackContext) -> None:
    text = update.message.text
    user_id = update.effective_user.id

    if text == "⚔️ Battle Mode":
        start_battle(update, context)
    elif text == "💰 Check Balance":
        check_balance(update, context)
    elif text == "🎁 Daily Bonus":
        claim_daily_bonus(update, context)
    elif text == "🏆 Leaderboard":
        show_leaderboard(update, context)
    elif text == "💱 Swap Tokens":
        show_swap_options(update, context)
    elif text == "🏆 Tournament Mode":
        create_tournament(update, context)
    elif text == "🎭 Character Classes":
        show_character_classes(update, context)
    elif text == "👥 Referral Info":
        show_referral_info(update, context)
    else:
        update.message.reply_text("Please use the menu buttons or commands.", reply_markup=get_main_menu_keyboard())

def check_balance(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    update.message.reply_text(
        f"💰 Your current balance is {user_data['tokens']} tokens.",
        reply_markup=get_main_menu_keyboard()
    )

def start_battle(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    user_id = user.id
    user_data = get_user_data(user_id)
    
    if not user_data:
        if not create_user(user_id, 100):
            update.message.reply_text("Error creating user account. Please try /start again.")
            return
        user_data = get_user_data(user_id)
        if not user_data:
            update.message.reply_text("Error accessing user data. Please try again later.")
            return
    
    if user_data['tokens'] < 50:
        update.message.reply_text(
            "❌ You need at least 50 tokens to enter a battle.\n"
            f"Your current balance: {user_data['tokens']} tokens\n"
            "Try claiming your daily bonus or winning more tokens!",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    keyboard = [
        [InlineKeyboardButton("50 tokens", callback_data="stake_50")],
        [InlineKeyboardButton("100 tokens", callback_data="stake_100")],
        [InlineKeyboardButton("200 tokens", callback_data="stake_200")],
        [InlineKeyboardButton("500 tokens", callback_data="stake_500")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "⚔️ Welcome to Battle Mode!\n\n"
        "Choose your stake amount:",
        reply_markup=reply_markup
    )

def handle_battle_stake(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    
    user_id = query.from_user.id
    stake = int(query.data.split('_')[1])
    user_data = get_user_data(user_id)
    
    if not user_data:
        query.edit_message_text("❌ Error: User data not found. Please try /start again.")
        return
    
    if user_data["tokens"] < stake:
        query.edit_message_text(
            f"❌ You don't have enough tokens for this stake ({stake} tokens required).\n"
            f"Your current balance: {user_data['tokens']} tokens"
        )
        return
    
    # Add player to matchmaking queue
    player_data = {
        "user_id": user_id,
        "stake": stake,
        "username": query.from_user.username or query.from_user.first_name,
        "rating": user_data["rating"]
    }
    
    # Check if there's a matching opponent
    opponent = None
    for i, p in enumerate(matchmaking_queue):
        if p["stake"] == stake and p["user_id"] != user_id:
            opponent = matchmaking_queue.pop(i)
            break
    
    if opponent:
        # Start battle session
        start_battle_session(query, context, player_data, opponent)
    else:
        # Add to queue
        matchmaking_queue.append(player_data)
        query.edit_message_text(
            f"⌛ Waiting for an opponent...\n"
            f"Stake amount: {stake} tokens\n"
            f"Your rating: {user_data['rating']}\n\n"
            "The battle will start automatically when an opponent is found."
        )

def start_battle_session(query: CallbackQuery, context: CallbackContext, 
                        player1: dict, player2: dict) -> None:
    game_id = random.randint(1000000, 9999999)
    stake = player1["stake"]
    
    # Verify both players have enough tokens
    for player in [player1, player2]:
        user_data = get_user_data(player["user_id"])
        if not user_data or user_data["tokens"] < stake:
            query.edit_message_text(
                "❌ Battle cancelled: One of the players doesn't have enough tokens."
            )
            return
    
    try:
        # Create game session in database
        conn = sqlite3.connect('game.db')
        c = conn.cursor()
        c.execute("""
            INSERT INTO game_sessions (player1_id, player2_id, stake, status, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (player1["user_id"], player2["user_id"], stake, "active", datetime.now().isoformat()))
        conn.commit()
        
        # Deduct stakes from both players
        for player in [player1, player2]:
            user_data = get_user_data(player["user_id"])
            new_balance = user_data["tokens"] - stake
            c.execute("UPDATE users SET tokens = ? WHERE id = ?", (new_balance, player["user_id"]))
        conn.commit()
        conn.close()
        
        # Initialize game state
        active_matches[game_id] = {
            "player1": player1,
            "player2": player2,
            "stake": stake,
            "moves": {},
            "started_at": datetime.now().isoformat()
        }
        
        # Create battle UI for both players
        keyboard = [
            [InlineKeyboardButton("🗿 Rock", callback_data=f"move_{game_id}_rock")],
            [InlineKeyboardButton("📄 Paper", callback_data=f"move_{game_id}_paper")],
            [InlineKeyboardButton("✂️ Scissors", callback_data=f"move_{game_id}_scissors")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        battle_message = (
            f"⚔️ Battle Started! Game #{game_id}\n\n"
            f"🆚 {player1['username']} vs {player2['username']}\n"
            f"💰 Stake: {stake} tokens\n"
            f"🏆 Prize Pool: {stake * 2} tokens\n\n"
            "Make your move!"
        )
        
        # Send battle UI to both players
        context.bot.send_message(
            player1["user_id"],
            battle_message,
            reply_markup=reply_markup
        )
        context.bot.send_message(
            player2["user_id"],
            battle_message,
            reply_markup=reply_markup
        )
        
        # Update the original message
        query.edit_message_text(
            f"✅ Battle started! Check your private messages with the bot."
        )
    except Exception as e:
        print(f"Error in start_battle_session: {e}")
        query.edit_message_text(
            "❌ An error occurred while starting the battle. Please try again."
        )

def handle_battle_move(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    
    # Parse game ID and move from callback data
    _, game_id, move = query.data.split('_')
    game_id = int(game_id)
    user_id = query.from_user.id
    
    if game_id not in active_matches:
        query.edit_message_text("❌ This battle has already ended or expired.")
        return
    
    game = active_matches[game_id]
    
    # Verify player is in the game
    if user_id != game["player1"]["user_id"] and user_id != game["player2"]["user_id"]:
        query.edit_message_text("❌ You are not a participant in this battle.")
        return
    
    # Check if player already made a move
    if user_id in game["moves"]:
        query.edit_message_text(
            f"✋ You've already chosen {game['moves'][user_id]}.\n"
            "Waiting for your opponent..."
        )
        return
    
    # Record the move
    game["moves"][user_id] = move
    
    # Update UI for this player
    query.edit_message_text(
        f"✅ You chose {move}!\n"
        "Waiting for your opponent..."
    )
    
    # If both players have moved, resolve the battle immediately
    if len(game["moves"]) == 2:
        resolve_battle(context, game_id)
        return

def resolve_battle(context: CallbackContext, game_id: int) -> None:
    try:
        game = active_matches[game_id]
        p1_id = game["player1"]["user_id"]
        p2_id = game["player2"]["user_id"]
        p1_move = game["moves"][p1_id]
        p2_move = game["moves"][p2_id]
        stake = game["stake"]
        
        # Determine winner
        moves = {"rock": 0, "paper": 1, "scissors": 2}
        p1_val = moves[p1_move]
        p2_val = moves[p2_move]
        
        # Calculate result (0 = draw, 1 = p1 wins, 2 = p2 wins)
        result = (p1_val - p2_val) % 3
        
        # Get user data
        p1_data = get_user_data(p1_id)
        p2_data = get_user_data(p2_id)
        
        if not p1_data or not p2_data:
            context.bot.send_message(p1_id, "❌ Error: Could not resolve battle. Please contact support.")
            context.bot.send_message(p2_id, "❌ Error: Could not resolve battle. Please contact support.")
            del active_matches[game_id]
            return
        
        # Update game session status
        conn = sqlite3.connect('game.db')
        c = conn.cursor()
        
        try:
            if result == 0:  # Draw
                # Return stakes to both players
                p1_tokens = p1_data["tokens"] + stake
                p2_tokens = p2_data["tokens"] + stake
                winner_id = None
                result_message = (
                    f"🤝 It's a draw!\n"
                    f"Player 1 chose: {p1_move}\n"
                    f"Player 2 chose: {p2_move}\n"
                    f"Stakes have been returned."
                )
            else:
                # Determine winner and loser
                winner_id = p1_id if result == 1 else p2_id
                loser_id = p2_id if result == 1 else p1_id
                
                # Calculate prize (90% of total pot)
                total_pot = stake * 2
                prize = int(total_pot * 0.9)
                
                # Update tokens
                if winner_id == p1_id:
                    p1_data["wins"] += 1
                    p2_data["losses"] += 1
                    p1_tokens = p1_data["tokens"] + prize
                    p2_tokens = p2_data["tokens"]
                else:
                    p2_data["wins"] += 1
                    p1_data["losses"] += 1
                    p1_tokens = p1_data["tokens"]
                    p2_tokens = p2_data["tokens"] + prize
                
                # Update ratings (±25 points)
                rating_change = 25
                if winner_id == p1_id:
                    p1_data["rating"] += rating_change
                    p2_data["rating"] -= rating_change
                else:
                    p1_data["rating"] -= rating_change
                    p2_data["rating"] += rating_change
                
                result_message = (
                    f"🏆 {game['player1' if winner_id == p1_id else 'player2']['username']} wins!\n"
                    f"Player 1 chose: {p1_move}\n"
                    f"Player 2 chose: {p2_move}\n"
                    f"Prize: {prize} tokens (90% of pot)"
                )
            
            # Update user data in database
            c.execute("UPDATE users SET tokens=?, wins=?, losses=?, rating=? WHERE id=?",
                     (p1_tokens, p1_data["wins"], p1_data["losses"], p1_data["rating"], p1_id))
            c.execute("UPDATE users SET tokens=?, wins=?, losses=?, rating=? WHERE id=?",
                     (p2_tokens, p2_data["wins"], p2_data["losses"], p2_data["rating"], p2_id))
            
            conn.commit()
            
            # Send result messages to both players
            context.bot.send_message(
                p1_id,
                result_message + f"\n\nYour new balance is {p1_tokens} tokens.",
                reply_markup=get_main_menu_keyboard()
            )
            context.bot.send_message(
                p2_id,
                result_message + f"\n\nYour new balance is {p2_tokens} tokens.",
                reply_markup=get_main_menu_keyboard()
            )
            
        except Exception as e:
            print(f"Database error in resolve_battle: {e}")
            conn.rollback()
            context.bot.send_message(p1_id, "❌ An error occurred while resolving the battle.")
            context.bot.send_message(p2_id, "❌ An error occurred while resolving the battle.")
        finally:
            conn.close()
            # Clean up the match
            del active_matches[game_id]
            
    except Exception as e:
        print(f"Error in resolve_battle: {e}")
        try:
            context.bot.send_message(p1_id, "❌ An error occurred while resolving the battle.")
            context.bot.send_message(p2_id, "❌ An error occurred while resolving the battle.")
            del active_matches[game_id]
        except:
            pass

def show_swap_options(update: Update, context: CallbackContext) -> None:
    user_data = get_user_data(update.effective_user.id)
    min_swap = 1000
    
    if user_data["tokens"] < min_swap:
        update.message.reply_text(
            f"❌ You need at least {min_swap} tokens to swap for crypto.\n"
            f"Current balance: {user_data['tokens']} tokens"
        )
        return
    
    keyboard = [
        [InlineKeyboardButton("1000 Tokens → 0.001 ETH", callback_data="swap_1000_eth")],
        [InlineKeyboardButton("5000 Tokens → 0.005 ETH", callback_data="swap_5000_eth")],
        [InlineKeyboardButton("10000 Tokens → 0.01 ETH", callback_data="swap_10000_eth")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "💱 Token Swap\n\n"
        "Choose amount to swap for ETH:\n"
        "(You'll need to provide your ETH address)",
        reply_markup=reply_markup
    )

def claim_daily_bonus(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    now = datetime.now().strftime('%Y-%m-%d')
    if user_data["last_daily"] == now:
        update.message.reply_text(
            '❌ You already claimed your daily bonus today. Come back tomorrow!',
            reply_markup=get_main_menu_keyboard()
        )
        return

    bonus = 50
    user_data["tokens"] += bonus
    update_user_data(user_id, user_data["tokens"], now)
    update.message.reply_text(
        f'🎁 You claimed your daily bonus of {bonus} tokens.\n\nYour new balance is {user_data["tokens"]} tokens.',
        reply_markup=get_main_menu_keyboard()
    )

def show_leaderboard(update: Update, context: CallbackContext) -> None:
    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    c.execute("SELECT id, tokens FROM users ORDER BY tokens DESC LIMIT 5")
    top_users = c.fetchall()
    conn.close()

    message = "🏆 Top 5 Players 🏆\n\n"
    for i, (user_id, tokens) in enumerate(top_users, 1):
        message += f"{i}. User {user_id}: {tokens} tokens\n"

    update.message.reply_text(message, reply_markup=get_main_menu_keyboard())

def create_tournament(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    user_data = get_user_data(user.id)
    
    if not user_data:
        update.message.reply_text("❌ Please start the bot first with /start")
        return
        
    if user_data["tokens"] < 200:
        update.message.reply_text("❌ You need at least 200 tokens to create a tournament!")
        return
    
    tournament_id = len(active_tournaments) + 1
    tournament = {
        "id": tournament_id,
        "creator": user.id,
        "players": [user.id],
        "entry_fee": 100,
        "prize_pool": 100,
        "status": "registering",
        "matches": [],
        "round": 0,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    active_tournaments[tournament_id] = tournament
    
    # Create tournament announcement keyboard
    keyboard = [
        [InlineKeyboardButton("🎮 Join Tournament", callback_data=f"join_tournament_{tournament_id}")],
        [InlineKeyboardButton("🚫 Cancel Tournament", callback_data=f"cancel_tournament_{tournament_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Deduct entry fee
    update_user_data(user.id, user_data["tokens"] - 100)
    
    message = (
        f"🏆 New Tournament Created #{tournament_id}\n\n"
        f"Entry Fee: 100 tokens\n"
        f"Current Prize Pool: 100 tokens\n"
        f"Players: 1/8\n\n"
        f"Tournament will start when 8 players join!\n"
        f"Winner takes 70% of prize pool\n"
        f"Runner-up takes 20% of prize pool\n"
        f"Semi-finalists share 10% of prize pool"
    )
    
    update.message.reply_text(message, reply_markup=reply_markup)

def handle_tournament_join(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    
    _, tournament_id = query.data.split('_')
    tournament_id = int(tournament_id)
    user = query.from_user
    user_data = get_user_data(user.id)
    
    if not user_data:
        query.edit_message_text("❌ Please start the bot first with /start")
        return
        
    if user_data["tokens"] < 100:
        query.edit_message_text("❌ You need 100 tokens to join the tournament!")
        return
    
    tournament = active_tournaments.get(tournament_id)
    if not tournament:
        query.edit_message_text("❌ Tournament not found or already ended!")
        return
        
    if user.id in tournament["players"]:
        query.edit_message_text("❌ You're already in this tournament!")
        return
        
    if len(tournament["players"]) >= 8:
        query.edit_message_text("❌ Tournament is full!")
        return
    
    # Add player and update prize pool
    tournament["players"].append(user.id)
    tournament["prize_pool"] += 100
    update_user_data(user.id, user_data["tokens"] - 100)
    
    # Update tournament message
    keyboard = [
        [InlineKeyboardButton("🎮 Join Tournament", callback_data=f"join_tournament_{tournament_id}")],
        [InlineKeyboardButton("🚫 Cancel Tournament", callback_data=f"cancel_tournament_{tournament_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"🏆 Tournament #{tournament_id}\n\n"
        f"Entry Fee: 100 tokens\n"
        f"Current Prize Pool: {tournament['prize_pool']} tokens\n"
        f"Players: {len(tournament['players'])}/8\n\n"
        f"Tournament will start when 8 players join!\n"
        f"Winner takes 70% of prize pool\n"
        f"Runner-up takes 20% of prize pool\n"
        f"Semi-finalists share 10% of prize pool"
    )
    
    query.edit_message_text(message, reply_markup=reply_markup)
    
    # Start tournament if 8 players joined
    if len(tournament["players"]) == 8:
        start_tournament_round(context, tournament_id)

def start_tournament_round(context: CallbackContext, tournament_id: int) -> None:
    tournament = active_tournaments[tournament_id]
    tournament["round"] += 1
    players = tournament["players"]
    
    if len(players) == 1:
        # Tournament ended, distribute prizes
        end_tournament(context, tournament_id)
        return
    
    # Pair players randomly
    random.shuffle(players)
    matches = []
    
    for i in range(0, len(players), 2):
        if i + 1 < len(players):
            match_id = len(active_matches) + 1
            match = {
                "id": match_id,
                "tournament_id": tournament_id,
                "player1": {"user_id": players[i]},
                "player2": {"user_id": players[i + 1]},
                "moves": {},
                "status": "active",
                "round": tournament["round"]
            }
            matches.append(match)
            active_matches[match_id] = match
    
    tournament["matches"].extend(matches)
    
    # Notify players and start matches
    for match in matches:
        p1_data = get_user_data(match["player1"]["user_id"])
        p2_data = get_user_data(match["player2"]["user_id"])
        
        keyboard = [
            [
                InlineKeyboardButton("🗿 Rock", callback_data=f"move_{match['id']}_rock"),
                InlineKeyboardButton("📄 Paper", callback_data=f"move_{match['id']}_paper"),
                InlineKeyboardButton("✂️ Scissors", callback_data=f"move_{match['id']}_scissors")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"🏆 Tournament Round {tournament['round']}\n"
            f"Make your move!\n\n"
            f"You vs Opponent\n"
            f"Rating: {p1_data['rating']} vs {p2_data['rating']}"
        )
        
        context.bot.send_message(
            match["player1"]["user_id"],
            message,
            reply_markup=reply_markup
        )
        context.bot.send_message(
            match["player2"]["user_id"],
            message,
            reply_markup=reply_markup
        )

def end_tournament(context: CallbackContext, tournament_id: int) -> None:
    tournament = active_tournaments[tournament_id]
    prize_pool = tournament["prize_pool"]
    
    # Get winner (last remaining player)
    winner_id = tournament["players"][0]
    winner_data = get_user_data(winner_id)
    
    # Calculate prizes
    winner_prize = int(prize_pool * 0.7)  # 70% to winner
    runner_up_prize = int(prize_pool * 0.2)  # 20% to runner-up
    semifinal_prize = int(prize_pool * 0.1 / 2)  # 10% split between semi-finalists
    
    # Update winner's tokens and send message
    update_user_data(winner_id, winner_data["tokens"] + winner_prize)
    
    message = (
        f"🎊 Tournament #{tournament_id} Ended!\n\n"
        f"🏆 Winner: {winner_data['username']}\n"
        f"💰 Prize: {winner_prize} tokens\n\n"
        f"Thank you for participating!"
    )
    
    # Notify all players
    for player_id in set(p["user_id"] for match in tournament["matches"] for p in [match["player1"], match["player2"]]):
        try:
            context.bot.send_message(player_id, message, reply_markup=get_main_menu_keyboard())
        except:
            continue
    
    # Clean up
    del active_tournaments[tournament_id]

def main() -> None:
    setup_database()
    load_dotenv()
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("battle", start_battle))
    dispatcher.add_handler(CommandHandler("balance", check_balance))
    dispatcher.add_handler(CommandHandler("daily", claim_daily_bonus))
    dispatcher.add_handler(CommandHandler("leaderboard", show_leaderboard))
    dispatcher.add_handler(CommandHandler("swap", show_swap_options))
    dispatcher.add_handler(CommandHandler("tournament", create_tournament))
    dispatcher.add_handler(CommandHandler("referral", handle_referral_code))
    dispatcher.add_handler(CommandHandler("classes", show_character_classes))
    dispatcher.add_handler(CommandHandler("referralinfo", show_referral_info))
    dispatcher.add_handler(CallbackQueryHandler(handle_battle_stake, pattern='^stake_[0-9]+$'))
    dispatcher.add_handler(CallbackQueryHandler(handle_battle_move, pattern='^move_[0-9]+_[a-z]+$'))
    dispatcher.add_handler(CallbackQueryHandler(handle_tournament_join, pattern='^join_tournament_[0-9]+$'))
    dispatcher.add_handler(CallbackQueryHandler(handle_class_selection, pattern='^select_class_[a-z]+$'))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_menu_choice))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()