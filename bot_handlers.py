from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext, ConversationHandler
from telegram.ext import Updater
from db import SessionLocal, Order
from utils import calc_fee_and_receive
import os

# Conversation states
(SEND_TYPE, RECEIVE_TYPE, SEND_AMOUNT, RECEIVE_ADDRESS, OVERVIEW_CONFIRM, WAIT_FOR_TX, WAIT_FOR_PROOF) = range(7)

# sample available types
SEND_OPTIONS = ["bKash_BDT", "Nagad_BDT", "Rocket_BDT", "Payeer_USD", "USDT_TRC20", "USDT_ERC20"]

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Welcome! Exchange service ready.\nUse /exchange to create an order.")
    
def exchange_start(update: Update, context: CallbackContext):
    keyboard = [[InlineKeyboardButton(x, callback_data=f"send|{x}") for x in SEND_OPTIONS[:3]],
                [InlineKeyboardButton(x, callback_data=f"send|{x}") for x in SEND_OPTIONS[3:]]]
    reply = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Choose your *Send via* option:", reply_markup=reply, parse_mode=ParseMode.MARKDOWN)
    return SEND_TYPE

def send_type_cb(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data.split("|")[1]
    context.user_data['send_type'] = data
    # ask receive type
    options = [o for o in SEND_OPTIONS if o != data]
    keyboard = [[InlineKeyboardButton(x, callback_data=f"recv|{x}")] for x in options]
    query.edit_message_text(f"Selected *Send via*: `{data}`\nNow choose *Receive via*:", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    return RECEIVE_TYPE

def recv_cb(update: Update, context: CallbackContext):
    q = update.callback_query; q.answer()
    data = q.data.split("|")[1]
    context.user_data['receive_type'] = data
    q.edit_message_text(f"Selected *Receive via*: `{data}`\nEnter send amount (number). If send method is BDT enter BDT amount, if USDT enter USD amount.", parse_mode=ParseMode.MARKDOWN)
    return SEND_AMOUNT

def got_amount(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    try:
        amt = float(text)
        if amt <= 0:
            raise ValueError
    except:
        update.message.reply_text("Invalid amount. Enter a valid number.")
        return SEND_AMOUNT
    context.user_data['send_amount'] = amt
    update.message.reply_text("Enter receive address (e.g. USDT wallet or leave '-' if not needed):")
    return RECEIVE_ADDRESS

def got_address(update: Update, context: CallbackContext):
    addr = update.message.text.strip()
    context.user_data['receive_address'] = addr
    # calculate fee & receive amount
    fee, receive_amount = calc_fee_and_receive(context.user_data['send_type'], context.user_data['receive_type'], context.user_data['send_amount'])
    context.user_data['fee'] = fee
    context.user_data['receive_amount'] = receive_amount
    # preview
    send_type = context.user_data['send_type']
    receive_type = context.user_data['receive_type']
    send_amount = context.user_data['send_amount']
    receive_address = addr
    payment_to = "01983268976"  # example; you may set dynamic by send_type
    context.user_data['payment_to'] = payment_to

    overview = f"""💱 Overview:
Send via: {send_type}
Receive via: {receive_type}
Send amount: {send_amount}
Fee: {fee}
Receive amount: {receive_amount}
Receive address: {receive_address}

Send your payment to: {payment_to}
📌 Personal number – send money to this number

After sending, press ✅ Yes I sent or ❌ Cancel."""
    keyboard = [[InlineKeyboardButton("✅ Yes I sent", callback_data="confirm_yes"), InlineKeyboardButton("❌ Cancel", callback_data="confirm_no")]]
    update.message.reply_text(overview, reply_markup=InlineKeyboardMarkup(keyboard))
    return OVERVIEW_CONFIRM

def overview_confirm_cb(update: Update, context: CallbackContext):
    q = update.callback_query; q.answer()
    if q.data == "confirm_no":
        q.edit_message_text("Order cancelled. Use /exchange to start again.")
        context.user_data.clear()
        return ConversationHandler.END
    else:
        q.edit_message_text("Okay — please send transaction ID / transaction reference now (text). You may also send a screenshot as proof after sending tx id.")
        return WAIT_FOR_TX

def got_tx(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    context.user_data['tx_id'] = text
    update.message.reply_text("TX/Ref received. Optionally send screenshot proof (photo) now, or type /skip to finish.")
    return WAIT_FOR_PROOF

def got_proof_photo(update: Update, context: CallbackContext):
    photo = update.message.photo[-1]
    file_id = photo.file_id
    context.user_data['proof_file_id'] = file_id
    return finalize_order(update, context)

def skip_proof(update: Update, context: CallbackContext):
    return finalize_order(update, context)

def finalize_order(update: Update, context: CallbackContext):
    # Save order to DB
    db = SessionLocal()
    o = Order(
        user_id=update.effective_user.id,
        username=update.effective_user.username or "",
        send_type=context.user_data['send_type'],
        receive_type=context.user_data['receive_type'],
        send_amount=context.user_data['send_amount'],
        fee=context.user_data['fee'],
        receive_amount=context.user_data['receive_amount'],
        receive_address=context.user_data['receive_address'],
        payment_to=context.user_data.get('payment_to'),
        tx_id=context.user_data.get('tx_id'),
        proof_file_id=context.user_data.get('proof_file_id')
    )
    db.add(o)
    db.commit()
    db.refresh(o)

    # Notify user
    update.message.reply_text(f"✅ Order submitted! Your order id: #{o.id}\nAdmin will check and update status soon.")
    # Notify admins
    ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip()]
    from telegram import Bot
    bot = Bot(token=os.getenv("BOT_TOKEN"))
    summary = f"📥 New Order #{o.id}\nUser: @{o.username or update.effective_user.full_name} ({o.user_id})\nSend: {o.send_amount} via {o.send_type}\nReceive: {o.receive_amount} ({o.receive_type})\nAddress: {o.receive_address}\nTX: {o.tx_id or '-'}"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Mark Complete", callback_data=f"admin|complete|{o.id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"admin|reject|{o.id}")
    ]])
    for aid in ADMIN_IDS:
        try:
            bot.send_message(chat_id=aid, text=summary, reply_markup=keyboard)
            if o.proof_file_id:
                bot.send_photo(chat_id=aid, photo=o.proof_file_id)
        except Exception as e:
            print("admin notify error", e)
    db.close()
    context.user_data.clear()
    return ConversationHandler.END

