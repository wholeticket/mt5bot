#property copyright "RobustForexEA"
#property version   "6.50"
#property description "NY & London Nasdaq EA — FTMO 1-Step $100k High-Win-Rate Mode (+0.75R Fast Bank, 10m Burst Guard, US Holiday Ban)."

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
input bool            InpTradeWithStructure=false; // off: 5-rule Nasdaq book only
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
input int    InpOrbMaxMorningEntries=1; // 0 keeps two shorts, or three on a large drive
input bool   InpOrbRequireOpenFail=true; // pass account only: skip a short until the open has failed
input int    InpOrbWeekdays=29;          // bits Mon=1 Tue=2 Wed=4 Thu=8 Fri=16 (29 = Mon/Wed/Thu/Fri)
input bool   InpOrbMorningFade=false;    // the original short after a failed open
input bool   InpDayShots=true;           // 10:00 New York fade, 11:00 New York continuation
input double InpDayShotPoints=60.0;      // move from the 09:30 open
input double InpDayShotTarget=155.0;     // points beyond the signal close

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
input bool InpBlockUsHolidays=true; // skip US NYSE/Nasdaq bank holidays

input group "Position Management"
input bool   InpUsePartialTakeProfit=true;
input double InpPartialFraction=0.50;       // bank 50% at +0.75R (+15pt NY / +11.25pt London), keep 50% runner
input double InpPartialRewardRisk=0.75;     // trigger Stage 1 at +0.75R (+15 pts NY / +11.25 pts London)
input bool   InpMoveStopToBreakeven=true;
input double InpBreakevenOffsetR=-0.70;     // Stage 1 stop at -0.70R (locks +$22/+$13 net cash while giving 14pt/10.5pt cushion!)
input double InpProfitLockTriggerR=4.0;     // Stage 2 trigger at +4.0R (+80 pts NY / +60 pts London)
input double InpProfitLockStopR=1.50;       // Stage 2 stop at +1.50R (+30 pts NY / +22.5 pts London)
input int    InpMaxBarsInTrade=0;

input group "Risk Limits"
input double InpRiskPercent=1.10;
input double InpFixedRiskMoney=1100.00;        // FTMO 1-Step $100k Sniper: $1,100 Shot (Full TP +$4,675 < $5k consistency!) / $660 Half-Shot (Full TP +$2,228)
input double InpMinLotRiskCapPercent=0.00;
input double InpMaxPortfolioRiskPercent=6.00;
input int    InpMaxPortfolioPositions=1;
input double InpMaxDailyLossPercent=2.40;      // FTMO 1-Step 3.0% Max Daily Loss ($3,000 hard limit)
input double InpMaxDailyLossMoney=2000.00;     // FTMO 1-Step $100k daily loss lock: max 1 Shot + 1 Half-Shot loss (-$1,760 worst day, $1,240 buffer!)
input double InpEquityFloorMoney=91000.00;     // FTMO $100k static floor buffer ($90,000 base floor)
input double InpEodTrailingLossMoney=9000.00;  // FTMO 1-Step 10% EOD Trailing Max Loss buffer ($1,000 buffer above $10,000 EOD trailing limit)
input double InpDailyProfitLockMoney=600.00;   // 1 Big Win & Done for the Day: once day profit >= $600, stop opening new trades today!
input double InpDailyProfitCapMoney=4750.00;   // FTMO 1-Step 50% Consistency: auto-bank open trade if day profit reaches $4,750 (< $5,000)
input double InpMaxEquityDrawdownPercent=40.00;
input double InpMaxDrawdownMoney=0.00;         // above 0, halt after this dollar drop from the peak
input bool   InpHaltOnDrawdown=false;          // stay stopped after the drawdown limit
input int    InpDrawdownCooldownDays=5;

input group "Costs"
input double InpCommissionPerLotRoundTurn=0.0;
input double InpMinRewardCostMultiple=1.0;

input group "Execution"
input ulong InpMagicNumber=26101201;
input int   InpMaximumSpreadPoints=250; // broker points (250 = 2.50 index points on US100.cash)
input int   InpDeviationPoints=20;

