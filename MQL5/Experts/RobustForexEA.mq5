#property copyright "RobustForexEA"
#property version   "6.16"
#property description "NY-session Nasdaq EA. Opening-range breaks, with the ICT fair-value-gap model still available."

#include <RobustForex/Strategy.mqh>
#include <RobustForex/OpeningRange.mqh>
#include <RobustForex/RiskManager.mqh>
#include <RobustForex/TradeManager.mqh>

enum ENUM_PLAYBOOK
  {
   PLAYBOOK_ICT            = 0, // ICT fair value gap
   PLAYBOOK_OPENING_RANGE  = 1  // opening range break
  };

input group "Model"
input ENUM_PLAYBOOK   InpPlaybook=PLAYBOOK_OPENING_RANGE;
input bool            InpTradeWithStructure=true; // long or short when structure agrees; shots go first
input bool            InpAllowContinuation=true;
input bool            InpAllowInverse=true;
input ENUM_TIMEFRAMES InpEntryTimeframe=PERIOD_M5;
input ENUM_TIMEFRAMES InpStructureTimeframe=PERIOD_M15;
input ENUM_TIMEFRAMES InpBiasTimeframe=PERIOD_M30;
input int             InpSwingStrength=2;
input int             InpStructureLookback=288;
input int             InpBiasLookback=144;
input int             InpFvgLookbackMinutes=480;
input int             InpMssValidMinutes=90;
input double          InpMinSwingStepPoints=20.0;

input group "Setup Quality"
input double InpMinImbalancePoints=15.0;   // middle candle of the three-candle gap
input double InpMinBodyFraction=0.55;      // gap candle and the entry candle
input double InpMinMssBodyFraction=0.50;   // structure-break candle
input double InpMinBouncePoints=8.0;
input double InpMinRoomPoints=12.0;        // from the entry to the next DOL
input double InpMinRewardRisk=1.0;
input double InpStopPoints=40.0;           // inverse model only; continuation uses the rejection wick
input int    InpChopBars=8;
input double InpMaxAlternation=0.80;

input group "Opening Range"
input int    InpOrbRangeMinutes=30;
input double InpOrbMinRangePoints=12.0;
input double InpOrbMaxRangePoints=80.0;
input double InpOrbRewardRisk=1.5;
input bool   InpOrbRequireDrive=true;
input int    InpOrbStyle=2;             // 0 range break, 1 with the drive, 2 fade the drive
input double InpOrbMinDrivePoints=5.0;
input double InpOrbFixedStopPoints=20.0;
input bool   InpOrbShortsOnly=true;
input bool   InpOrbMorningOnly=true;
input int    InpOrbMaxMorningEntries=0; // 0 keeps two shorts, or three on a large drive
input bool   InpOrbRequireOpenFail=false; // pass account only: skip a short until the open has failed
input int    InpOrbWeekdays=31;          // bits Mon=1 Tue=2 Wed=4 Thu=8 Fri=16, 31 is every day
input bool   InpOrbMorningFade=true;     // the original short after a failed open
input bool   InpDayShots=false;          // 10:00 New York fade, 11:00 New York continuation
input double InpDayShotPoints=60.0;      // move from the 09:30 open
input double InpDayShotTarget=60.0;      // points beyond the signal close

input group "New York Session"
input bool InpTradeNyAm=true;
input int  InpNyAmStartHour=9;
input int  InpNyAmStartMinute=30;
input int  InpNyAmEndHour=11;
input int  InpNyAmEndMinute=30;
input bool InpTradeNyPm=true;
input int  InpNyPmStartHour=13;
input int  InpNyPmStartMinute=0;
input int  InpNyPmEndHour=16;
input int  InpNyPmEndMinute=0;
input bool InpPmOnlyIfNoAmSetup=false;
input bool InpBlockLunch=true;

input group "News and Calendar"
input bool InpBlockHighImpactNews=true;
input int  InpNewsMinutesBefore=10;
input int  InpNewsMinutesAfter=10;
input bool InpBlockFomcDay=true;
input bool InpBlockOpexDay=true;

input group "Position Management"
input bool   InpUsePartialTakeProfit=true;
input double InpPartialFraction=0.50;
input double InpPartialRewardRisk=1.0;
input bool   InpMoveStopToBreakeven=true;
input int    InpMaxBarsInTrade=0;

input group "Risk Limits"
input double InpRiskPercent=0.50;
input double InpFixedRiskMoney=0.00;          // above 0, each trade risks this many dollars
input double InpMinLotRiskCapPercent=0.00;
input double InpMaxPortfolioRiskPercent=1.50;
input int    InpMaxPortfolioPositions=1;
input double InpMaxDailyLossPercent=2.00;
input double InpMaxDailyLossMoney=0.00;       // above 0, block a trade whose stop would reach this daily loss
input double InpEquityFloorMoney=0.00;        // above 0, a full stop is not allowed to reach this equity
input double InpMaxEquityDrawdownPercent=10.00;
input double InpMaxDrawdownMoney=0.00;        // above 0, halt after this dollar drop from the peak
input bool   InpHaltOnDrawdown=false;         // stay stopped after the drawdown limit
input int    InpDrawdownCooldownDays=10;