# Admin callbacks to complete/reject
def admin_action_cb(update: Update, context: CallbackContext):
    q = update.callback_query; q.answer()
    parts = q.data.split("|")
    if len(parts) != 3: return
    _, action, oid = parts
    db = SessionLocal()
    order = db.query(Order).filter(Order.id==int(oid)).first()
    if not order:
        q.edit_message_text("Order not found.")
        db.close()
        return
    if action == "complete":
        order.status = "Completed"
        db.commit()
        # notify user
        context.bot.send_message(chat_id=order.user_id, text=f"✅ Your Order #{order.id} marked *Completed* by admin.", parse_mode=ParseMode.MARKDOWN)
        q.edit_message_text(f"Order #{order.id} marked Completed.")
    elif action == "reject":
        order.status = "Rejected"
        order.admin_note = "Please provide correct details"  # admin can edit note later
        db.commit()
        context.bot.send_message(chat_id=order.user_id, text=f"❌ Your Order #{order.id} was *Rejected* by admin. Note: {order.admin_note}", parse_mode=ParseMode.MARKDOWN)
        q.edit_message_text(f"Order #{order.id} marked Rejected.")
    db.close()

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Cancelled.")
    context.user_data.clear()
    return ConversationHandler.END

def register_handlers(dispatcher):
    conv = ConversationHandler(
        entry_points=[CommandHandler('exchange', exchange_start)],
        states={
            SEND_TYPE: [CallbackQueryHandler(send_type_cb, pattern=r'^send\|')],
            RECEIVE_TYPE: [CallbackQueryHandler(recv_cb, pattern=r'^recv\|')],
            SEND_AMOUNT: [MessageHandler(Filters.text & ~Filters.command, got_amount)],
            RECEIVE_ADDRESS: [MessageHandler(Filters.text & ~Filters.command, got_address)],
            OVERVIEW_CONFIRM: [CallbackQueryHandler(overview_confirm_cb, pattern=r'^confirm_')],
            WAIT_FOR_TX: [MessageHandler(Filters.text & ~Filters.command, got_tx)],
            WAIT_FOR_PROOF: [
                MessageHandler(Filters.photo, got_proof_photo),
                CommandHandler('skip', skip_proof),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(conv)
    dispatcher.add_handler(CallbackQueryHandler(admin_action_cb, pattern=r'^admin\|'))
