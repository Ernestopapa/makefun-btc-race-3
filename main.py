import sys
import json

class Bot:
    def __init__(self):
        self.closes = []
        self.highs = []
        self.position = None
        self.peak_equity = 1000 * 10**6
        self.entry_close = 0
        self.bars_count = 0
        self.seq = 0

    def run(self):
        for line in sys.stdin:
            data = json.loads(line)
            if data['type'] == 'hello':
                pass
            elif data['type'] == 'batch':
                self.seq = data['seq']
                self.handle_batch(data)
            elif data['type'] == 'done':
                break

    def handle_batch(self, data):
        # Update account and peak equity
        account = data.get('account', {})
        equity = int(account.get('equity_quote_units', 0))
        if equity > self.peak_equity:
            self.peak_equity = equity

        # Find CBBTC bar and current position
        cbbtc_bar = None
        for bar in data.get('bars', []):
            if bar.get('symbol') == 'CBBTC':
                cbbtc_bar = bar
                break
        
        pos = None
        for p in account.get('positions', []):
            if p.get('symbol') == 'CBBTC':
                pos = p
                break
        self.position = pos
        cash = int(account.get('cash_quote_units', 0))

        orders = []
        if cbbtc_bar:
            close = int(cbbtc_bar.get('c', 0))
            high = int(cbbtc_bar.get('h', 0))
            self.closes.append(close)
            self.highs.append(high)

            self.bars_count += 1
            if self.bars_count <= 60:
                print(json.dumps({"type": "reply", "seq": self.seq, "orders": []}), flush=True)
                return

            # Exits (while holding)
            if self.position and int(self.position.get('qty', 0)) > 0:
                qty = int(self.position.get('qty', 0))
                cost = int(self.position.get('cost_quote_units', 0))
                # Take profit: current position value > cost * 1.015: sell ALL.
                pos_value = qty * close * 10**6 // 10**(8 + 5)

                if pos_value > cost * 1.015:
                    orders.append({"side": "sell", "symbol": "CBBTC", "client_id": f"s{self.seq}-1", "qty": str(qty), "max_slippage_bps": 100})
                    self.entry_close = 0
                elif close < 0.99 * self.entry_close:
                    # Stop loss: close falls below 99% of entry_close: sell ALL.
                    orders.append({"side": "sell", "symbol": "CBBTC", "client_id": f"s{self.seq}-1", "qty": str(qty), "max_slippage_bps": 100})
                    self.entry_close = 0
                elif equity < 0.92 * self.peak_equity:
                    # Hard stop: equity falls below 92% of peak equity: sell ALL.
                    orders.append({"side": "sell", "symbol": "CBBTC", "client_id": f"s{self.seq}-1", "qty": str(qty), "max_slippage_bps": 100})
                    self.entry_close = 0
                
                if orders:
                    print(json.dumps({"type": "reply", "seq": self.seq, "orders": orders}), flush=True)
                    return
            
            # Entry (only when flat)
            elif not self.position or int(self.position.get('qty', 0)) == 0:
                # Entry: close < 0.99 * max_highs_60 AND close > close_5_bars_ago
                if close < 0.99 * max(self.highs[-60:]) and close > self.closes[-6]:
                    orders.append({"side": "buy", "symbol": "CBBTC", "client_id": f"b{self.seq}-1", "notional_quote_units": str(cash * 6 // 10), "max_slippage_bps": 100})
                    self.entry_close = close

        print(json.dumps({"type": "reply", "seq": self.seq, "orders": orders}), flush=True)

if __name__ == '__main__':
    bot = Bot()
    bot.run()