input group "Costs"
input double InpCommissionPerLotRoundTurn=0.0;
input double InpMinRewardCostMultiple=1.0;

input group "Execution"
input ulong InpMagicNumber=26101201;
input int   InpMaximumSpreadPoints=80; // broker points, not index points
input int   InpDeviationPoints=20;

CIctStrategy        g_strategy;
COpeningRange       g_orb;
CRiskManager        g_risk;
CRobustTradeManager g_trades;
datetime            g_last_bar_time=0;
double              g_tester_target=0.0;
double              g_tester_risk_money=0.0;
double              g_signal_risk=0.0;
datetime            g_calendar_warned=0;

bool InputsAreValid(void)
  {
   if(InpPlaybook==PLAYBOOK_ICT && !InpAllowContinuation && !InpAllowInverse)
      return false;
   if(InpPlaybook==PLAYBOOK_OPENING_RANGE &&
      (InpOrbRangeMinutes<10 || InpOrbRangeMinutes>60 || (InpOrbRangeMinutes%5)!=0 ||
       InpOrbMinRangePoints<=0.0 || InpOrbMaxRangePoints<=InpOrbMinRangePoints ||
       InpOrbRewardRisk<=0.0 ||
       InpOrbStyle<0 || InpOrbStyle>2 ||
       InpOrbMinDrivePoints<=0.0 ||
       InpOrbFixedStopPoints<=0.0 ||
       (InpDayShots && (InpDayShotPoints<=0.0 || InpDayShotTarget<=0.0))))
      return false;
   if(!InpTradeNyAm && !InpTradeNyPm)
      return false;
   if(InpEntryTimeframe==PERIOD_CURRENT ||
      InpStructureTimeframe==PERIOD_CURRENT ||
      InpBiasTimeframe==PERIOD_CURRENT)
      return false;
   if(InpTradeNyAm &&
      (InpNyAmStartHour*60+InpNyAmStartMinute)>=(InpNyAmEndHour*60+InpNyAmEndMinute))
      return false;
   if(InpTradeNyPm &&
      (InpNyPmStartHour*60+InpNyPmStartMinute)>=(InpNyPmEndHour*60+InpNyPmEndMinute))
      return false;

   return (InpSwingStrength>=1 && InpSwingStrength<=5 &&
           InpStructureLookback>=40 &&
           InpBiasLookback>=40 &&
           InpFvgLookbackMinutes>=60 &&
           InpMssValidMinutes>=5 &&
           InpMinSwingStepPoints>=0.0 &&
           InpMinImbalancePoints>0.0 &&
           InpMinBodyFraction>0.0 && InpMinBodyFraction<=1.0 &&
           InpMinMssBodyFraction>0.0 && InpMinMssBodyFraction<=1.0 &&
           InpMinBouncePoints>0.0 &&
           InpMinRoomPoints>0.0 &&
           InpMinRewardRisk>0.0 &&
           InpStopPoints>0.0 &&
           InpChopBars>=4 &&
           InpMaxAlternation>=0.0 && InpMaxAlternation<=1.0 &&
           InpNyAmStartHour>=0 && InpNyAmStartHour<=23 &&
           InpNyAmEndHour>=0 && InpNyAmEndHour<=23 &&
           InpNyPmStartHour>=0 && InpNyPmStartHour<=23 &&
           InpNyPmEndHour>=0 && InpNyPmEndHour<=23 &&
           InpNyAmStartMinute>=0 && InpNyAmStartMinute<=59 &&
           InpNyAmEndMinute>=0 && InpNyAmEndMinute<=59 &&
           InpNyPmStartMinute>=0 && InpNyPmStartMinute<=59 &&
           InpNyPmEndMinute>=0 && InpNyPmEndMinute<=59 &&
           InpNewsMinutesBefore>=0 && InpNewsMinutesAfter>=0 &&
           InpPartialFraction>=0.0 && InpPartialFraction<1.0 &&
           InpPartialRewardRisk>0.0 &&
           InpMaxBarsInTrade>=0 &&
           InpRiskPercent>0.0 &&
           InpFixedRiskMoney>=0.0 &&
           InpRiskPercent<=InpMaxPortfolioRiskPercent &&
           InpMinLotRiskCapPercent>=0.0 &&
           InpMinLotRiskCapPercent<=InpMaxPortfolioRiskPercent &&
           InpMaxPortfolioPositions>=1 &&
           InpMaxDailyLossPercent>0.0 &&
           InpMaxDailyLossMoney>=0.0 &&
           InpEquityFloorMoney>=0.0 &&
           InpOrbWeekdays>=0 && InpOrbWeekdays<=31 &&
           InpMaxEquityDrawdownPercent>0.0 &&
           InpMaxDrawdownMoney>=0.0 &&
           InpOrbMaxMorningEntries>=0 &&
           InpDrawdownCooldownDays>=0 &&
           InpCommissionPerLotRoundTurn>=0.0 &&
           InpMinRewardCostMultiple>=0.0 &&
           InpMaximumSpreadPoints>=0 &&
           InpDeviationPoints>=0);
  }

