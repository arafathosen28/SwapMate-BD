from decimal import Decimal

def calc_fee_and_receive(send_type, receive_type, send_amount):
    # simple example logic: percentage fee or flat
    # modify to real rates / dynamic pricing later
    fee = 10.0 if send_amount < 1000 else 20.0
    # For currency rate example: assume 1 USD = 100 BDT (dummy)
    if send_type.endswith("BDT") and receive_type.startswith("USDT"):
        rate = 100.0
        receive_amount = (send_amount - fee) / rate
    elif send_type.startswith("USDT") and receive_type.endswith("BDT"):
        rate = 100.0
        receive_amount = (send_amount - fee) * rate
    else:
        receive_amount = max(0, send_amount - fee)
    return fee, round(receive_amount, 6)