input group "Ride"
input bool   InpRideMoves=false;     // after 11:00 hop is off; empty days use the 11:00 trade
input double InpRideMinMove=12.0;    // points the last half hour already traveled
input double InpRideRiskMoney=400.0; // dollars at risk on a hop; shots keep their own risk

input group "Gold"
input bool   InpGoldMoves=false;         // gold scalping disabled after 2026 study
input string InpGoldSymbol="XAUUSD";     // FTMO gold spot
input double InpGoldMinMove=1.20;        // dollars in the last 3 minutes
input double InpGoldRiskMoney=250.0;     // dollars at risk; Nasdaq shots keep their own risk
input int    InpGoldMaxPerDay=2;
input int    InpGoldMaxSpreadPoints=60;  // 60 points is 0.60 on gold

CIctStrategy        g_strategy;
COpeningRange       g_orb;
CRiskManager        g_risk;
CRobustTradeManager g_trades;
datetime            g_last_bar_time=0;
datetime            g_gold_bar=0;
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
   if(InpGoldMoves &&
      (InpGoldMinMove<=0.0 || InpGoldRiskMoney<=0.0 || InpGoldMaxPerDay<1 ||
       InpGoldMaxSpreadPoints<0 || StringLen(InpGoldSymbol)==0))
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
bool RideEnabled(void);
void ReplayOpeningRange(void);
bool IsShotWeekday(const MqlDateTime &eastern);

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
   orb.fade10_weekdays=8;      // Thursday only for 10:00 fade
   orb.daily_on=true;
   orb.daily_weekdays=7;       // Mon/Tue/Wed only for 11:00 moderate fade
   orb.daily_minute=11*60;
   orb.daily_dir=-1;           // fade 10..60 pt range mornings at 11:00
   orb.daily_min_move=10.0;
   orb.daily_max_move=60.0;
   orb.daily_stop=20.0;
   orb.daily_target=120.0;
   orb.pm_drive_on=true;       // 14:30 continuation off 13:00 open (Wed/Thu/Fri)
   orb.pm_drive_weekdays=28;
   orb.pm_drive_move=80.0;
   orb.pm_drive_stop=20.0;
   orb.pm_drive_target=100.0;
   orb.london_on=true;         // 03:30 NY (08:30 UK) London Open range-fade (5..30 pts)
   orb.london_min_move=5.0;
   orb.london_max_move=30.0;
   orb.london_stop=15.0;
   orb.london_target=90.0;
   orb.skip_us_holidays=InpBlockUsHolidays;
   orb.london_max_burst10=22.0; // skip London fade if last 10m spiked > 22 pts
   orb.fade10_max_burst10=65.0; // skip Thu 10am fade if last 10m spiked > 65 pts
   orb.shot11_max_burst10=55.0; // skip 11am trend shot if last 10m already exhausted > 55 pts
   orb.pm_max_burst10=50.0;     // skip 14:30 PM drive if last 10m already dumped/spiked > 50 pts
   if((bool)MQLInfoInteger(MQL_TESTER))
     {
      // 10:00 fade on Thursday (8); 11:00 trend shot on Mon/Wed/Thu/Fri (29).
      orb.weekdays=29;
      orb.morning_fade=false;
      orb.day_shots=true;
      orb.fixed_stop=20.0;
      orb.day_target=155.0;
      orb.daily_on=true;
      g_tester_risk_money=1100.0;
      g_tester_target=orb.day_target;
     }
   else
     {
      orb.weekdays=(InpOrbWeekdays==25 ? 29 : InpOrbWeekdays);
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
   PrintFormat("EA|event=book|mode=FTMO_1STEP_100K_SNIPER_V650|london=1|lon_stop=15|lon_target=90|daily=%d|daily_days=%d|daily_stop=%.0f|daily_target=%.0f|daily_risk=660|shots=%d|weekdays=%d|fade10=%d|stop=%.0f|target=%.0f|risk=1100|pm1430=1|partial=0.50|trig=0.75R|cushion=-0.70|lock4R=1.5R|us_holiday_ban=%d|daily_loss_lock=2000|daily_win_lock=600|eod_trail_lock=9000|consistency_cap=4750",
               (int)orb.daily_on,orb.daily_weekdays,orb.daily_stop,orb.daily_target,(int)orb.day_shots,orb.weekdays,
               orb.fade10_weekdays,orb.fixed_stop,orb.day_target,(int)orb.skip_us_holidays);
   PrintFormat("EA|event=structure|enabled=%d|continuation=%d|inverse=%d",
               (int)InpTradeWithStructure,(int)InpAllowContinuation,(int)InpAllowInverse);
   ReplayOpeningRange();
   PrintFormat("EA|event=ride|enabled=%d|min_move=%.0f|risk=%.0f",
               (int)RideEnabled(),InpRideMinMove,InpRideRiskMoney);
   if(InpGoldMoves && !(bool)MQLInfoInteger(MQL_TESTER))
      SymbolSelect(InpGoldSymbol,true);
   PrintFormat("EA|event=gold|enabled=%d|symbol=%s|min_move=%.2f|risk=%.0f|max=%d|intact=1",
               (int)(InpGoldMoves && !(bool)MQLInfoInteger(MQL_TESTER)),InpGoldSymbol,InpGoldMinMove,InpGoldRiskMoney,InpGoldMaxPerDay);
   return INIT_SUCCEEDED;
  }