string AmSetupKey(void)
  {
   return StringFormat("ICT_AM_%I64u",InpMagicNumber);
  }

string SessionTradeKey(void)
  {
   return StringFormat("ICT_ST_%I64u",InpMagicNumber);
  }

int SessionTradeFlags(const MqlDateTime &eastern)
  {
   string key=SessionTradeKey();
   if(!GlobalVariableCheck(key))
      return 0;
   double stored=GlobalVariableGet(key);
   int day=(int)MathFloor(stored/10.0);
   if(day!=IctDayKey(eastern))
      return 0;
   return (int)MathRound(stored-day*10.0);
  }

bool SessionAlreadyTraded(const MqlDateTime &eastern,const string session)
  {
   int flags=SessionTradeFlags(eastern);
   if(session=="am")
      return ((flags&1)!=0);
   if(session=="pm")
      return ((flags&2)!=0);
   return false;
  }

void MarkSessionTraded(const MqlDateTime &eastern,const string session)
  {
   int flags=SessionTradeFlags(eastern);
   if(session=="am")
      flags|=1;
   else if(session=="pm")
      flags|=2;
   GlobalVariableSet(SessionTradeKey(),IctDayKey(eastern)*10.0+flags);
  }

bool AmSetupAlreadyFormed(const MqlDateTime &eastern)
  {
   string key=AmSetupKey();
   if(!GlobalVariableCheck(key))
      return false;
   return ((int)GlobalVariableGet(key)==IctDayKey(eastern));
  }

void MarkAmSetup(const MqlDateTime &eastern)
  {
   GlobalVariableSet(AmSetupKey(),(double)IctDayKey(eastern));
  }

bool IsNewSignalBar(void)
  {
   datetime current_bar=iTime(_Symbol,InpEntryTimeframe,0);
   if(current_bar<=0 || current_bar==g_last_bar_time)
      return false;
   g_last_bar_time=current_bar;
   return true;
  }

bool ClosedBarEastern(MqlDateTime &eastern)
  {
   datetime opened=iTime(_Symbol,InpEntryTimeframe,1);
   if(opened<=0)
      return false;
   IctGmtToEastern(IctServerToGmt(opened),eastern);
   return true;
  }

// session is "am" or "pm" when the closed bar belongs to a trade window.
bool InTradeWindow(const MqlDateTime &eastern,string &session)
  {
   session="";
   if(InpBlockLunch && IctMinutesInside(eastern,11,30,13,0))
      return false;
   if(InpTradeNyAm &&
      IctMinutesInside(eastern,InpNyAmStartHour,InpNyAmStartMinute,
                       InpNyAmEndHour,InpNyAmEndMinute))
     {
      session="am";
      return true;
     }
   if(InpTradeNyPm &&
      IctMinutesInside(eastern,InpNyPmStartHour,InpNyPmStartMinute,
                       InpNyPmEndHour,InpNyPmEndMinute))
     {
      session="pm";
      return true;
     }
   return false;
  }

bool NameContains(const string text,const string needle)
  {
   string lower=text;
   StringToLower(lower);
   return (StringFind(lower,needle)>=0);
  }

bool IsFomcEvent(const string name)
  {
   return (NameContains(name,"fomc") || NameContains(name,"federal funds"));
  }

bool IsSpeakerEvent(const string name)
  {
   return (NameContains(name,"powell") || NameContains(name,"fed chair"));
  }

// Calendar timestamps are read as UTC. The query is padded by two days so a
// server-versus-GMT mismatch in the request window cannot hide today's events.
bool CalendarBlocks(const datetime now_gmt,const MqlDateTime &eastern,string &reason)
  {
   reason="";
   if(!InpBlockHighImpactNews && !InpBlockFomcDay)
      return false;

   MqlCalendarValue values[];
   datetime from=now_gmt-2*86400;
   datetime to=now_gmt+2*86400;
   ResetLastError();
   int count=CalendarValueHistory(values,from,to,"US","USD");
   if(count<0)
     {
      if(g_calendar_warned==0 || now_gmt-g_calendar_warned>86400)
        {
         g_calendar_warned=now_gmt;
         PrintFormat("FILTER|event=calendar_unavailable|error=%d",GetLastError());
        }
      return false;
     }

   for(int i=0; i<count; i++)
     {
      MqlCalendarEvent event;
      if(!CalendarEventById(values[i].event_id,event))
         continue;

      MqlDateTime event_eastern;
      IctGmtToEastern(values[i].time,event_eastern);
      bool same_day=IctSameDay(event_eastern,eastern);
      if(InpBlockFomcDay && same_day && IsFomcEvent(event.name))
        {
         reason="fomc_day";
         return true;
        }

      bool high=(event.importance>=CALENDAR_IMPORTANCE_HIGH || IsSpeakerEvent(event.name));
      if(!InpBlockHighImpactNews || !high || !same_day)
         continue;

      // A release published as a date rather than a clock time blocks the day,
      // because there is no minute to put a ten-minute window around.
      if(event.time_mode!=CALENDAR_TIMEMODE_DATETIME)
        {
         reason="red_folder_day";
         return true;
        }

      long seconds_until=(long)values[i].time-(long)now_gmt;
      if(seconds_until<=(long)InpNewsMinutesBefore*60 &&
         seconds_until>=-(long)InpNewsMinutesAfter*60)
        {
         reason="red_folder";
         return true;
        }
     }
   return false;
  }

