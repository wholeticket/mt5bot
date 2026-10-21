#ifndef ROBUST_FOREX_TRADE_MANAGER_MQH
#define ROBUST_FOREX_TRADE_MANAGER_MQH

#include <Trade/Trade.mqh>
#include <RobustForex/Strategy.mqh>
#include <RobustForex/RiskManager.mqh>

class CRobustTradeManager
  {
private:
   CTrade       m_trade;
   ulong        m_magic;
   int          m_deviation_points;
   CRiskManager *m_risk;
   string       m_partial_prefix;
   string       m_risk_prefix;
   ulong        m_modify_fail_ticket;
   datetime     m_modify_fail_time;
   ulong        m_partial_fail_ticket;
   datetime     m_partial_fail_time;

   bool TradeResultSucceeded(void) const
     {
      uint code=m_trade.ResultRetcode();
      return (code==TRADE_RETCODE_DONE ||
              code==TRADE_RETCODE_DONE_PARTIAL ||
              code==TRADE_RETCODE_PLACED);
     }

   string PartialKey(const ulong ticket) const
     {
      return m_partial_prefix+IntegerToString(ticket);
     }

   string RiskKey(const ulong ticket) const
     {
      return m_risk_prefix+IntegerToString(ticket);
     }

   bool PartialAlreadyTaken(const ulong ticket) const
     {
      return GlobalVariableCheck(PartialKey(ticket));
     }

   void MarkPartialTaken(const ulong ticket) const
     {
      GlobalVariableSet(PartialKey(ticket),1.0);
     }

   void ForgetTicket(const ulong ticket) const
     {
      if(GlobalVariableCheck(PartialKey(ticket)))
         GlobalVariableDel(PartialKey(ticket));
      if(GlobalVariableCheck(RiskKey(ticket)))
         GlobalVariableDel(RiskKey(ticket));
     }

   // A rejected modify or partial close must not be retried on every tick, or
   // one bad request becomes an order flood. Each operation keeps its own slot
   // so a repeatedly rejected partial close cannot starve stop-loss movement,
   // which is the risk-critical operation of the two.
   bool RetryBlocked(const ulong ticket,
                     const ulong fail_ticket,
                     const datetime fail_time) const
     {
      return (ticket==fail_ticket && TimeCurrent()-fail_time<60);
     }

   double MinimumStopDistance(const string symbol) const
     {
      double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
      return (double)MathMax(SymbolInfoInteger(symbol,SYMBOL_TRADE_STOPS_LEVEL),
                             SymbolInfoInteger(symbol,SYMBOL_TRADE_FREEZE_LEVEL))*point;
     }

   bool SelectManaged(const string symbol,const int index,ulong &ticket) const
     {
      ticket=PositionGetTicket(index);
      if(ticket==0)
         return false;
      return (PositionGetString(POSITION_SYMBOL)==symbol &&
              (ulong)PositionGetInteger(POSITION_MAGIC)==m_magic);
     }

   // The stop moves to breakeven after the trim, so the live stop is no
   // longer the original risk. Remember the distance while it is still the
   // one the position was opened with.
   void RememberRisk(const string symbol)
     {
      ulong ticket=0;
      ENUM_POSITION_TYPE type=POSITION_TYPE_BUY;
      datetime open_time=0;
      if(!ManagedPosition(symbol,ticket,type,open_time))
         return;
      double open=PositionGetDouble(POSITION_PRICE_OPEN);
      double stop=PositionGetDouble(POSITION_SL);
      double risk=MathAbs(open-stop);
      if(risk>0.0)
         GlobalVariableSet(RiskKey(ticket),risk);
     }

   double InitialRisk(const ulong ticket,const double open,const double stop)
     {
      if(GlobalVariableCheck(RiskKey(ticket)))
        {
         double stored=GlobalVariableGet(RiskKey(ticket));
         if(stored>0.0)
            return stored;
        }
      double risk=MathAbs(open-stop);
      if(risk>0.0)
         GlobalVariableSet(RiskKey(ticket),risk);
      return risk;
     }

public:
   void Initialize(const ulong magic,const int deviation_points,CRiskManager *risk)
     {
      m_magic=magic;
      m_deviation_points=deviation_points;
      m_risk=risk;
      m_partial_prefix=StringFormat("ICT_PC_%I64u_",magic);
      m_risk_prefix=StringFormat("ICT_RK_%I64u_",magic);
      m_modify_fail_ticket=0;
      m_modify_fail_time=0;
      m_partial_fail_ticket=0;
      m_partial_fail_time=0;
      // Tester tickets restart from low numbers, so leftover keys from an
      // earlier run would suppress the first partial close of the next one.
      if((bool)MQLInfoInteger(MQL_TESTER))
        {
         GlobalVariablesDeleteAll(m_partial_prefix);
         GlobalVariablesDeleteAll(m_risk_prefix);
        }
      m_trade.SetExpertMagicNumber(m_magic);
      m_trade.SetDeviationInPoints(m_deviation_points);
      m_trade.SetAsyncMode(false);
     }

   bool HasAnyPosition(const string symbol) const
     {
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong ticket=PositionGetTicket(i);
         if(ticket>0 && PositionGetString(POSITION_SYMBOL)==symbol)
            return true;
        }
      return false;
     }

   bool HasManagedPosition(const string symbol) const
     {
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong ticket=0;
         if(SelectManaged(symbol,i,ticket))
            return true;
        }
      return false;
     }

   bool ManagedPosition(const string symbol,
                        ulong &ticket,
                        ENUM_POSITION_TYPE &type,
                        datetime &open_time) const
     {
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         if(!SelectManaged(symbol,i,ticket))
            continue;
         type=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
         open_time=(datetime)PositionGetInteger(POSITION_TIME);
         return true;
        }
      return false;
     }

   // Continuation passes the rejection wick as an absolute stop. The inverse
   // model passes a distance instead, because its stop is a fixed number of
   // points from the fill rather than from the signal-bar close. The DOL is
   // always an absolute target. Either level is rejected, not widened, when
   // the fill has already spent the idea or the broker would not accept it.
   bool BuildIctLevels(const string symbol,
                       const ENUM_ICT_SIGNAL signal,
                       const double stop_price,
                       const double stop_distance,
                       const double target_price,
                       const double min_reward_risk,
                       double &entry,
                       double &stop,
                       double &target) const
     {
      MqlTick tick;
      if(!SymbolInfoTick(symbol,tick) || target_price<=0.0 || min_reward_risk<=0.0)
         return false;
      if(stop_price<=0.0 && stop_distance<=0.0)
         return false;

      double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
      double minimum_distance=MinimumStopDistance(symbol);

      if(signal==ICT_SIGNAL_BUY)
        {
         entry=tick.ask;
         stop=(stop_distance>0.0 ? entry-stop_distance : stop_price);
         stop=m_risk.NormalizePriceDown(symbol,stop);
         target=m_risk.NormalizePriceDown(symbol,target_price);
         if(stop<=0.0 || entry-stop<minimum_distance+point || target<=entry+minimum_distance+point)
           {
            PrintFormat("TRADE|event=levels_rejected|symbol=%s|reason=thesis_spent|entry=%.8f|stop=%.8f|target=%.8f",
                        symbol,entry,stop,target);
            return false;
           }
        }
      else if(signal==ICT_SIGNAL_SELL)
        {
         entry=tick.bid;
         stop=(stop_distance>0.0 ? entry+stop_distance : stop_price);
         stop=m_risk.NormalizePriceUp(symbol,stop);
         target=m_risk.NormalizePriceUp(symbol,target_price);
         if(stop<=0.0 || stop-entry<minimum_distance+point || target>=entry-minimum_distance-point)
           {
            PrintFormat("TRADE|event=levels_rejected|symbol=%s|reason=thesis_spent|entry=%.8f|stop=%.8f|target=%.8f",
                        symbol,entry,stop,target);
            return false;
           }
        }
      else
         return false;

      double risk=MathAbs(entry-stop);
      double reward=MathAbs(target-entry);
      if(risk<=0.0 || reward/risk<min_reward_risk)
        {
         PrintFormat("TRADE|event=levels_rejected|symbol=%s|reason=reward_too_small|reward_risk=%.2f|required=%.2f",
                     symbol,(risk>0.0 ? reward/risk : 0.0),min_reward_risk);
         return false;
        }

      entry=m_risk.NormalizePrice(symbol,entry);
      return true;
     }

   bool Open(const string symbol,
             const ENUM_ICT_SIGNAL signal,
             const double volume,
             const double stop,
             const double target,
             const string comment)
     {
      if(volume<=0.0 || HasAnyPosition(symbol))
        {
         PrintFormat("TRADE|event=open_blocked|symbol=%s|reason=%s",
                     symbol,(volume<=0.0 ? "invalid_volume" : "existing_position"));
         return false;
        }
      if(AccountInfoInteger(ACCOUNT_TRADE_ALLOWED)==0)
        {
         PrintFormat("TRADE|event=open_blocked|symbol=%s|reason=trade_disabled|balance=%.2f",
                     symbol,AccountInfoDouble(ACCOUNT_BALANCE));
         return false;
        }

      m_trade.SetTypeFillingBySymbol(symbol);
      bool request_ok=false;
      if(signal==ICT_SIGNAL_BUY)
         request_ok=m_trade.Buy(volume,symbol,0.0,stop,target,comment);
      else if(signal==ICT_SIGNAL_SELL)
         request_ok=m_trade.Sell(volume,symbol,0.0,stop,target,comment);

      if(!request_ok || !TradeResultSucceeded())
        {
         PrintFormat("TRADE|event=open_failed|symbol=%s|retcode=%u|description=%s|error=%d",
                     symbol,m_trade.ResultRetcode(),m_trade.ResultRetcodeDescription(),GetLastError());
         return false;
        }

      RememberRisk(symbol);
      PrintFormat("TRADE|event=opened|symbol=%s|deal=%I64u|volume=%.8f|price=%.8f|sl=%.8f|tp=%.8f",
                  symbol,m_trade.ResultDeal(),volume,m_trade.ResultPrice(),stop,target);
      return true;
     }

   void CloseManaged(const string symbol,const string reason)
     {
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong ticket=0;
         if(!SelectManaged(symbol,i,ticket))
            continue;

         m_trade.SetTypeFillingBySymbol(symbol);
         if(!m_trade.PositionClose(ticket,m_deviation_points) || !TradeResultSucceeded())
            PrintFormat("TRADE|event=close_failed|ticket=%I64u|reason=%s|retcode=%u|description=%s",
                        ticket,reason,m_trade.ResultRetcode(),m_trade.ResultRetcodeDescription());
         else
           {
            ForgetTicket(ticket);
            PrintFormat("TRADE|event=closed|ticket=%I64u|reason=%s|price=%.8f",
                        ticket,reason,m_trade.ResultPrice());
           }
        }
     }

   // Two-stage smart runner management:
   // Stage 1: At +partial_reward_risk * R (e.g. +1.0R), scale out partial_fraction (e.g. 40%)
   //          and move the remaining runner's stop to entry + breakeven_offset_r * R
   //          (e.g. -0.60R, which locks in positive net profit while giving the runner
   //          12 pts NY / 9 pts London breathing room to survive normal entry retests).
   // Stage 2: At +lock_trigger_r * R (e.g. +4.0R), move the runner's stop to
   //          entry + lock_stop_r * R (e.g. +1.50R) to bank a multi-R win if price reverses.
   void Manage(const string symbol,
               const bool partial_enabled,
               const double partial_fraction,
               const double partial_reward_risk,
               const bool move_to_breakeven,
               const double breakeven_offset_r=-0.60,
               const double lock_trigger_r=4.0,
               const double lock_stop_r=1.50)
     {
      MqlTick tick;
      if(!SymbolInfoTick(symbol,tick))
         return;

      double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
      double tick_size=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
      double minimum_distance=MinimumStopDistance(symbol);

      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong ticket=0;
         if(!SelectManaged(symbol,i,ticket))
            continue;

         ENUM_POSITION_TYPE type=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
         double open=PositionGetDouble(POSITION_PRICE_OPEN);
         double current_stop=PositionGetDouble(POSITION_SL);
         double target=PositionGetDouble(POSITION_TP);
         double volume=PositionGetDouble(POSITION_VOLUME);
         double risk=InitialRisk(ticket,open,current_stop);
         if(risk<=0.0 || partial_reward_risk<=0.0)
            continue;

         double advance=(type==POSITION_TYPE_BUY ? tick.bid-open : open-tick.ask);
         bool scale_ready=(advance>=partial_reward_risk*risk);

         if(partial_enabled && partial_fraction>0.0 && scale_ready && !PartialAlreadyTaken(ticket))
            TakePartial(symbol,ticket,volume,partial_fraction);

         if(!move_to_breakeven)
            continue;

         bool stage1_active=(scale_ready || PartialAlreadyTaken(ticket));
         if(!stage1_active)
            continue;

         double desired_r=breakeven_offset_r;
         if(lock_trigger_r>0.0 && advance>=lock_trigger_r*risk)
            desired_r=MathMax(desired_r,lock_stop_r);

         if(type==POSITION_TYPE_BUY)
           {
            double candidate=m_risk.NormalizePriceDown(symbol,open+desired_r*risk);
            candidate=MathMin(candidate,tick.bid-minimum_distance-point);
            if(candidate>current_stop+tick_size/2.0 && candidate<tick.bid)
               ModifyStop(ticket,candidate,target);
           }
         else if(type==POSITION_TYPE_SELL)
           {
            double candidate=m_risk.NormalizePriceUp(symbol,open-desired_r*risk);
            candidate=MathMax(candidate,tick.ask+minimum_distance+point);
            if((current_stop<=0.0 || candidate<current_stop-tick_size/2.0) && candidate>tick.ask)
               ModifyStop(ticket,candidate,target);
           }
        }
     }

