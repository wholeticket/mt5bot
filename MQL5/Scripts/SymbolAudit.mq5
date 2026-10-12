#property copyright "RobustForexEA"
#property version   "1.00"
#property script_show_inputs
#property description "Audits broker symbol specs and volatility-to-cost ratios."

// Every preset written so far assumed EURUSD-like specs. Crypto and metals
// differ in contract size, minimum lot, spread and tick value by more than an
// order of magnitude, and those differences decide whether a strategy is
// viable before any signal logic is involved. This script reads the real
// numbers off the broker instead of guessing them.
//
// The output column that matters is cost_per_atr: round-trip cost expressed as
// a fraction of one ATR. A strategy risking about one ATR per trade pays that
// fraction of its risk in costs on every trade, so it is the ceiling on how
// small an edge can survive. EURUSD on M15 sits near 0.35, which is why the
// M15 test lost money regardless of signal quality. Below roughly 0.10 is
// workable; below 0.05 is comfortable.

input double InpCommissionPerLotRoundTurn=5.50; // set 0 for spread-only instruments
input double InpAccountRiskPercent=0.50;
input ENUM_TIMEFRAMES InpTimeframeA=PERIOD_M15;
input ENUM_TIMEFRAMES InpTimeframeB=PERIOD_H1;
input bool   InpOnlyTradableSymbols=true;

// Returns ATR in price terms, or 0.0 when history is not available.
double AverageTrueRange(const string symbol,const ENUM_TIMEFRAMES tf,const int period)
  {
   int handle=iATR(symbol,tf,period);
   if(handle==INVALID_HANDLE)
      return 0.0;

   // A symbol absent from Market Watch has no series loaded yet, and the
   // request above is what triggers the download. Give it time rather than
   // reporting a genuine instrument as dataless.
   double buffer[1];
   for(int attempt=0;attempt<40;attempt++)
     {
      if(BarsCalculated(handle)>period && CopyBuffer(handle,0,1,1,buffer)==1)
        {
         IndicatorRelease(handle);
         return buffer[0];
        }
      Sleep(250);
     }
   IndicatorRelease(handle);
   return 0.0;
  }

// Commission as the price distance needed to earn it back. Independent of
// position size, because a larger trade owes more but earns more per point.
double CommissionAsPriceDistance(const string symbol)
  {
   if(InpCommissionPerLotRoundTurn<=0.0)
      return 0.0;
   double tick_value=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_VALUE);
   double tick_size=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tick_value<=0.0 || tick_size<=0.0)
      return 0.0;
   return InpCommissionPerLotRoundTurn/(tick_value/tick_size);
  }

bool LooksInteresting(const string symbol,const string path)
  {
   string haystack=symbol+"|"+path;
   StringToUpper(haystack);
   string needles[]={"BTC","ETH","LTC","XRP","BCH","SOL","ADA","DOG","DOT","LINK",
                     "AVAX","MATIC","BNB","TRX","CRYPTO","XAU","XAG","XPT","XPD",
                     "GOLD","SILVER","METAL","OIL","WTI","BRENT","US30","NAS","SPX",
                     "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD"};
   for(int i=0;i<ArraySize(needles);i++)
      if(StringFind(haystack,needles[i])>=0)
         return true;
   return false;
  }