bool SpreadIsAcceptable(double &spread_points)
  {
   MqlTick tick;
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   if(!SymbolInfoTick(_Symbol,tick) || point<=0.0)
      return false;
   spread_points=(tick.ask-tick.bid)/point;
   return spread_points<=InpMaximumSpreadPoints;
  }

double CommissionAsPriceDistance(void)
  {
   if(InpCommissionPerLotRoundTurn<=0.0)
      return 0.0;
   double tick_value=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tick_size=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tick_value<=0.0 || tick_size<=0.0)
      return 0.0;
   double value_per_price_unit=tick_value/tick_size;
   if(value_per_price_unit<=0.0)
      return 0.0;
   return InpCommissionPerLotRoundTurn/value_per_price_unit;
  }

bool MoveIsWorthTheCost(const double expected_move,const double spread_points)
  {
   if(InpMinRewardCostMultiple<=0.0)
      return true;
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   double round_trip=spread_points*point+CommissionAsPriceDistance();
   if(round_trip<=0.0)
      return true;
   return expected_move>=InpMinRewardCostMultiple*round_trip;
  }

string ModelName(const ENUM_ICT_MODEL model)
  {
   if(model==ICT_MODEL_CONTINUATION)
      return "continuation";
   if(model==ICT_MODEL_INVERSE)
      return "inverse";
   return "none";
  }

string BotLabel(void);
void ShowBotLabel(void);

