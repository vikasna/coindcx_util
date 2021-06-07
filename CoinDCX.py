import hmac
import hashlib
import base64
import json
import time
import requests
import secret
import argparse
import math
import re

class CoinDCX:
    def __init__(self):
        self.MAX_COINS_IN_COINDCX = 0
        self.__updated_max_coins = False
        self.__key = secret.API_KEY
        self.__secret = secret.API_SECRET
        self.__secret_bytes = bytes(self.__secret, encoding='utf-8')
        self.marketDetails(argparse.Namespace(silent=True))

    def getAPIData(self,_url,_body=None,_method="post"):
        self.url = _url
        timeStamp = int(round(time.time() * 1000))
        body = {
          "timestamp": timeStamp
        }
        if _body is not None:
            body.update(_body)
        json_body = json.dumps(body, separators = (',', ':'))
        signature = hmac.new(self.__secret_bytes, json_body.encode(), hashlib.sha256).hexdigest()
        headers = {
            'Content-Type': 'application/json',
            'X-AUTH-APIKEY': self.__key,
            'X-AUTH-SIGNATURE': signature
        }
        
        if self.url.endswith("orders/create"):
            print(body)

        try:
            if _method == "get":
                response = requests.get(self.url)
            else:
                response = requests.post(self.url, data = json_body, headers = headers)
        except Exception as e:
            print(f"Exception was riase for url '{self.url}': {str(e)}")
            return None
        if response.status_code != 200:
            self.analyzeError(response)
            return None
        return response.json()

    def analyzeError(self,response):
        errs_from_documentation = {
	    	400: "Bad Request -- Your request is invalid.",
	    	401: "Unauthorized -- Your API key is wrong.",
	    	404: "Not Found -- The specified link could not be found.",
	    	429: "Too Many Requests -- You're making too many API calls",
	    	500: "Internal Server Error -- We had a problem with our server. Try again later.",
	    	503: "Service Unavailable -- We're temporarily offline for maintenance. Please try again later."
        }
        if response.status_code in errs_from_documentation:
            print(f"Error for '{self.url}': {errs_from_documentation[response.status_code]}")
        else:
            print(f"Unknown error for '{self.url}' status code: {response.status_code}")

    def orderBook(self,args):
        _pair = args.pair or "I-BTC_INR"
        _ds = self.getAPIData(_url=f"https://public.coindcx.com/market_data/orderbook?pair={_pair}",_method="get")
        if _ds is None:
            print(f"Could not get the order book for pair: {_pair}")
            return
        _new_ds = {"asks":{},"bids":{}}
        # in each ask and bid, the key is Price and value is Quantity
        for _type in _ds:
            for price in _ds[_type]:
                _new_ds[_type][float(price)] = float(_ds[_type][price])
        print(_new_ds)
        return _new_ds

    def lend(self,args):
        _duration = args.duration or 7
        _currency_short_name = args.currencies or []
        _ignore_small_amounts = not args.not_ignore_small_amounts

        balances = self.getAPIData(_url="https://api.coindcx.com/exchange/v1/users/balances")
        if balances is None:
            print("Could not fetch balances, lending aborted!")
            return
        avail_for_lending = []
        for doc in balances:
            if doc["currency"] == "INR":
                continue
            if doc["balance"] != "0.0":
                # avail for lending
                currency = doc["currency"]
                balance = doc["balance"]
                if float(balance) < 0.001 and _ignore_small_amounts:
                    print(f"Not lending '{currency}' as its balance is very small {balance}")
                elif _currency_short_name and currency not in _currency_short_name:
                    print(f"Not lending '{currency}' as it is not requested!")
                else:
                    lend_body = {
                        "currency_short_name": currency,
                        "duration": int(_duration),
                        "amount": float(balance),
                    }
                    print(f"Lending request sent for: {lend_body}")
                    lend_data = self.getAPIData(_url="https://api.coindcx.com/exchange/v1/funding/lend",_body=lend_body)
                    if lend_data is not None:
                        print(f"Lend status:")
                        print(json.dumps(lend_data,indent=2))
                print('-'*80,sep='')
                print('-'*80,sep='')

    def lendStatus(self,args):
        data = self.getAPIData(_url="https://api.coindcx.com/exchange/v1/funding/fetch_orders")
        if data is not None:
            print("Lending that are still active:")
            print(json.dumps(list(filter(lambda x: x["status"] == "open", data)),indent=2))
            print('-'*80,sep='')
            print('-'*80,sep='')

    def marketDetails(self,args):
        silent = args.silent if hasattr(args,'silent') else False
        data = self.getAPIData(_url="https://api.coindcx.com/exchange/v1/markets_details",_method="get")
        if data is None:
            print("Market details API retunred Nothing!")
            return
        _ret = []
        for c in data:
            if c["base_currency_short_name"] == "INR":
                if not self.__updated_max_coins:
                    self.MAX_COINS_IN_COINDCX+=1
                if not silent:
                    print(c)
                tmp = {}
                for k,v in c.items():
                    if isinstance(v,int):
                        tmp[k] = v
                        continue
                    try:
                        v = float(v)
                    except:
                        pass
                    tmp[k] = v
                _ret.append(tmp)
        self.__updated_max_coins = True
        return _ret
    
    def getBalances(self,args):	
        data = self.getAPIData(_url="https://api.coindcx.com/exchange/v1/users/balances")
        total_balance = 0.0
        if data is not None:
            for doc in data:
                if doc["balance"] == "0.0" and doc["locked_balance"] == "0.0":
                    continue
                target_currency = doc["currency"]
                exchange = "I"
                pair = f"{exchange}-{target_currency}_INR"
                ltp_data = self.getAPIData(_url=f"https://public.coindcx.com/market_data/trade_history?pair={pair}&limit=1",_method="get")
                #print(f"{pair} -- {ltp_data}")
                if target_currency == "INR" and ltp_data is not None and len(ltp_data) == 0:
                    ltp_data = [{"p":1}]
                if ltp_data is not None and len(ltp_data) >= 1 and "p" in ltp_data[0]:
                    print(f"{target_currency} in INR: {ltp_data[0]['p']}")
                    doc["in_INR"] = float(ltp_data[0]["p"]) * (float(doc["balance"])+float(doc["locked_balance"]))
                    total_balance += doc["in_INR"]
            print("Non-zero balances:")
            print(json.dumps(list(filter(lambda x: x["balance"] != "0.0" or x["locked_balance"] != "0.0", data)),indent=2))
            print(f"Total balance in INR: {total_balance}")
            print('-'*80,sep='')
            print('-'*80,sep='')

    def getFundsAvail(self):
        currency = "INR"
        bal_data = self.getAPIData(_url="https://api.coindcx.com/exchange/v1/users/balances")
        if bal_data is None:
            print("Balances returned nothing, not proceeding!")
            return
        funds_avail = 0.0
        for doc in bal_data:
            if doc["currency"] == currency:
                # consider only balance for trading as locked balance represent the amount that may be used for trading already eg. open orders
                funds_avail = float(doc["balance"])#+float(doc["locked_balance"])
                break
        return funds_avail

    def getTradeHistory(self,arg,processed=True):
        hist_data = self.getAPIData(_url="https://api.coindcx.com//exchange/v1/orders/trade_history?limit=5000")
        if hist_data is None:
            print("TradeHist returned nothing, not proceeding!")
            return
        my_hist_data = {}
        total_invested = 0.00
        for row in hist_data:
            print(row)
            if row["symbol"] not in my_hist_data:
                my_hist_data[row["symbol"]] = {"amt_spent":0.0}
            if row["side"] == "buy":
                amt_spent = ( float(row["quantity"])*float(row["price"]) ) + float(row["fee_amount"])
                my_hist_data[row["symbol"]]["amt_spent"] += amt_spent
                total_invested += amt_spent
            else:
                amt_got = float(row["quantity"])*float(row["price"])
                #my_hist_data[row["symbol"]]["amt_spent"] -= amt_got
                #total_invested -= amt_spent
                # amt_spent can go negative if huge gains made when selling
        print('-'*40)
        print(total_invested)
        if processed:
            print(my_hist_data)
            return my_hist_data
        print(hist_data)
        return hist_data

    def buyAll(self,args):
        buy_except = args.do_not_buy or []
        funds_avail = self.getFundsAvail()
        if funds_avail is None: 
            print("Could not get funds avail for buying, aborting!")
            return
        print(f"Funds avail for buying: {funds_avail}")

        # get all coins that has INR as its base currency
        market_details = self.marketDetails(argparse.Namespace(silent=True))
        if market_details is None:
            print("Could not get market details for INR coins, aborting!")
            return

        # filter out coins that we dont want to buy
        # and get order_book_price for each pair (using median of all order book price)
        market_details_modded = []
        order_book_price = {}
        print(f"Total number of coins in coinDCX base currency INR: {self.MAX_COINS_IN_COINDCX}")
        print(f"Min amount that can be spent per coin: INR {funds_avail/self.MAX_COINS_IN_COINDCX}")
        for m in market_details:
            if m["pair"] in buy_except:
                continue
            else:
                pair = m["pair"]
                ob_data = self.getAPIData(_url=f"https://public.coindcx.com/market_data/orderbook?pair={pair}",_method="get")
                if ob_data is None:
                    print(f"No orderbook data fetched for {pair}, skipping this coin!")
                    continue
                middle_index = math.trunc(len(list(ob_data["bids"].keys()))/2)
                if len(ob_data["bids"].keys()) == 0:
                    print(f"No bidding data for {pair}, skipping this coin!")
                    continue
                if len(ob_data["bids"].keys()) >= 2:
                    middle_index = 1
                else:
                    middle_index = 0
                order_book_price_for_pair = float(list(ob_data["bids"].keys())[middle_index])
                order_book_price[pair] = order_book_price_for_pair
                market_details_modded.append(m)
        market_details = market_details_modded

        # sort order_book_price based on values in increasing order
        order_book_price = {k: v for k, v in sorted(order_book_price.items(), key=lambda item: item[1])}

        # get number of total coins to buy
        number_of_coins_to_buy = len(market_details)
        print(f"Initial number of coins to buy: {number_of_coins_to_buy}")

        # assign eq weight and get cost to be spent to buy each coin
        # and get the quantity to buy for each coin
        # adjust the number_of_coins_to_buy
        quantity_to_buy = {}
        for m in market_details:
            pair = m["pair"]
            weight = 1.00
            funds_per_coin = (funds_avail/number_of_coins_to_buy) * weight
            """
            As per an update from our internal team the orderbook of ADA/INR tells us that price is allowed up to two decimal places 
            (which is fine for this request) and the quantity is allowed only in integers (no decimal places allowed for quantity) - which is failing for his request leading to the error.
            Request you to pay attention on base_currency_precision (for price) and target_currency_precision (for quantity) for a given market.
            You can get the entire list of currency-pairs (markets) with all these details using https://api.coindcx.com/exchange/v1/markets_details
            """
            # quantity should be 1 decimal precision
            quantity = round(funds_per_coin/order_book_price[pair],m["target_currency_precision"])
            if m["target_currency_precision"] == 0:
                quantity = int(quantity)
            if quantity == 0.0:
                number_of_coins_to_buy = number_of_coins_to_buy - 1
                m["no_buy"] = 1
                print(f"\tTotal Quantity is 0.0 for {pair}, not buying!")
        print(f"Modified number of coins to buy: {number_of_coins_to_buy}")
        print(f"Modified min amount that can be spent per coin: INR {funds_avail/number_of_coins_to_buy}")
        for m in market_details:
            pair = m["pair"]
            if "no_buy" in m:
                del order_book_price[pair]
                continue
            weight = 1.00
            funds_per_coin = (funds_avail/number_of_coins_to_buy) * weight
            # quantity should be 1 decimal precision
            quantity = round(funds_per_coin/order_book_price[pair],m["target_currency_precision"])
            if m["target_currency_precision"] == 0:
                quantity = int(quantity)
            quantity_to_buy[pair] = quantity

        # place orders
        for pair in order_book_price:
            market = pair.replace("I-","").replace("_","")
            quantity = quantity_to_buy[pair]
            body = {
                "side": "buy",
                "order_type": "limit_order",
                "market": market,
                "price_per_unit": order_book_price[pair], #This parameter is only required for a 'limit_order'
                "total_quantity": quantity, #Replace this with the quantity you want
            }
            resp_ds = self.getAPIData(_url=f"https://api.coindcx.com/exchange/v1/orders/create",_body=body)
            #resp_ds = None
            print('-'*80,sep="")
            print("Request:")
            print(body)
            print("Response:")
            print(resp_ds)
            print('-'*80,sep="")