private:
   void ModifyStop(const ulong ticket,const double stop,const double target)
     {
      if(RetryBlocked(ticket,m_modify_fail_ticket,m_modify_fail_time))
         return;

      if(!m_trade.PositionModify(ticket,stop,target) || !TradeResultSucceeded())
        {
         m_modify_fail_ticket=ticket;
         m_modify_fail_time=TimeCurrent();
         PrintFormat("TRADE|event=modify_failed|ticket=%I64u|retcode=%u|description=%s",
                     ticket,m_trade.ResultRetcode(),m_trade.ResultRetcodeDescription());
        }
      else
         PrintFormat("TRADE|event=stop_moved|ticket=%I64u|sl=%.8f",ticket,stop);
     }

   void TakePartial(const string symbol,
                    const ulong ticket,
                    const double volume,
                    const double fraction)
     {
      if(RetryBlocked(ticket,m_partial_fail_ticket,m_partial_fail_time))
         return;

      double min_volume=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
      double volume_step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
      if(volume_step<=0.0)
         return;

      double requested=MathFloor(volume*fraction/volume_step+1e-8)*volume_step;
      requested=NormalizeDouble(requested,8);
      if(requested<min_volume || volume-requested<min_volume)
        {
         MarkPartialTaken(ticket);
         PrintFormat("TRADE|event=partial_skipped|ticket=%I64u|reason=volume_too_small|volume=%.8f",
                     ticket,volume);
         return;
        }

      m_trade.SetTypeFillingBySymbol(symbol);
      if(!m_trade.PositionClosePartial(ticket,requested,m_deviation_points) || !TradeResultSucceeded())
        {
         m_partial_fail_ticket=ticket;
         m_partial_fail_time=TimeCurrent();
         PrintFormat("TRADE|event=partial_failed|ticket=%I64u|retcode=%u|description=%s",
                     ticket,m_trade.ResultRetcode(),m_trade.ResultRetcodeDescription());
         return;
        }

      MarkPartialTaken(ticket);
      PrintFormat("TRADE|event=partial_closed|ticket=%I64u|volume=%.8f|price=%.8f",
                  ticket,requested,m_trade.ResultPrice());
     }
  };

#endif