int OnInit(void)
  {
   if(!InputsAreValid())
     {
      Print("EA|event=init_failed|reason=invalid_inputs");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(!SymbolSelect(_Symbol,true))
     {
      PrintFormat("EA|event=init_failed|reason=symbol_select|symbol=%s|error=%d",_Symbol,GetLastError());
      return INIT_FAILED;
     }

   g_risk.Initialize();
   g_trades.Initialize(InpMagicNumber,InpDeviationPoints,GetPointer(g_risk));
   if((bool)MQLInfoInteger(MQL_TESTER))
     {
      if(GlobalVariableCheck(AmSetupKey()))
         GlobalVariableDel(AmSetupKey());
      if(GlobalVariableCheck(SessionTradeKey()))
         GlobalVariableDel(SessionTradeKey());
     }

   IctStrategySettings cfg;
   cfg.entry_timeframe=InpEntryTimeframe;
   cfg.structure_timeframe=InpStructureTimeframe;
   cfg.bias_timeframe=InpBiasTimeframe;
   cfg.swing_strength=InpSwingStrength;
   cfg.structure_lookback=InpStructureLookback;
   cfg.bias_lookback=InpBiasLookback;
   cfg.fvg_lookback_minutes=InpFvgLookbackMinutes;
   cfg.mss_valid_minutes=InpMssValidMinutes;
   cfg.min_swing_step=InpMinSwingStepPoints;
   cfg.min_imbalance=InpMinImbalancePoints;
   cfg.min_body_fraction=InpMinBodyFraction;
   cfg.min_mss_body_fraction=InpMinMssBodyFraction;
   cfg.min_bounce=InpMinBouncePoints;
   cfg.min_room=InpMinRoomPoints;
   cfg.min_reward_risk=InpMinRewardRisk;
   cfg.stop_points=InpStopPoints;
   cfg.chop_bars=InpChopBars;
   cfg.max_alternation=InpMaxAlternation;
   cfg.allow_continuation=InpAllowContinuation;
   cfg.allow_inverse=InpAllowInverse;

   if(!g_strategy.Initialize(_Symbol,cfg))
      return INIT_FAILED;

   OrbSettings orb;
   orb.range_minutes=InpOrbRangeMinutes;
   orb.min_range=InpOrbMinRangePoints;
   orb.max_range=InpOrbMaxRangePoints;
   orb.reward_risk=InpOrbRewardRisk;
   orb.require_drive=InpOrbRequireDrive;
   orb.style=InpOrbStyle;
   orb.min_drive=InpOrbMinDrivePoints;
   orb.fixed_stop=InpOrbFixedStopPoints;
   orb.shorts_only=InpOrbShortsOnly;
   orb.morning_only=InpOrbMorningOnly;
   orb.max_morning_entries=InpOrbMaxMorningEntries;
   orb.require_open_fail=InpOrbRequireOpenFail;
   orb.day_move=InpDayShotPoints;
   orb.daily_on=true;
   orb.daily_minute=11*60;
   orb.daily_dir=1;
   orb.daily_min_move=0.0;
   orb.daily_stop=30.0;
   orb.daily_target=120.0;
   if((bool)MQLInfoInteger(MQL_TESTER))
     {
      // Shots stay Monday, Thursday, Friday. The 11:00 trade fills
      // every weekday the shot does not take.
      orb.weekdays=25;
      orb.morning_fade=false;
      orb.day_shots=true;
      orb.fixed_stop=20.0;
      orb.day_target=155.0;
      orb.daily_on=true;
      g_tester_risk_money=0.0;
      g_tester_target=orb.day_target;
     }
   else
     {
      orb.weekdays=InpOrbWeekdays;
      orb.morning_fade=InpOrbMorningFade;
      orb.day_shots=InpDayShots;
      orb.fixed_stop=InpOrbFixedStopPoints;
      orb.day_target=InpDayShotTarget;
      g_tester_target=orb.day_target;
     }
   g_orb.Configure(orb);

   g_last_bar_time=iTime(_Symbol,InpEntryTimeframe,0);
   ShowBotLabel();
   PrintFormat("EA|event=initialized|bot=%s|symbol=%s|entry=%s|structure=%s|bias=%s|magic=%I64u",
               BotLabel(),_Symbol,EnumToString(InpEntryTimeframe),EnumToString(InpStructureTimeframe),
               EnumToString(InpBiasTimeframe),InpMagicNumber);
   PrintFormat("EA|event=book|daily=%d|daily_stop=%.0f|daily_target=%.0f|shots=%d|weekdays=%d|stop=%.0f|target=%.0f|risk=%.0f",
               (int)orb.daily_on,orb.daily_stop,orb.daily_target,(int)orb.day_shots,orb.weekdays,
               orb.fixed_stop,orb.day_target,InpFixedRiskMoney);
   PrintFormat("EA|event=structure|enabled=%d|continuation=%d|inverse=%d",
               (int)InpTradeWithStructure,(int)InpAllowContinuation,(int)InpAllowInverse);
   return INIT_SUCCEEDED;
  }

string BotLabel(void)
  {
   if(InpOrbRequireOpenFail && InpFixedRiskMoney>0.0 && InpOrbMaxMorningEntries==1)
      return "PASS BOT";
   if(!InpOrbRequireOpenFail && InpFixedRiskMoney<=0.0 && InpOrbMaxMorningEntries==0)
      return "PROFIT BOT";
   return "CUSTOM BOT";
  }

void ShowBotLabel(void)
  {
   string risk=(InpFixedRiskMoney>0.0
                ? StringFormat("$%.0f a trade",InpFixedRiskMoney)
                : StringFormat("%.0f%% of the balance",InpRiskPercent));
   string shorts=(InpOrbMaxMorningEntries==1 ? "1 short" :
                  (InpOrbMaxMorningEntries==0 ? "up to 3 shorts"
                                              : StringFormat("%d shorts",InpOrbMaxMorningEntries)));
   string wait=(InpOrbRequireOpenFail ? "waits for the open" : "does not wait for the open");
   string days="every day";
   if(InpOrbWeekdays>0 && InpOrbWeekdays<31)
     {
      string names[5]={"Mon","Tue","Wed","Thu","Fri"};
      days="";
      for(int i=0;i<5;i++)
        {
         if((InpOrbWeekdays&(1<<i))==0)
            continue;
         if(days!="")
            days+=" ";
         days+=names[i];
        }
     }
   string structure="";
   if(InpTradeWithStructure && (InpAllowContinuation || InpAllowInverse))
      structure="\nalso long or short when structure agrees, shots go first";
   if(InpDayShots && !InpOrbMorningFade)
     {
      Comment(BotLabel()+"\n"+risk+"\n"+
              StringFormat("fade a %.0f-point move at 10:00 New York",InpDayShotPoints)+"\n"+
              StringFormat("go with a %.0f-point move at 11:00 New York",InpDayShotPoints)+"\n"+
              "if that shot is not taken, one 11:00 trade, stop 30, target 120, $250\n"+
              "afternoon buy on a 20-point drop, Wed Thu Fri\n"+
              days+structure);
      return;
     }
   Comment(BotLabel()+"\n"+risk+"\n"+shorts+", "+wait+"\n"+days+structure);
  }

// Mon Thu Fri own the morning through the 11:00 bar. A structure
// trade can go long or short only after that decision, and only when
// the fair-value-gap rules already require enough room and reward.
bool IsShotWeekday(const MqlDateTime &eastern)
  {
   int dow=eastern.day_of_week;
   if(dow<1 || dow>5)
      return false;
   if(InpOrbWeekdays<=0 || InpOrbWeekdays>=31)
      return true;
   return ((InpOrbWeekdays&(1<<(dow-1)))!=0);
  }

bool StructureMayEnter(const MqlDateTime &eastern)
  {
   if(!InpTradeWithStructure)
      return false;
   if(!InpAllowContinuation && !InpAllowInverse)
      return false;
   if(IsShotWeekday(eastern) && (eastern.hour*60+eastern.min)<=11*60)
      return false;
   return true;
  }

// Returns false when a full stop would reach the equity floor. The
// dollar risk is cut so the stop lands on the floor, not through it.
bool EntryRiskPercent(double &percent)
  {
   if(InpFixedRiskMoney<=0.0)
     {
      percent=InpRiskPercent;
      return true;
     }
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity<=0.0)
     {
      percent=InpRiskPercent;
      return true;
     }
   double money=InpFixedRiskMoney;
   if(g_signal_risk>0.0)
      money=g_signal_risk;
   else if((bool)MQLInfoInteger(MQL_TESTER) && g_tester_risk_money>0.0)
      money=g_tester_risk_money;
   if(InpEquityFloorMoney>0.0)
     {
      double room=equity-InpEquityFloorMoney;
      if(room<250.0)
         return false;
      if(room<money)
         money=room;
     }
   percent=money/equity*100.0;
   return true;
  }