// A restart forgets the 09:30 open. Walk today's closed bars so the
// 11:00 shot still knows that open, and so a shot already checked is
// not taken a second time.
void ReplayOpeningRange(void)
  {
   g_orb.SetReplay(true);
   MqlRates bars[];
   ArraySetAsSeries(bars,false);
   int copied=CopyRates(_Symbol,PERIOD_M5,1,200,bars);
   if(copied<=0)
     {
      g_orb.SetReplay(false);
      return;
     }
   bool newest_first=(copied>1 && bars[0].time>bars[copied-1].time);
   int opens=0;
   for(int n=0;n<copied;n++)
     {
      int i=(newest_first ? copied-1-n : n);
      MqlDateTime eastern;
      IctGmtToEastern(IctServerToGmt(bars[i].time),eastern);
      if(eastern.hour==9 && eastern.min==30)
         opens++;
      OrbSignal orb;
      g_orb.Evaluate(bars[i],eastern,orb);
     }
   g_orb.SetReplay(false);
   MqlDateTime now_eastern;
   IctGmtToEastern(TimeGMT(),now_eastern);
   int today=now_eastern.year*10000+now_eastern.mon*100+now_eastern.day;
   if(GlobalVariableCheck("mt5bot.nasdaq.day") && (int)GlobalVariableGet("mt5bot.nasdaq.day")==today)
      g_orb.MarkDailyDone();
   double open_price=0.0;
   bool seen=false,fade_done=false,with_done=false,daily_done=false;
   g_orb.ShotState(open_price,seen,fade_done,with_done,daily_done);
   PrintFormat("EA|event=replay|bars=%d|order=%s|opens=%d|shot_open=%.2f|seen=%d|fade10=%d|with11=%d|daily=%d|early=1",
               copied,(newest_first ? "new_first" : "old_first"),opens,
               open_price,(int)seen,(int)fade_done,(int)with_done,(int)daily_done);
  }

// Both hops on the new account stopped out. Empty days stay with the
// one 11:00 trade. The 60-point shot is unchanged.
bool RideEnabled(void)
  {
   return false;
  }

int RideDayKey(const MqlDateTime &eastern)
  {
   return eastern.year*10000+eastern.mon*100+eastern.day;
  }

int RideCount(const MqlDateTime &eastern)
  {
   if(!GlobalVariableCheck("mt5bot.ride.day"))
      return 0;
   if((int)GlobalVariableGet("mt5bot.ride.day")!=RideDayKey(eastern))
      return 0;
   return (int)GlobalVariableGet("mt5bot.ride.count");
  }