def processCommandline(coin):
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers()

    lend = subparser.add_parser('lend', description="Lend all currencies which have balance > 0.001. Or specify which currencies to lend by passing the short currency names to --currencies option.")
    lend.add_argument('--currencies', nargs='+', help="Optional, list of short currency names to lend")
    lend.add_argument('--duration', help="Duration to lend (days). Default 7 days")
    lend.add_argument('--not-ignore-small-amounts', action='store_true', help="Default is to ignore small amounts < 0.001. Pass this to not ignore small amounts")
    lend.set_defaults(function=coin.lend)

    lend_status = subparser.add_parser('lend-status',description="Show status of active lending currencies")
    lend_status.set_defaults(function=coin.lendStatus)

    balances = subparser.add_parser('balances',description="Show non-zero balances")
    balances.set_defaults(function=coin.getBalances)

    order_book = subparser.add_parser('order-book',description="Show order book for selected pair")
    order_book.add_argument('--pair', help="Pair you want to get the order  book for, eg. I-BTC_INR is the default")
    order_book.set_defaults(function=coin.orderBook)

    inr_coins = subparser.add_parser('market-data',description="Show details of all coins which has INR as base currency")
    inr_coins.set_defaults(function=coin.marketDetails)

    buy = subparser.add_parser('buy',description="Buy all coins which has INR base currency. Exclude some using --do-not-buy option")
    buy.add_argument('--do-not-buy', nargs='+', help="Pairs that you do not want to buy")
    buy.set_defaults(function=coin.buyAll)

    trade_hist = subparser.add_parser('trade_history', description="Get upto a max of 5000 trade history")
    trade_hist.set_defaults(function=coin.getTradeHistory)

    args = parser.parse_args()

    if 'function' not in args:
        print('Please specify a command')
        print('For more help. use --help')
        exit(1)

    args.function(args)
    return args

if __name__ == "__main__":
    coin = CoinDCX()
    processCommandline(coin)