void OnDeinit(const int reason)
  {
   Comment("");
   g_strategy.Release();
   PrintFormat("EA|event=deinitialized|reason=%d",reason);
  }

bool FlatOpeningRange(void)
  {
   if(InpPlaybook!=PLAYBOOK_OPENING_RANGE || !g_trades.HasManagedPosition(_Symbol))
      return false;

   datetime forming=iTime(_Symbol,PERIOD_M5,0);
   if(forming<=0)
      return false;
   MqlDateTime eastern;
   IctGmtToEastern(IctServerToGmt(forming),eastern);
   int minutes=eastern.hour*60+eastern.min;

   ulong ticket=0;
   ENUM_POSITION_TYPE type=POSITION_TYPE_BUY;
   datetime open_time=0;
   if(!g_trades.ManagedPosition(_Symbol,ticket,type,open_time))
      return false;
   if(!PositionSelectByTicket(ticket))
      return false;

   string comment=PositionGetString(POSITION_COMMENT);
   if(StringFind(comment,"ORB am")>=0 && minutes>=11*60+30)
     {
      g_trades.CloseManaged(_Symbol,"am_flat");
      return true;
     }
   if(minutes>=15*60+55)
     {
      g_trades.CloseManaged(_Symbol,"session_flat");
      return true;
     }
   return false;
  }