void MarkRide(const MqlDateTime &eastern)
  {
   int count=RideCount(eastern)+1;
   GlobalVariableSet("mt5bot.ride.day",RideDayKey(eastern));
   GlobalVariableSet("mt5bot.ride.count",count);
  }

// The 11:00 bar belongs to the shots. A hop can use a later bar, and
// only while the New York window is still open.
bool RideMayEnter(const MqlDateTime &eastern)
  {
   if(!InpRideMoves || InpRideMinMove<=0.0)
      return false;
   if(eastern.day_of_week<1 || eastern.day_of_week>5)
      return false;
   if(eastern.hour*60+eastern.min<=11*60)
      return false;
   if(RideCount(eastern)>=2)
      return false;
   string session="";
   return InTradeWindow(eastern,session);
  }

// Last six closed M5 bars. The move has to already be there, and it
// cannot have given back half of that push. The target is a slice of
// the move, not the 155-point shot.
bool TryRide(const MqlDateTime &eastern)
  {
   MqlRates rates[];
   ArraySetAsSeries(rates,true);
   if(CopyRates(_Symbol,PERIOD_M5,1,6,rates)!=6)
      return false;

   double net=rates[0].close-rates[5].open;
   if(MathAbs(net)<InpRideMinMove)
      return false;

   bool buy=(net>0.0);
   double pullback=0.0;
   if(buy)
     {
      double extreme=rates[0].high;
      for(int i=1;i<6;i++)
         extreme=MathMax(extreme,rates[i].high);
      pullback=extreme-rates[0].close;
     }
   else
     {
      double extreme=rates[0].low;
      for(int i=1;i<6;i++)
         extreme=MathMin(extreme,rates[i].low);
      pullback=rates[0].close-extreme;
     }
   if(pullback>MathAbs(net)*0.5)
      return false;

   double bite=MathAbs(net)*0.40;
   if(bite<8.0)
      bite=8.0;
   if(bite>25.0)
      bite=25.0;
   double stop_distance=pullback+2.0;
   if(stop_distance<8.0)
      stop_distance=8.0;
   if(stop_distance>20.0)
      stop_distance=20.0;
   if(bite<stop_distance*InpMinRewardRisk)
      return false;

   ENUM_ICT_SIGNAL signal=(buy ? ICT_SIGNAL_BUY : ICT_SIGNAL_SELL);
   double target=rates[0].close+(buy ? bite : -bite);
   g_signal_risk=(InpRideRiskMoney>0.0 ? InpRideRiskMoney : 400.0);
   bool sent=SubmitSignal(signal,0.0,stop_distance,target,"ride","ORB ride");
   g_signal_risk=0.0;
   if(sent)
     {
      MarkRide(eastern);
      PrintFormat("EA|event=ride|side=%s|move=%.1f|bite=%.1f|stop=%.1f",
                  (buy ? "buy" : "sell"),net,bite,stop_distance);
     }
   return sent;
  }

int GoldDayKey(const MqlDateTime &eastern)
  {
   return eastern.year*10000+eastern.mon*100+eastern.day;
  }

int GoldCount(const MqlDateTime &eastern)
  {
   if(!GlobalVariableCheck("mt5bot.gold.day"))
      return 0;
   if((int)GlobalVariableGet("mt5bot.gold.day")!=GoldDayKey(eastern))
      return 0;
   return (int)GlobalVariableGet("mt5bot.gold.count");
  }

void MarkGold(const MqlDateTime &eastern)
  {
   int count=GoldCount(eastern)+1;
   GlobalVariableSet("mt5bot.gold.day",GoldDayKey(eastern));
   GlobalVariableSet("mt5bot.gold.count",count);
  }

// Shot days need the account free from 09:50 through the 11:00 bar.
// Other weekdays still have the one 11:00 Nasdaq trade, so gold
// steps aside from 10:50 until that bar has closed.
bool GoldBlockedForShots(const MqlDateTime &eastern)
  {
   int minute=eastern.hour*60+eastern.min;
   if(minute>11*60)
      return false;
   if(IsShotWeekday(eastern))
      return minute>=9*60+50;
   return minute>=10*60+50;
  }

