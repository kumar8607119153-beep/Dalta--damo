import os
from pionex_python.restful.Orders import Orders

def run_trading_bot():
    try:
        api_key = os.environ.get("PIONEX_API_KEY")
        api_secret = os.environ.get("PIONEX_SECRET_KEY")
        
        if not api_key or not api_secret:
            print("API Keys are not configured yet. Skipping execution.")
            return

        ordersClient = Orders(api_key, api_secret)
        
        signal = "BUY"  # आपका ट्रेडिंग सिग्नल लॉजिक
        
        if signal == "BUY":
            order_params = {
                'symbol': 'BTC_USDT',
                'side': 'BUY',
                'type': 'MARKET',
                'amount': '10'
            }
            response = ordersClient.new_order(order=order_params)
            print("Order Placed Successfully:", response)
        else:
            print("No Signal")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_trading_bot()
              