bool SubmitSignal(const ENUM_ICT_SIGNAL signal,const double stop_price,const double stop_distance,
                  const double target_price,const string session,const string comment)
  {
   double spread_points=0.0;
   if(!SpreadIsAcceptable(spread_points))
     {
      PrintFormat("FILTER|event=entry_blocked|symbol=%s|reason=spread|points=%.1f",
                  _Symbol,spread_points);
      return false;
     }

   double entry=0.0;
   double stop=0.0;
   double target=0.0;
   if(!g_trades.BuildIctLevels(_Symbol,signal,stop_price,stop_distance,target_price,
                               InpMinRewardRisk,entry,stop,target))
      return false;

   if(!MoveIsWorthTheCost(MathAbs(target-entry),spread_points))
     {
      PrintFormat("FILTER|event=entry_blocked|symbol=%s|reason=cost_too_high|reward=%.8f|spread_points=%.1f",
                  _Symbol,MathAbs(target-entry),spread_points);
      return false;
     }

   double risk_percent=0.0;
   if(!EntryRiskPercent(risk_percent))
     {
      PrintFormat("RISK|event=entry_blocked|symbol=%s|reason=equity_floor|equity=%.2f|floor=%.2f",
                  _Symbol,AccountInfoDouble(ACCOUNT_EQUITY),InpEquityFloorMoney);
      return false;
     }

   ENUM_ORDER_TYPE order_type=(signal==ICT_SIGNAL_BUY ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   double volume=g_risk.CalculateVolume(_Symbol,order_type,entry,stop,risk_percent,
                                        InpMinLotRiskCapPercent);
   double planned_risk=g_risk.RiskPercentForVolume(_Symbol,order_type,entry,stop,volume);
   if(planned_risk<=0.0)
      planned_risk=risk_percent;

   string risk_reason="";
   if(!g_risk.CanOpen(InpMagicNumber,InpMaxPortfolioPositions,planned_risk,
                      InpMaxPortfolioRiskPercent,InpMaxDailyLossPercent,
                      InpMaxEquityDrawdownPercent,InpDrawdownCooldownDays,risk_reason,
                      InpMaxDailyLossMoney,InpMaxDrawdownMoney,InpHaltOnDrawdown))
     {
      PrintFormat("RISK|event=entry_blocked|symbol=%s|reason=%s|planned_risk=%.2f",
                  _Symbol,risk_reason,planned_risk);
      return false;
     }

   PrintFormat("SIGNAL|symbol=%s|session=%s|side=%s|stop=%.2f|target=%.2f|volume=%.4f|risk=%.2f",
               _Symbol,session,(signal==ICT_SIGNAL_BUY ? "buy" : "sell"),
               stop,target,volume,planned_risk);
   return g_trades.Open(_Symbol,signal,volume,stop,target,comment);
  }

void OnTick(void)
  {
   g_risk.RefreshAnchors();

   if(g_trades.HasManagedPosition(_Symbol))
      g_trades.Manage(_Symbol,
                      ((bool)MQLInfoInteger(MQL_TESTER) ? false : InpUsePartialTakeProfit),
                      InpPartialFraction,InpPartialRewardRisk,InpMoveStopToBreakeven);

   if(!IsNewSignalBar())
      return;

   if(FlatOpeningRange())
      return;

   if(InpMaxBarsInTrade>0 && g_trades.HasManagedPosition(_Symbol))
     {
      ulong ticket=0;
      ENUM_POSITION_TYPE type=POSITION_TYPE_BUY;
      datetime open_time=0;
      if(g_trades.ManagedPosition(_Symbol,ticket,type,open_time))
        {
         int period_seconds=PeriodSeconds(InpEntryTimeframe);
         if(period_seconds>0)
           {
            int bars_held=(int)((TimeCurrent()-open_time)/period_seconds);
            if(bars_held>=InpMaxBarsInTrade)
              {
               g_trades.CloseManaged(_Symbol,"time_exit");
               return;
              }
           }
        }
     }

   if(g_trades.HasAnyPosition(_Symbol))
      return;

   MqlDateTime eastern;
   if(!ClosedBarEastern(eastern))
      return;

   if(InpPlaybook==PLAYBOOK_OPENING_RANGE)
     {
      if(InpBlockOpexDay && !(bool)MQLInfoInteger(MQL_TESTER) && IctIsOpexDay(eastern))
         return;
      string news_reason="";
      if(CalendarBlocks(TimeGMT(),eastern,news_reason))
         return;

      MqlRates closed[];
      ArraySetAsSeries(closed,true);
      if(CopyRates(_Symbol,PERIOD_M5,1,1,closed)!=1)
         return;

      OrbSignal orb;
      if(g_orb.Evaluate(closed[0],eastern,orb)!=ICT_SIGNAL_NONE)
        {
         string comment=(orb.session=="am" ? "ORB am" :
                        (orb.session=="day" ? "ORB day" :
                        (orb.session=="daily" ? "ORB daily" : "ORB pm")));
         g_signal_risk=(orb.session=="daily" ? 250.0 : 0.0);
         SubmitSignal(orb.signal,orb.stop_price,orb.stop_distance,orb.target,orb.session,comment);
         g_signal_risk=0.0;
        }
      else if(orb.reason!="")
         PrintFormat("FILTER|event=no_entry|symbol=%s|session=%s|reason=%s",
                     _Symbol,orb.session,orb.reason);
      if(!StructureMayEnter(eastern))
         return;
     }

   string session="";
   if(!InTradeWindow(eastern,session))
      return;

   if(InpBlockOpexDay && !(bool)MQLInfoInteger(MQL_TESTER) && IctIsOpexDay(eastern))
     {
      PrintFormat("FILTER|event=entry_blocked|symbol=%s|reason=opex",_Symbol);
      return;
     }

   string news_reason="";
   if(CalendarBlocks(TimeGMT(),eastern,news_reason))
     {
      PrintFormat("FILTER|event=entry_blocked|symbol=%s|reason=%s",_Symbol,news_reason);
      return;
     }

   if(session=="pm" && InpPmOnlyIfNoAmSetup && AmSetupAlreadyFormed(eastern))
     {
      PrintFormat("FILTER|event=entry_blocked|symbol=%s|reason=am_setup_already_formed",_Symbol);
      return;
     }

   if(SessionAlreadyTraded(eastern,session))
     {
      PrintFormat("FILTER|event=entry_blocked|symbol=%s|reason=session_already_traded|session=%s",
                  _Symbol,session);
      return;
     }

   IctSignalContext ctx;
   ENUM_ICT_SIGNAL signal=g_strategy.Evaluate(ctx);
   if(signal==ICT_SIGNAL_NONE)
     {
      PrintFormat("FILTER|event=no_entry|symbol=%s|session=%s|reason=%s|trend=%d|mss=%d|dol=%.2f",
                  _Symbol,session,ctx.reject_reason,ctx.trend,ctx.mss,ctx.dol);
      return;
     }

   if(session=="am")
      MarkAmSetup(eastern);

   double spread_points=0.0;
   if(!SpreadIsAcceptable(spread_points))
     {
      PrintFormat("FILTER|event=entry_blocked|symbol=%s|reason=spread|points=%.1f",
                  _Symbol,spread_points);
      return;
     }

   double entry=0.0;
   double stop=0.0;
   double target=0.0;
   if(!g_trades.BuildIctLevels(_Symbol,signal,ctx.stop_price,ctx.stop_distance,ctx.target,
                               InpMinRewardRisk,entry,stop,target))
      return;

   if(!MoveIsWorthTheCost(MathAbs(target-entry),spread_points))
     {
      PrintFormat("FILTER|event=entry_blocked|symbol=%s|reason=cost_too_high|reward=%.8f|spread_points=%.1f",
                  _Symbol,MathAbs(target-entry),spread_points);
      return;
     }

   double risk_percent=0.0;
   if(!EntryRiskPercent(risk_percent))
     {
      PrintFormat("RISK|event=entry_blocked|symbol=%s|reason=equity_floor|equity=%.2f|floor=%.2f",
                  _Symbol,AccountInfoDouble(ACCOUNT_EQUITY),InpEquityFloorMoney);
      return;
     }

   ENUM_ORDER_TYPE order_type=(signal==ICT_SIGNAL_BUY ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   double volume=g_risk.CalculateVolume(_Symbol,order_type,entry,stop,risk_percent,
                                        InpMinLotRiskCapPercent);
   double planned_risk=g_risk.RiskPercentForVolume(_Symbol,order_type,entry,stop,volume);
   if(planned_risk<=0.0)
      planned_risk=risk_percent;

   string risk_reason="";
   if(!g_risk.CanOpen(InpMagicNumber,InpMaxPortfolioPositions,planned_risk,
                      InpMaxPortfolioRiskPercent,InpMaxDailyLossPercent,
                      InpMaxEquityDrawdownPercent,InpDrawdownCooldownDays,risk_reason,
                      InpMaxDailyLossMoney,InpMaxDrawdownMoney,InpHaltOnDrawdown))
     {
      PrintFormat("RISK|event=entry_blocked|symbol=%s|reason=%s|planned_risk=%.2f",
                  _Symbol,risk_reason,planned_risk);
      return;
     }

   PrintFormat("SIGNAL|symbol=%s|session=%s|model=%s|side=%s|fvg_low=%.2f|fvg_high=%.2f|dol=%.2f|stop=%.2f|target=%.2f|volume=%.4f|risk=%.2f",
               _Symbol,session,ModelName(ctx.model),
               (signal==ICT_SIGNAL_BUY ? "buy" : "sell"),
               ctx.fvg_low,ctx.fvg_high,ctx.dol,stop,target,volume,planned_risk);
   if(g_trades.Open(_Symbol,signal,volume,stop,target,"ICT "+ModelName(ctx.model)))
      MarkSessionTraded(eastern,session);
  }

double LotsTraded(void)
  {
   if(!HistorySelect(0,TimeCurrent()))
      return 0.0;

   double lots=0.0;
   int total=HistoryDealsTotal();
   for(int i=0;i<total;i++)
     {
      ulong ticket=HistoryDealGetTicket(i);
      if(ticket==0)
         continue;
      if((ulong)HistoryDealGetInteger(ticket,DEAL_MAGIC)!=InpMagicNumber)
         continue;
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket,DEAL_ENTRY)!=DEAL_ENTRY_IN)
         continue;
      lots+=HistoryDealGetDouble(ticket,DEAL_VOLUME);
     }
   return lots;
  }