bool GoldWindowOpen(const MqlDateTime &eastern)
  {
   int minute=eastern.hour*60+eastern.min;
   return minute>=3*60 && minute<16*60;
  }

void ManageGold(void)
  {
   if(!InpGoldMoves || StringLen(InpGoldSymbol)==0)
      return;
   if(!g_trades.HasManagedPosition(InpGoldSymbol))
      return;
   g_trades.Manage(InpGoldSymbol,
                   ((bool)MQLInfoInteger(MQL_TESTER) ? false : InpUsePartialTakeProfit),
                   InpPartialFraction,InpPartialRewardRisk,InpMoveStopToBreakeven);
  }

void FlatGold(const MqlDateTime &eastern)
  {
   if(!InpGoldMoves || !g_trades.HasManagedPosition(InpGoldSymbol))
      return;
   int minute=eastern.hour*60+eastern.min;
   if(minute<16*60 && !GoldBlockedForShots(eastern))
      return;

   ulong ticket=0;
   ENUM_POSITION_TYPE type=POSITION_TYPE_BUY;
   datetime open_time=0;
   if(!g_trades.ManagedPosition(InpGoldSymbol,ticket,type,open_time))
      return;
   if(!PositionSelectByTicket(ticket))
      return;
   if(StringFind(PositionGetString(POSITION_COMMENT),"Gold hop")<0)
      return;
   g_trades.CloseManaged(InpGoldSymbol,(minute>=16*60 ? "session_flat" : "shot_wait"));
  }

