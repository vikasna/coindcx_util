# coindcx_util
Wrapper on coindcx apis to get some basic operations done

Before using this script, edit the secret.py and add your API key and secret code.

This allows following operations:
    Show status of active lending currencies.
    Show non-zero balances.
    Show order book for selected pair.
    Show details of all coins which has INR as base currency.
    Buy all coins which has INR base currency. Exclude some using --do-not-buy option. This is a naive implementation to buy all supported currencies by equally weighting all.
    Get upto a max of 5000 trade history.

To get help on using above operations, run:
python3 CoinDCX.py --help