double OnTester(void)
  {
   double gross=TesterStatistics(STAT_PROFIT);
   double deposit=TesterStatistics(STAT_INITIAL_DEPOSIT);
   double drawdown=TesterStatistics(STAT_EQUITY_DDREL_PERCENT);
   double trades=TesterStatistics(STAT_TRADES);
   double gross_win=TesterStatistics(STAT_GROSS_PROFIT);
   double gross_loss=MathAbs(TesterStatistics(STAT_GROSS_LOSS));

   double lots=LotsTraded();
   double commission=lots*MathMax(InpCommissionPerLotRoundTurn,0.0);
   double profit=gross-commission;
   double profit_factor=(gross_loss+commission>0.0 ? gross_win/(gross_loss+commission) : 0.0);

   PrintFormat("TESTER|event=result|target=%.0f|trades=%.0f|lots=%.2f|gross_profit=%.2f|est_commission=%.2f|net_profit=%.2f|net_profit_factor=%.3f|equity_dd=%.2f",
               g_tester_target,trades,lots,gross,commission,profit,profit_factor,
               TesterStatistics(STAT_EQUITY_DD));

   if(deposit<=0.0 || trades<=0.0 || !MathIsValidNumber(profit_factor))
      return -DBL_MAX;

   profit_factor=MathMin(profit_factor,3.0);
   double return_percent=profit/deposit*100.0;
   double sample_factor=MathMin(1.0,trades/200.0);
   double score=return_percent*profit_factor*sample_factor/
                MathPow(1.0+drawdown/10.0,2.0);

   if(drawdown>InpMaxEquityDrawdownPercent)
      score-=1000.0+(drawdown-InpMaxEquityDrawdownPercent)*100.0;
   if(profit<=0.0 || profit_factor<1.0)
      score-=1000.0;
   if(trades<30.0)
      score-=500.0;
   return score;
  }