void OnStart(void)
  {
   string filename="symbol_audit.csv";
   int file=FileOpen(filename,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(file==INVALID_HANDLE)
     {
      PrintFormat("AUDIT|event=file_open_failed|error=%d",GetLastError());
      return;
     }

   FileWrite(file,"symbol","tradable","digits","point","contract_size",
             "vol_min","vol_step","vol_max","spread_points","spread_price",
             "commission_price","stops_level_pts","tick_value_per_lot",
             "margin_min_lot","price",
             "atr_a","atr_a_pct_price","cost_per_atr_a","risk_lots_a","min_lot_risk_pct_a",
             "atr_b","atr_b_pct_price","cost_per_atr_b","risk_lots_b","min_lot_risk_pct_b",
             "history_from");

   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   double risk_money=equity*InpAccountRiskPercent/100.0;

   int total=SymbolsTotal(false);
   int written=0;
   PrintFormat("AUDIT|event=start|broker_symbols=%d|equity=%.2f|risk_money=%.2f|tf_a=%s|tf_b=%s",
               total,equity,risk_money,EnumToString(InpTimeframeA),EnumToString(InpTimeframeB));

   for(int i=0;i<total;i++)
     {
      string symbol=SymbolName(i,false);
      if(symbol=="")
         continue;
      string path=SymbolInfoString(symbol,SYMBOL_PATH);
      if(!LooksInteresting(symbol,path))
         continue;

      // Selecting into Market Watch is what makes ticks and history reachable.
      if(!SymbolSelect(symbol,true))
         continue;

      ENUM_SYMBOL_TRADE_MODE mode=(ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(symbol,SYMBOL_TRADE_MODE);
      bool tradable=(mode==SYMBOL_TRADE_MODE_FULL);
      if(InpOnlyTradableSymbols && !tradable)
         continue;

      int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
      double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
      double contract=SymbolInfoDouble(symbol,SYMBOL_TRADE_CONTRACT_SIZE);
      double vol_min=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
      double vol_step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
      double vol_max=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
      double tick_value=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_VALUE);
      double tick_size=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
      long stops_level=SymbolInfoInteger(symbol,SYMBOL_TRADE_STOPS_LEVEL);

      MqlTick tick;
      double spread_price=0.0;
      double price=0.0;
      if(SymbolInfoTick(symbol,tick) && tick.bid>0.0)
        {
         spread_price=tick.ask-tick.bid;
         price=tick.bid;
        }
      double spread_points=(point>0.0 ? spread_price/point : 0.0);
      double commission_price=CommissionAsPriceDistance(symbol);
      double cost_price=spread_price+commission_price;

      double margin=0.0;
      if(price>0.0 && !OrderCalcMargin(ORDER_TYPE_BUY,symbol,vol_min,tick.ask,margin))
         margin=0.0;

      // Value of one whole unit of price movement, per lot.
      double value_per_price=(tick_size>0.0 ? tick_value/tick_size : 0.0);

      double atr_a=AverageTrueRange(symbol,InpTimeframeA,14);
      double atr_b=AverageTrueRange(symbol,InpTimeframeB,14);

      double cost_a=(atr_a>0.0 ? cost_price/atr_a : 0.0);
      double cost_b=(atr_b>0.0 ? cost_price/atr_b : 0.0);

      // Lots that put exactly the target risk behind a one-ATR stop, and the
      // risk the broker minimum lot forces if that is smaller than one lot
      // step. The second number is where small accounts get hurt.
      double risk_lots_a=0.0,risk_lots_b=0.0;
      double min_lot_risk_a=0.0,min_lot_risk_b=0.0;
      if(value_per_price>0.0 && equity>0.0)
        {
         if(atr_a>0.0)
           {
            risk_lots_a=risk_money/(atr_a*value_per_price);
            min_lot_risk_a=vol_min*atr_a*value_per_price/equity*100.0;
           }
         if(atr_b>0.0)
           {
            risk_lots_b=risk_money/(atr_b*value_per_price);
            min_lot_risk_b=vol_min*atr_b*value_per_price/equity*100.0;
           }
        }

      datetime history_from=(datetime)SeriesInfoInteger(symbol,InpTimeframeB,SERIES_FIRSTDATE);

      FileWrite(file,symbol,(tradable ? "yes" : "no"),digits,
                DoubleToString(point,8),DoubleToString(contract,2),
                DoubleToString(vol_min,4),DoubleToString(vol_step,4),DoubleToString(vol_max,2),
                DoubleToString(spread_points,1),DoubleToString(spread_price,digits),
                DoubleToString(commission_price,digits),(int)stops_level,
                DoubleToString(tick_value,5),DoubleToString(margin,2),
                DoubleToString(price,digits),
                DoubleToString(atr_a,digits),
                DoubleToString(price>0.0 ? atr_a/price*100.0 : 0.0,4),
                DoubleToString(cost_a,4),
                DoubleToString(risk_lots_a,4),
                DoubleToString(min_lot_risk_a,3),
                DoubleToString(atr_b,digits),
                DoubleToString(price>0.0 ? atr_b/price*100.0 : 0.0,4),
                DoubleToString(cost_b,4),
                DoubleToString(risk_lots_b,4),
                DoubleToString(min_lot_risk_b,3),
                TimeToString(history_from,TIME_DATE));
      written++;

      PrintFormat("AUDIT|symbol=%s|atr_%s=%.*f|cost_per_atr=%.3f|vol_min=%.4f|min_lot_risk=%.2f%%|history_from=%s",
                  symbol,EnumToString(InpTimeframeB),digits,atr_b,cost_b,vol_min,
                  min_lot_risk_b,TimeToString(history_from,TIME_DATE));
     }

   FileClose(file);
   PrintFormat("AUDIT|event=complete|symbols_written=%d|file=MQL5/Files/%s",written,filename);
  }