bool SubmitGold(const ENUM_ICT_SIGNAL signal,const double stop_distance,const double target_price)
  {
   double entry=0.0;
   double stop=0.0;
   double target=0.0;
   if(!g_trades.BuildIctLevels(InpGoldSymbol,signal,0.0,stop_distance,target_price,
                               InpMinRewardRisk,entry,stop,target))
      return false;

   g_signal_risk=InpGoldRiskMoney;
   double risk_percent=0.0;
   bool risk_ok=EntryRiskPercent(risk_percent);
   g_signal_risk=0.0;
   if(!risk_ok)
     {
      PrintFormat("RISK|event=entry_blocked|symbol=%s|reason=equity_floor|equity=%.2f|floor=%.2f",
                  InpGoldSymbol,AccountInfoDouble(ACCOUNT_EQUITY),InpEquityFloorMoney);
      return false;
     }

   ENUM_ORDER_TYPE order_type=(signal==ICT_SIGNAL_BUY ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   double volume=g_risk.CalculateVolume(InpGoldSymbol,order_type,entry,stop,risk_percent,
                                        InpMinLotRiskCapPercent);
   double planned_risk=g_risk.RiskPercentForVolume(InpGoldSymbol,order_type,entry,stop,volume);
   if(planned_risk<=0.0)
      planned_risk=risk_percent;

   string risk_reason="";
   if(!g_risk.CanOpen(InpMagicNumber,InpMaxPortfolioPositions,planned_risk,
                      InpMaxPortfolioRiskPercent,InpMaxDailyLossPercent,
                      InpMaxEquityDrawdownPercent,InpDrawdownCooldownDays,risk_reason,
                      InpMaxDailyLossMoney,InpMaxDrawdownMoney,InpHaltOnDrawdown))
     {
      PrintFormat("RISK|event=entry_blocked|symbol=%s|reason=%s|planned_risk=%.2f",
                  InpGoldSymbol,risk_reason,planned_risk);
      return false;
     }

   PrintFormat("SIGNAL|symbol=%s|session=gold|side=%s|stop=%.2f|target=%.2f|volume=%.4f|risk=%.2f",
               InpGoldSymbol,(signal==ICT_SIGNAL_BUY ? "buy" : "sell"),
               stop,target,volume,planned_risk);
   return g_trades.Open(InpGoldSymbol,signal,volume,stop,target,"Gold hop");
  }

// Last three closed minutes of gold. The move has to already be there,
// the newest of those minutes has to still be going the same way, and
// price must not have given back half. A move that has stalled is left
// alone. This only skips weaker entries. Nasdaq still goes first.
bool TryGold(void)
  {
   if((bool)MQLInfoInteger(MQL_TESTER))
      return false;
   if(!InpGoldMoves || InpGoldMinMove<=0.0 || StringLen(InpGoldSymbol)==0)
      return false;
   if(AccountInfoInteger(ACCOUNT_TRADE_ALLOWED)==0)
      return false;

   MqlDateTime eastern;
   IctGmtToEastern(TimeGMT(),eastern);
   if(eastern.day_of_week<1 || eastern.day_of_week>5)
      return false;
   if(!GoldWindowOpen(eastern) || GoldBlockedForShots(eastern))
      return false;
   if(GoldCount(eastern)>=InpGoldMaxPerDay)
     {
      // Say so once a day. This used to be silent, so the viewer could
      // show a ready setup that was never going to be taken. The flag
      // survives a reload, so a restart does not repeat the line.
      int day_key=GoldDayKey(eastern);
      bool logged=(GlobalVariableCheck("mt5bot.gold.caplog") &&
                   (int)GlobalVariableGet("mt5bot.gold.caplog")==day_key);
      if(!logged)
        {
         GlobalVariableSet("mt5bot.gold.caplog",day_key);
         PrintFormat("EA|event=gold|state=daily_cap|count=%d|max=%d",
                     GoldCount(eastern),InpGoldMaxPerDay);
        }
      return false;
     }
   if(g_trades.HasAnyPosition(_Symbol) || g_trades.HasAnyPosition(InpGoldSymbol))
      return false;
   if(!SymbolSelect(InpGoldSymbol,true))
      return false;

   MqlRates rates[];
   ArraySetAsSeries(rates,true);
   if(CopyRates(InpGoldSymbol,PERIOD_M1,1,3,rates)!=3)
      return false;
   if(rates[0].time==g_gold_bar)
      return false;
   g_gold_bar=rates[0].time;

   double net=rates[0].close-rates[2].open;
   if(MathAbs(net)<InpGoldMinMove)
      return false;

   bool buy=(net>0.0);
   double pullback=0.0;
   if(buy)
     {
      double extreme=rates[0].high;
      for(int i=1;i<3;i++)
         extreme=MathMax(extreme,rates[i].high);
      pullback=extreme-rates[0].close;
     }
   else
     {
      double extreme=rates[0].low;
      for(int i=1;i<3;i++)
         extreme=MathMin(extreme,rates[i].low);
      pullback=rates[0].close-extreme;
     }
   if(pullback>MathAbs(net)*0.5)
      return false;

   double last_minute=rates[0].close-rates[0].open;
   if((buy && last_minute<=0.0) || (!buy && last_minute>=0.0))
      return false;

   MqlTick tick;
   double point=SymbolInfoDouble(InpGoldSymbol,SYMBOL_POINT);
   if(!SymbolInfoTick(InpGoldSymbol,tick) || point<=0.0)
      return false;
   double spread_points=(tick.ask-tick.bid)/point;
   if(spread_points>InpGoldMaxSpreadPoints)
     {
      PrintFormat("EA|event=gold|state=spread|points=%.1f|max=%d",
                  spread_points,InpGoldMaxSpreadPoints);
      return false;
     }

   double bite=MathAbs(net)*0.50;
   if(bite<0.90)
      bite=0.90;
   if(bite>2.50)
      bite=2.50;
   double stop_distance=pullback+0.30;
   if(stop_distance<0.80)
      stop_distance=0.80;
   if(stop_distance>1.60)
      stop_distance=1.60;
   if(bite<stop_distance*InpMinRewardRisk)
      return false;
   if(bite<spread_points*point*2.0)
      return false;

   double entry=(buy ? tick.ask : tick.bid);
   double target=entry+(buy ? bite : -bite);
   ENUM_ICT_SIGNAL signal=(buy ? ICT_SIGNAL_BUY : ICT_SIGNAL_SELL);
   bool sent=SubmitGold(signal,stop_distance,target);
   if(sent)
     {
      MarkGold(eastern);
      PrintFormat("EA|event=gold|side=%s|move=%.2f|bite=%.2f|stop=%.2f|spread=%.1f",
                  (buy ? "buy" : "sell"),net,bite,stop_distance,spread_points);
     }
   return sent;
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
   if(RideEnabled())
      structure+="\nafter 11:00, hop on a move already going and take a small bite";
   if(InpGoldMoves)
      structure+="\nGold joins only while the move is still going, and stands aside for the Nasdaq shots";
   if(InpDayShots && !InpOrbMorningFade)
     {
      Comment(BotLabel()+" v6.50 (FTMO 1-Step $100k · 1-Big-Win-a-Day Sniper)\n"+risk+" Shot / $660 Half-Shot (50% @ +0.75R & -0.70R cushion, +4R locks +1.5R)\n"+
              "1-Step Guards: 1 Big Win ($600+) & Done · 3% Daily Loss Lock ($2,000) · 10% EOD Trailing · 50% Consistency ($4,750)\n"+
              "All weekdays 08:30 UK (03:30 NY) fade a 5..30 point London move ($660, stop 15, target 90)\n"+
              StringFormat("Thu 10:00 NY fade a %.0f-point move ($1,100, stop 20, target 155)",InpDayShotPoints)+"\n"+
              StringFormat("Mon/Wed/Thu/Fri 11:00 NY go with a %.0f-point move ($1,100, stop 20, target 155, 10m burst <= 55)",InpDayShotPoints)+"\n"+
              "Mon/Tue/Wed 11:00 NY fade a 10..60 point range move ($660, stop 20, target 120)\n"+
              "Wed/Thu/Fri 14:30 NY go with an 80-point afternoon drive from 13:00 ($660, stop 20, target 100, 10m burst <= 50)\n"+
              "US Market Holidays: Banned (NYSE/Nasdaq holidays skipped)\n"+
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
   if((bool)MQLInfoInteger(MQL_TESTER) || InpDayShots)
      return false;
   if(!InpTradeWithStructure)
      return false;
   if(!InpAllowContinuation && !InpAllowInverse)
      return false;
   if(IsShotWeekday(eastern) && (eastern.hour*60+eastern.min)<=11*60)
      return false;
   return true;
  }

// Returns false when a full stop would reach the static or EOD trailing equity floor.
// The dollar risk is cut so the stop lands on the floor, not through it.
bool EntryRiskPercent(double &percent)
  {
   if(InpFixedRiskMoney<=0.0 && !(bool)MQLInfoInteger(MQL_TESTER))
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
   double money=1100.0;
   if(g_signal_risk>0.0)
      money=g_signal_risk;
   double effective_floor=InpEquityFloorMoney;
   if(InpEodTrailingLossMoney>0.0)
     {
      double eod_floor=g_risk.EodPeakBalance()-InpEodTrailingLossMoney;
      if(eod_floor>effective_floor)
         effective_floor=eod_floor;
     }
   if(effective_floor>0.0)
     {
      double room=equity-effective_floor;
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
   MqlDateTime open_eastern;
   IctGmtToEastern(IctServerToGmt(open_time),open_eastern);
   int open_minutes=open_eastern.hour*60+open_eastern.min;
   if((StringFind(comment,"ORB london")>=0 || open_minutes<9*60) && minutes>=9*60+20)
     {
      g_trades.CloseManaged(_Symbol,"london_flat");
      return true;
     }
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
   bool tester=(bool)MQLInfoInteger(MQL_TESTER);
   if(!g_risk.CanOpen(InpMagicNumber,InpMaxPortfolioPositions,planned_risk,
                      (tester ? 100.0 : InpMaxPortfolioRiskPercent),
                      (tester ? 100.0 : InpMaxDailyLossPercent),
                      (tester ? 100.0 : InpMaxEquityDrawdownPercent),
                      InpDrawdownCooldownDays,risk_reason,
                      2000.0,
                      (tester ? 0.0 : InpMaxDrawdownMoney),
                      (tester ? false : InpHaltOnDrawdown),
                      600.0))
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

void NoteTradeAccess(void)
  {
   static bool warned=false;
   if(AccountInfoInteger(ACCOUNT_TRADE_ALLOWED)==0)
     {
      warned=true;
      Comment(BotLabel()+"\n"+
              "Trading is off\n"+
              "The server is rejecting every order\n"+
              StringFormat("Balance $%.0f",AccountInfoDouble(ACCOUNT_BALANCE))+"\n"+
              "No new trade will be sent");
      return;
     }
   if(warned)
     {
      warned=false;
      ShowBotLabel();
     }
  }

void OnTick(void)
  {
   NoteTradeAccess();
   g_risk.RefreshAnchors();

   if(g_trades.HasManagedPosition(_Symbol))
     {
      // FTMO 1-Step 50% Consistency Guard: if today's total profit (realized + floating)
      // reaches InpDailyProfitCapMoney ($4,750), bank the position immediately so no single
      // day ever exceeds $5,000 (50% of the $10,000 target).
      if(InpDailyProfitCapMoney>0.0)
        {
         double day_start=g_risk.DayStartEquity();
         double equity=AccountInfoDouble(ACCOUNT_EQUITY);
         if(day_start>0.0 && (equity-day_start)>=InpDailyProfitCapMoney)
           {
            g_trades.CloseManaged(_Symbol,"consistency_50pct_cap");
            return;
           }
        }
      g_trades.Manage(_Symbol,
                      true,
                      0.50,0.75,true,
                      -0.70,4.0,1.50);
     }

   MqlDateTime gold_clock;
   IctGmtToEastern(TimeGMT(),gold_clock);
   ManageGold();
   FlatGold(gold_clock);

   if(!IsNewSignalBar())
     {
      TryGold();
      return;
     }

   MqlDateTime eastern;
   bool have_eastern=ClosedBarEastern(eastern);
   MqlRates closed[];
   ArraySetAsSeries(closed,true);
   bool have_closed=(CopyRates(_Symbol,PERIOD_M5,1,1,closed)==1);
   if(have_eastern && have_closed)
      g_orb.RecordBar(closed[0],eastern);

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

   if(!have_eastern || !have_closed)
      return;

   if(InpPlaybook==PLAYBOOK_OPENING_RANGE)
     {
      if(InpBlockOpexDay && !(bool)MQLInfoInteger(MQL_TESTER) && IctIsOpexDay(eastern))
         return;
      string news_reason="";
      if(!(bool)MQLInfoInteger(MQL_TESTER) && CalendarBlocks(TimeGMT(),eastern,news_reason))
         return;

      OrbSignal orb;
      bool shot_sent=false;
      if(g_orb.Evaluate(closed[0],eastern,orb)!=ICT_SIGNAL_NONE)
        {
         string comment=(orb.session=="london" ? "ORB london" :
                        (orb.session=="am" ? "ORB am" :
                        (orb.session=="day" ? "ORB day" :
                        (orb.session=="daily" ? "ORB daily" : "ORB pm"))));
         double base_shot=1100.0;
         g_signal_risk=((orb.session=="daily" || orb.session=="london") ? 660.0 : base_shot);
         shot_sent=SubmitSignal(orb.signal,orb.stop_price,orb.stop_distance,orb.target,orb.session,comment);
         g_signal_risk=0.0;
         if(shot_sent && orb.session=="daily" && eastern.hour*60+eastern.min<11*60)
           {
            int key=eastern.year*10000+eastern.mon*100+eastern.day;
            GlobalVariableSet("mt5bot.nasdaq.day",key);
           }
        }
      else if(orb.reason!="")
         PrintFormat("FILTER|event=no_entry|symbol=%s|session=%s|reason=%s",
                     _Symbol,orb.session,orb.reason);
      if(shot_sent)
         return;
      if(RideEnabled() && RideMayEnter(eastern) && !g_trades.HasAnyPosition(_Symbol))
        {
         if(TryRide(eastern))
            return;
        }
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
