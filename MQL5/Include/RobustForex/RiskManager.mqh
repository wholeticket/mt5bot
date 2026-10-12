#ifndef ROBUST_FOREX_RISK_MANAGER_MQH
#define ROBUST_FOREX_RISK_MANAGER_MQH

class CRiskManager
  {
private:
   string m_prefix;

   long DayKey(void) const
     {
      MqlDateTime parts;
      TimeToStruct(TimeCurrent(),parts);
      return (long)parts.year*10000+(long)parts.mon*100+(long)parts.day;
     }

   // Fixed keys rather than one per calendar date. Date-suffixed keys leaked a
   // global variable every day, and once the terminal limit was reached
   // GlobalVariableGet returned 0 and the daily loss limit silently stopped
   // being enforced.
   string DayStampKey(void) const
     {
      return m_prefix+"_DAYSTAMP";
     }

   string DayEquityKey(void) const
     {
      return m_prefix+"_DAYEQUITY";
     }

   string PeakKey(void) const
     {
      return m_prefix+"_PEAK";
     }

   string LockKey(void) const
     {
      return m_prefix+"_LOCK";
     }

   double LossForPosition(const string symbol,
                          const ENUM_POSITION_TYPE position_type,
                          const double volume,
                          const double stop_price) const
     {
      if(stop_price<=0.0)
         return DBL_MAX;
      MqlTick tick;
      if(!SymbolInfoTick(symbol,tick))
         return DBL_MAX;
      double current_price=(position_type==POSITION_TYPE_BUY ? tick.bid : tick.ask);
      double result=0.0;
      ENUM_ORDER_TYPE order_type=(position_type==POSITION_TYPE_BUY ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
      if(!OrderCalcProfit(order_type,symbol,volume,current_price,stop_price,result))
         return DBL_MAX;
      return MathMax(0.0,-result);
     }

public:
   void Initialize(void)
     {
      m_prefix=StringFormat("RobustForex_%I64d",AccountInfoInteger(ACCOUNT_LOGIN));
      if((bool)MQLInfoInteger(MQL_TESTER))
        {
         double equity=AccountInfoDouble(ACCOUNT_EQUITY);
         GlobalVariableSet(DayStampKey(),(double)DayKey());
         GlobalVariableSet(DayEquityKey(),equity);
         GlobalVariableSet(PeakKey(),equity);
         if(GlobalVariableCheck(LockKey()))
            GlobalVariableDel(LockKey());
        }
      RefreshAnchors();
     }

   void RefreshAnchors(void)
     {
      double equity=AccountInfoDouble(ACCOUNT_EQUITY);

      // Re-anchor only when the calendar day actually changes, so restarting
      // mid-session does not hand the day a fresh loss budget.
      double today=(double)DayKey();
      if(!GlobalVariableCheck(DayStampKey()) ||
         GlobalVariableGet(DayStampKey())!=today ||
         !GlobalVariableCheck(DayEquityKey()))
        {
         GlobalVariableSet(DayStampKey(),today);
         GlobalVariableSet(DayEquityKey(),equity);
        }

      string peak_key=PeakKey();
      if(!GlobalVariableCheck(peak_key))
         GlobalVariableSet(peak_key,equity);
      else if(equity>GlobalVariableGet(peak_key))
         GlobalVariableSet(peak_key,equity);
     }

   double NormalizePrice(const string symbol,const double price) const
     {
      int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
      double tick_size=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
      if(tick_size<=0.0)
         return NormalizeDouble(price,digits);
      return NormalizeDouble(MathRound(price/tick_size)*tick_size,digits);
     }

   double NormalizePriceDown(const string symbol,const double price) const
     {
      int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
      double tick_size=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
      if(tick_size<=0.0)
         return NormalizeDouble(price,digits);
      return NormalizeDouble(MathFloor(price/tick_size+1e-9)*tick_size,digits);
     }

   double NormalizePriceUp(const string symbol,const double price) const
     {
      int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
      double tick_size=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
      if(tick_size<=0.0)
         return NormalizeDouble(price,digits);
      return NormalizeDouble(MathCeil(price/tick_size-1e-9)*tick_size,digits);
     }

   double CalculateVolume(const string symbol,
                          const ENUM_ORDER_TYPE order_type,
                          const double entry_price,
                          const double stop_price,
                          const double risk_percent,
                          const double min_lot_risk_cap_percent) const
     {
      if(risk_percent<=0.0 || entry_price<=0.0 || stop_price<=0.0 ||
         MathAbs(entry_price-stop_price)<SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE))
         return 0.0;

      double one_lot_result=0.0;
      if(!OrderCalcProfit(order_type,symbol,1.0,entry_price,stop_price,one_lot_result))
        {
         PrintFormat("RISK|event=order_calc_failed|symbol=%s|error=%d",symbol,GetLastError());
         return 0.0;
        }

      double loss_per_lot=MathAbs(one_lot_result);
      if(loss_per_lot<=0.0)
         return 0.0;

      double equity=AccountInfoDouble(ACCOUNT_EQUITY);
      double risk_money=equity*risk_percent/100.0;
      double raw_volume=risk_money/loss_per_lot;
      double min_volume=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
      double max_volume=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
      double volume_step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
      if(volume_step<=0.0 || equity<=0.0)
         return 0.0;

      // On a small account at a higher timeframe the ATR stop is often wide
      // enough that the target risk buys less than one minimum lot. Refusing
      // silently is worse than it looks: the only setups that clear the floor
      // are the ones with the tightest stops, so the traded sample ends up
      // biased toward low volatility - the opposite of what the volatility
      // filter selects for. Both outcomes are logged with the arithmetic.
      if(raw_volume<min_volume)
        {
         double min_lot_risk=min_volume*loss_per_lot/equity*100.0;
         if(min_lot_risk_cap_percent<=0.0 || min_lot_risk>min_lot_risk_cap_percent)
           {
            PrintFormat("RISK|event=below_min_lot|symbol=%s|needed=%.4f|min_lot=%.2f|target_risk=%.2f|min_lot_risk=%.2f|cap=%.2f",
                        symbol,raw_volume,min_volume,risk_percent,min_lot_risk,
                        min_lot_risk_cap_percent);
            return 0.0;
           }
         PrintFormat("RISK|event=min_lot_used|symbol=%s|needed=%.4f|min_lot=%.2f|risk=%.2f",
                     symbol,raw_volume,min_volume,min_lot_risk);
         return NormalizeDouble(min_volume,8);
        }

      double volume=MathFloor(raw_volume/volume_step+1e-8)*volume_step;
      volume=MathMin(volume,max_volume);

      double volume_limit=SymbolInfoDouble(symbol,SYMBOL_VOLUME_LIMIT);
      if(volume_limit>0.0)
         volume=MathMin(volume,volume_limit);

      // Re-align after clamping: a broker maximum or aggregate limit that is
      // not itself a multiple of the step would otherwise produce a volume the
      // server rejects as invalid.
      volume=MathFloor(volume/volume_step+1e-8)*volume_step;

      // Rounding down to the volume step can land under the broker minimum
      // when the minimum is not an exact multiple of the step.
      if(volume<min_volume)
         return 0.0;
      return NormalizeDouble(volume,8);
     }

   // The risk a specific volume actually carries. Needed because the minimum-lot
   // override can hand back a size whose risk exceeds the target, and the
   // portfolio limits have to be checked against what will really be traded
   // rather than against the nominal setting.
   double RiskPercentForVolume(const string symbol,
                               const ENUM_ORDER_TYPE order_type,
                               const double entry_price,
                               const double stop_price,
                               const double volume) const
     {
      double equity=AccountInfoDouble(ACCOUNT_EQUITY);
      if(volume<=0.0 || equity<=0.0)
         return 0.0;

      double one_lot_result=0.0;
      if(!OrderCalcProfit(order_type,symbol,1.0,entry_price,stop_price,one_lot_result))
         return 0.0;

      double loss_per_lot=MathAbs(one_lot_result);
      if(loss_per_lot<=0.0)
         return 0.0;
      return volume*loss_per_lot/equity*100.0;
     }

   int CountManagedPositions(const ulong magic) const
     {
      int count=0;
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong ticket=PositionGetTicket(i);
         if(ticket>0 && (ulong)PositionGetInteger(POSITION_MAGIC)==magic)
            count++;
        }
      return count;
     }

   double PortfolioRiskPercent(const ulong magic) const
     {
      double total_loss=0.0;
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong ticket=PositionGetTicket(i);
         if(ticket==0 || (ulong)PositionGetInteger(POSITION_MAGIC)!=magic)
            continue;

         double loss=LossForPosition(PositionGetString(POSITION_SYMBOL),
                                     (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE),
                                     PositionGetDouble(POSITION_VOLUME),
                                     PositionGetDouble(POSITION_SL));
         if(loss==DBL_MAX)
            return DBL_MAX;
         total_loss+=loss;
        }

      double equity=AccountInfoDouble(ACCOUNT_EQUITY);
      return (equity>0.0 ? total_loss/equity*100.0 : DBL_MAX);
     }

   bool CanOpen(const ulong magic,
                const int max_positions,
                const double new_risk_percent,
                const double max_portfolio_risk_percent,
                const double max_daily_loss_percent,
                const double max_drawdown_percent,
                const int drawdown_cooldown_days,
                string &reason,
                const double max_daily_loss_money=0.0,
                const double max_drawdown_money=0.0,
                const bool halt_on_drawdown=false)
     {
      RefreshAnchors();
      double equity=AccountInfoDouble(ACCOUNT_EQUITY);
      double daily_start=GlobalVariableGet(DayEquityKey());
      double peak=GlobalVariableGet(PeakKey());

      if(daily_start>0.0 && (daily_start-equity)/daily_start*100.0>=max_daily_loss_percent)
        {
         reason="daily_loss_lock";
         return false;
        }
      // FTMO's daily loss is a fixed dollar line. Block the trade when
      // today's loss plus this trade's full stop would reach it.
      if(max_daily_loss_money>0.0 && daily_start>0.0)
        {
         double day_loss=daily_start-equity;
         if(day_loss<0.0)
            day_loss=0.0;
         double new_risk_money=equity*new_risk_percent/100.0;
         if(day_loss+new_risk_money>=max_daily_loss_money)
           {
            reason="daily_loss_money_lock";
            return false;
           }
        }

      // A permanent drawdown lock would freeze the account forever, so the
      // lock instead pauses trading and then re-anchors after a cooldown.
      // The lock is released by elapsed time only. Releasing it on recovery
      // instead would let equity oscillating around the limit restart the
      // cooldown clock forever, and an earlier attempt at recovery-based
      // hysteresis let a stale lock fall through and skip the pause entirely.
      double drawdown_percent=(peak>0.0 ? (peak-equity)/peak*100.0 : 0.0);
      double drawdown_money=(peak>0.0 ? peak-equity : 0.0);
      string lock_key=LockKey();
      bool locked=GlobalVariableCheck(lock_key);
      bool money_breach=(max_drawdown_money>0.0 && drawdown_money>=max_drawdown_money);

      if(!locked && (drawdown_percent>=max_drawdown_percent || money_breach))
        {
         GlobalVariableSet(lock_key,(double)TimeCurrent());
         PrintFormat("RISK|event=drawdown_lock_engaged|equity=%.2f|peak=%.2f|drawdown=%.2f|drawdown_money=%.2f",
                     equity,peak,drawdown_percent,drawdown_money);
         reason="equity_drawdown_lock";
         return false;
        }

      if(locked)
        {
         if(halt_on_drawdown)
           {
            reason="equity_drawdown_halt";
            return false;
           }
         datetime locked_at=(datetime)GlobalVariableGet(lock_key);
         long cooldown_seconds=(long)drawdown_cooldown_days*86400;
         if(TimeCurrent()-locked_at<cooldown_seconds)
           {
            reason="equity_drawdown_cooldown";
            return false;
           }

         GlobalVariableSet(PeakKey(),equity);
         GlobalVariableDel(lock_key);
         PrintFormat("RISK|event=drawdown_lock_released|equity=%.2f|drawdown=%.2f",
                     equity,drawdown_percent);
        }

      if(CountManagedPositions(magic)>=max_positions)
        {
         reason="max_positions";
         return false;
        }

      double portfolio_risk=PortfolioRiskPercent(magic);
      if(portfolio_risk==DBL_MAX ||
         portfolio_risk+new_risk_percent>max_portfolio_risk_percent+1e-8)
        {
         reason="portfolio_risk";
         return false;
        }

      reason="";
      return true;
     }
  };

#endif
