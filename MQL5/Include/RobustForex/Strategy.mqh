#ifndef ROBUST_FOREX_STRATEGY_MQH
#define ROBUST_FOREX_STRATEGY_MQH

enum ENUM_ICT_SIGNAL
  {
   ICT_SIGNAL_NONE = 0,
   ICT_SIGNAL_BUY  = 1,
   ICT_SIGNAL_SELL = -1
  };

enum ENUM_ICT_MODEL
  {
   ICT_MODEL_NONE         = 0,
   ICT_MODEL_CONTINUATION = 1, // pullback into an FVG, then a rejection toward the DOL
   ICT_MODEL_INVERSE      = 2  // DOL sweep plus MSS, then a close straight through an FVG
  };

// Distances are price units on the chart. On NAS100 / NQ / MNQ one index point
// is 1.0 in the price, so 40 means forty index points, not forty SYMBOL_POINT
// steps. A broker that quotes the index in a scaled price needs these scaled too.
struct IctStrategySettings
  {
   ENUM_TIMEFRAMES entry_timeframe;
   ENUM_TIMEFRAMES structure_timeframe;
   ENUM_TIMEFRAMES bias_timeframe;
   int             swing_strength;
   int             structure_lookback;
   int             bias_lookback;
   int             fvg_lookback_minutes;
   int             mss_valid_minutes;
   double          min_swing_step;
   double          min_imbalance;
   double          min_body_fraction;
   double          min_mss_body_fraction;
   double          min_bounce;
   double          min_room;
   double          min_reward_risk;
   double          stop_points;
   int             chop_bars;
   double          max_alternation;
   bool            allow_continuation;
   bool            allow_inverse;
  };

struct IctSignalContext
  {
   ENUM_ICT_MODEL model;
   int            trend;
   int            mss;
   double         fvg_low;
   double         fvg_high;
   double         dol;
   double         stop_price;
   double         stop_distance;
   double         target;
   string         reject_reason;
  };

struct IctSwing
  {
   double   price;
   datetime time;
   int      shift;
   bool     is_high;
  };

struct IctLevel
  {
   double   price;
   datetime formed;
   bool     is_high;
  };

struct IctGap
  {
   double   low;
   double   high;
   datetime candle3_time;
   int      direction;
   int      period_seconds;
  };

// Calendar helpers below speak UTC. Bar times coming out of CopyRates are
// broker server time, and the New York session is applied on top of both.

datetime IctCivilToUtc(const int year,const int month,const int day,
                       const int hour,const int minute)
  {
   int y=year;
   int m=month;
   if(m<=2)
      y--;
   // Howard Hinnant's civil-from-days, inverted. Integer division is safe
   // here because every year the terminal will see is positive.
   int era=y/400;
   int yoe=y-era*400;
   int mp=m+(m>2 ? -3 : 9);
   int doy=(153*mp+2)/5+day-1;
   int doe=yoe*365+yoe/4-yoe/100+doy;
   long days=(long)era*146097+(long)doe-719468;
   return (datetime)(days*86400+(long)hour*3600+(long)minute*60);
  }

int IctWeekdaySunday0(const int year,const int month,const int day)
  {
   int y=year;
   if(month<3)
      y--;
   int month_table[12]={0,3,2,5,0,3,5,1,4,6,2,4};
   int value=y+y/4-y/100+y/400+month_table[month-1]+day;
   int dow=value%7;
   if(dow<0)
      dow+=7;
   return dow;
  }

int IctNthWeekday(const int year,const int month,const int weekday,const int n)
  {
   int first=IctWeekdaySunday0(year,month,1);
   int day=1+(weekday-first+7)%7;
   return day+(n-1)*7;
  }

// US Eastern. DST starts the second Sunday of March at 07:00 UTC and ends the
// first Sunday of November at 06:00 UTC.
int IctEasternOffsetSeconds(const datetime gmt)
  {
   MqlDateTime parts;
   TimeToStruct(gmt,parts);
   datetime start=IctCivilToUtc(parts.year,3,IctNthWeekday(parts.year,3,0,2),7,0);
   datetime end=IctCivilToUtc(parts.year,11,IctNthWeekday(parts.year,11,0,1),6,0);
   if(gmt>=start && gmt<end)
      return -4*3600;
   return -5*3600;
  }

datetime IctServerToGmt(const datetime server_time)
  {
   // In MT5 Strategy Tester, TimeGMT() equals TimeCurrent() (raw == 0),
   // which shifted all bar times by 2-3 hours. FTMO server time is always
   // New York + 7 hours (UTC+2 in US winter, UTC+3 in US summer).
   long raw=(long)TimeCurrent()-(long)TimeGMT();
   if((bool)MQLInfoInteger(MQL_TESTER) || MathAbs(raw)<60)
     {
      datetime approx_gmt=(datetime)((long)server_time-2*3600);
      int eastern_off=IctEasternOffsetSeconds(approx_gmt); // -5*3600 winter, -4*3600 summer
      long broker_offset=7*3600+eastern_off;               // +2*3600 winter, +3*3600 summer
      return (datetime)((long)server_time-broker_offset);
     }
   // The raw difference wobbles by a second. A bar that opens at
   // 10:00:00 would otherwise look like 09:59:59 and the shot would miss.
   long hours=(raw>=0 ? (raw+1800)/3600 : (raw-1800)/3600);
   long offset=hours*3600;
   return (datetime)((long)server_time-offset);
  }

void IctGmtToEastern(const datetime gmt,MqlDateTime &eastern)
  {
   datetime shifted=(datetime)((long)gmt+IctEasternOffsetSeconds(gmt));
   TimeToStruct(shifted,eastern);
  }

datetime IctEasternToUtc(const int year,const int month,const int day,
                         const int hour,const int minute)
  {
   datetime as_standard=IctCivilToUtc(year,month,day,hour,minute)+5*3600;
   if(IctEasternOffsetSeconds(as_standard)==-5*3600)
      return as_standard;
   return IctCivilToUtc(year,month,day,hour,minute)+4*3600;
  }

bool IctSameDay(const MqlDateTime &left,const MqlDateTime &right)
  {
   return (left.year==right.year && left.mon==right.mon && left.day==right.day);
  }

int IctDayKey(const MqlDateTime &parts)
  {
   return parts.year*10000+parts.mon*100+parts.day;
  }

// Monthly equity-index options expire on the third Friday.
bool IctIsOpexDay(const MqlDateTime &eastern)
  {
   return (IctWeekdaySunday0(eastern.year,eastern.mon,eastern.day)==5 &&
           eastern.day==IctNthWeekday(eastern.year,eastern.mon,5,3));
  }

// Gregorian Easter Sunday (Meeus/Jones/Butcher) to derive Good Friday.
void IctEasterSunday(const int year,int &easter_month,int &easter_day)
  {
   int a=year%19;
   int b=year/100;
   int c=year%100;
   int d=b/4;
   int e=b%4;
   int f=(b+8)/25;
   int g=(b-f+1)/3;
   int h=(19*a+b-d-g+15)%30;
   int i=c/4;
   int k=c%4;
   int l=(32+2*e+2*i-h-k)%7;
   int m=(a+11*h+22*l)/451;
   easter_month=(h+l-7*m+114)/31;
   easter_day=((h+l-7*m+114)%31)+1;
  }

// US NYSE/Nasdaq market holidays (plus Black Friday & Christmas Eve thin sessions).
bool IctIsUsMarketHoliday(const MqlDateTime &eastern)
  {
   int y=eastern.year;
   int m=eastern.mon;
   int d=eastern.day;
   int dow=IctWeekdaySunday0(y,m,d); // 0=Sun .. 6=Sat

   // 1. New Year's Day (Jan 1, or Mon Jan 2 when Jan 1 is Sunday)
   if(m==1 && (d==1 || (d==2 && dow==1)))
      return true;
   // 2. Martin Luther King Jr. Day (3rd Monday of January)
   if(m==1 && d==IctNthWeekday(y,1,1,3))
      return true;
   // 3. Presidents' Day (3rd Monday of February)
   if(m==2 && d==IctNthWeekday(y,2,1,3))
      return true;
   // 4. Good Friday (2 days before Easter Sunday)
   if(m==3 || m==4)
     {
      int em=0,ed=0;
      IctEasterSunday(y,em,ed);
      datetime gf=IctCivilToUtc(y,em,ed,12,0)-2*86400;
      MqlDateTime gf_parts;
      TimeToStruct(gf,gf_parts);
      if(m==gf_parts.mon && d==gf_parts.day)
         return true;
     }
   // 5. Memorial Day (Last Monday of May)
   if(m==5 && dow==1 && d>=25)
      return true;
   // 6. Juneteenth (Jun 19, Fri Jun 18 if Sat, Mon Jun 20 if Sun)
   if(m==6 && (d==19 || (d==18 && dow==5) || (d==20 && dow==1)))
      return true;
   // 7. Independence Day (Jul 4, Fri Jul 3 if Sat, Mon Jul 5 if Sun)
   if(m==7 && (d==4 || (d==3 && dow==5) || (d==5 && dow==1)))
      return true;
   // 8. Labor Day (1st Monday of September)
   if(m==9 && d==IctNthWeekday(y,9,1,1))
      return true;
   // 9. Thanksgiving (4th Thursday of November) & Black Friday (day after)
   if(m==11)
     {
      int tg=IctNthWeekday(y,11,4,4);
      if(d==tg || d==tg+1)
         return true;
     }
   // 10. Christmas Eve & Christmas Day (Dec 24, Dec 25, or Mon Dec 26 when Dec 25 is Sun)
   if(m==12 && (d==24 || d==25 || (d==26 && dow==1)))
      return true;

   return false;
  }

bool IctMinutesInside(const MqlDateTime &eastern,
                      const int start_hour,const int start_minute,
                      const int end_hour,const int end_minute)
  {
   int now=eastern.hour*60+eastern.min;
   int start=start_hour*60+start_minute;
   int end=end_hour*60+end_minute;
   return (now>=start && now<end);
  }

double IctBodyFraction(const MqlRates &bar)
  {
   double range=bar.high-bar.low;
   if(range<=0.0)
      return 0.0;
   return MathAbs(bar.close-bar.open)/range;
  }

class CIctStrategy
  {
private:
   string              m_symbol;
   IctStrategySettings m_cfg;
   double              m_point;

   bool TryCopy(const ENUM_TIMEFRAMES timeframe,const int count,
                MqlRates &rates[],int &copied) const
     {
      ArraySetAsSeries(rates,true);
      ArrayResize(rates,0);
      ResetLastError();
      copied=CopyRates(m_symbol,timeframe,0,count,rates);
      return (copied>0);
     }

   bool CopySeries(const ENUM_TIMEFRAMES timeframe,const int count,
                   MqlRates &rates[],int &copied) const
     {
      if(TryCopy(timeframe,count,rates,copied))
         return true;
      PrintFormat("STRATEGY|event=copy_failed|symbol=%s|timeframe=%s|error=%d",
                  m_symbol,EnumToString(timeframe),GetLastError());
      return false;
     }

   bool IsChoppy(const MqlRates &rates[],const int copied) const
     {
      int flips=0;
      int pairs=0;
      int limit=MathMin(m_cfg.chop_bars,copied-2);
      for(int i=1; i<limit; i++)
        {
         int newer=(rates[i].close>rates[i].open ? 1 : (rates[i].close<rates[i].open ? -1 : 0));
         int older=(rates[i+1].close>rates[i+1].open ? 1 : (rates[i+1].close<rates[i+1].open ? -1 : 0));
         if(newer==0 || older==0)
            continue;
         pairs++;
         if(newer!=older)
            flips++;
        }
      if(pairs<4)
         return false;
      return ((double)flips/(double)pairs>m_cfg.max_alternation);
     }

   void FindSwings(const MqlRates &rates[],const int copied,IctSwing &swings[]) const
     {
      ArrayResize(swings,0);
      int strength=m_cfg.swing_strength;
      if(copied<strength*2+3)
         return;

      for(int i=strength+1; i<copied-strength; i++)
        {
         bool is_high=true;
         bool is_low=true;
         for(int k=1; k<=strength && (is_high || is_low); k++)
           {
            if(rates[i].high<=rates[i-k].high || rates[i].high<=rates[i+k].high)
               is_high=false;
            if(rates[i].low>=rates[i-k].low || rates[i].low>=rates[i+k].low)
               is_low=false;
           }
         // A bar that is both is a one-bar range, not a swing.
         if(is_high==is_low)
            continue;

         int n=ArraySize(swings);
         ArrayResize(swings,n+1);
         swings[n].price=(is_high ? rates[i].high : rates[i].low);
         swings[n].time=rates[i].time;
         swings[n].shift=i;
         swings[n].is_high=is_high;
        }
     }

   // Keep swings that are at least one step away from the previous kept
   // swing. A tiny pause inside a larger leg is not its own swing.
   int CollectSeparated(const IctSwing &swings[],const datetime not_after,const bool want_high,
                        IctSwing &out[],const int max_out) const
     {
      ArrayResize(out,0);
      for(int i=0; i<ArraySize(swings) && ArraySize(out)<max_out; i++)
        {
         if(not_after>0 && swings[i].time>not_after)
            continue;
         if(swings[i].is_high!=want_high)
            continue;
         int kept=ArraySize(out);
         if(kept>0 && MathAbs(swings[i].price-out[kept-1].price)<m_cfg.min_swing_step)
            continue;
         ArrayResize(out,kept+1);
         out[kept]=swings[i];
        }
      return ArraySize(out);
     }

   bool SeparatedSwing(const IctSwing &swings[],const datetime not_after,const bool want_high,
                       IctSwing &recent,IctSwing &prior) const
     {
      IctSwing chain[];
      if(CollectSeparated(swings,not_after,want_high,chain,2)<2)
         return false;
      recent=chain[0];
      prior=chain[1];
      return true;
     }

   // A continuation entry is the pullback, so the newest high is often lower
   // while the prior staircase is still intact. That staircase stays the trend
   // until a later swing steps through it.
   int TrendAt(const IctSwing &swings[],const datetime not_after) const
     {
      IctSwing highs[];
      IctSwing lows[];
      int high_count=CollectSeparated(swings,not_after,true,highs,3);
      int low_count=CollectSeparated(swings,not_after,false,lows,3);
      if(high_count<2 || low_count<2)
         return 0;

      double step=m_cfg.min_swing_step;
      bool highs_up=highs[0].price>highs[1].price;
      bool lows_up=lows[0].price>lows[1].price;
      bool highs_down=highs[0].price<highs[1].price;
      bool lows_down=lows[0].price<lows[1].price;
      bool displaced_up=(highs[0].price-highs[1].price>=step || lows[0].price-lows[1].price>=step);
      bool displaced_down=(highs[1].price-highs[0].price>=step || lows[1].price-lows[0].price>=step);
      if(highs_up && lows_up && displaced_up)
         return 1;
      if(highs_down && lows_down && displaced_down)
         return -1;

      if(high_count>=3 && low_count>=3 &&
         highs[1].price>highs[2].price+step &&
         lows[1].price>lows[2].price+step &&
         lows[0].price>lows[1].price-step)
         return 1;
      if(high_count>=3 && low_count>=3 &&
         highs[1].price<highs[2].price-step &&
         lows[1].price<lows[2].price-step &&
         highs[0].price<highs[1].price+step)
         return -1;
      return 0;
     }

   bool ClosedBeyond(const MqlRates &rates[],const IctSwing &swing,const bool above) const
     {
      int last=swing.shift;
      if(last>ArraySize(rates))
         last=ArraySize(rates);
      for(int i=1; i<last; i++)
        {
         if(above && rates[i].close>swing.price)
            return true;
         if(!above && rates[i].close<swing.price)
            return true;
        }
      return false;
     }

   void AddLevel(IctLevel &levels[],const double price,const datetime formed,const bool is_high) const
     {
      if(price<=0.0 || formed<=0)
         return;
      int n=ArraySize(levels);
      ArrayResize(levels,n+1);
      levels[n].price=price;
      levels[n].formed=formed;
      levels[n].is_high=is_high;
     }

   bool WindowExtreme(const MqlRates &bars[],const int copied,
                      const datetime start_server,const datetime end_server,
                      double &high,double &low) const
     {
      high=0.0;
      low=0.0;
      bool any=false;
      for(int i=0; i<copied; i++)
        {
         if(bars[i].time<start_server || bars[i].time>=end_server)
            continue;
         if(!any || bars[i].high>high)
            high=bars[i].high;
         if(!any || bars[i].low<low)
            low=bars[i].low;
         any=true;
        }
      return (any && high>low);
     }

   void ShiftEasternDays(int &year,int &month,int &day,const int delta) const
     {
      datetime shifted=IctCivilToUtc(year,month,day,12,0)+(datetime)(delta*86400);
      MqlDateTime parts;
      TimeToStruct(shifted,parts);
      year=parts.year;
      month=parts.mon;
      day=parts.day;
     }

   void PreviousWeekday(int &year,int &month,int &day) const
     {
      ShiftEasternDays(year,month,day,-1);
      for(int guard=0; guard<4; guard++)
        {
         int dow=IctWeekdaySunday0(year,month,day);
         if(dow!=0 && dow!=6)
            return;
         ShiftEasternDays(year,month,day,-1);
        }
     }

   datetime ToServer(const datetime gmt) const
     {
      return (datetime)((long)gmt+((long)TimeCurrent()-(long)TimeGMT()));
     }

   void CollectSessionLevels(const MqlRates &minute_bars[],const int copied,
                             const MqlDateTime &eastern,IctLevel &levels[]) const
     {
      int year=eastern.year;
      int month=eastern.mon;
      int day=eastern.day;

      // Asia belongs to this New York date: previous evening 18:00 through 03:00.
      int asia_year=year;
      int asia_month=month;
      int asia_day=day;
      ShiftEasternDays(asia_year,asia_month,asia_day,-1);
      datetime asia_start=ToServer(IctEasternToUtc(asia_year,asia_month,asia_day,18,0));
      datetime asia_end=ToServer(IctEasternToUtc(year,month,day,3,0));
      double high=0.0;
      double low=0.0;
      if(WindowExtreme(minute_bars,copied,asia_start,asia_end,high,low))
        {
         AddLevel(levels,high,asia_end,true);
         AddLevel(levels,low,asia_end,false);
        }

      datetime london_start=ToServer(IctEasternToUtc(year,month,day,3,0));
      datetime london_end=ToServer(IctEasternToUtc(year,month,day,9,30));
      if(WindowExtreme(minute_bars,copied,london_start,london_end,high,low))
        {
         AddLevel(levels,high,london_end,true);
         AddLevel(levels,low,london_end,false);
        }

      int prev_year=year;
      int prev_month=month;
      int prev_day=day;
      PreviousWeekday(prev_year,prev_month,prev_day);
      datetime day_start=ToServer(IctEasternToUtc(prev_year,prev_month,prev_day,9,30));
      datetime day_end=ToServer(IctEasternToUtc(prev_year,prev_month,prev_day,16,0));
      if(WindowExtreme(minute_bars,copied,day_start,day_end,high,low))
        {
         AddLevel(levels,high,day_end,true);
         AddLevel(levels,low,day_end,false);
        }
     }

   void CollectSwingLevels(const IctSwing &swings[],IctLevel &levels[]) const
     {
      for(int i=0; i<ArraySize(swings); i++)
         AddLevel(levels,swings[i].price,swings[i].time,swings[i].is_high);
     }

   bool WasSwept(const IctLevel &level,const MqlRates &bars[],const int copied,
                 const datetime before_server) const
     {
      for(int i=1; i<copied; i++)
        {
         if(bars[i].time<level.formed || bars[i].time>before_server)
            continue;
         if(level.is_high && bars[i].high>level.price+m_point)
            return true;
         if(!level.is_high && bars[i].low<level.price-m_point)
            return true;
        }
      return false;
     }

   // Nearest unswept liquidity in front of price. A nearer level that has
   // already been run is not the magnet anymore; the next one is.
   bool NearestOpenDol(const IctLevel &levels[],const MqlRates &bars[],const int copied,
                       const int direction,const double price,const datetime before_server,
                       double &dol) const
     {
      dol=0.0;
      double best_distance=DBL_MAX;
      for(int i=0; i<ArraySize(levels); i++)
        {
         if(direction==1 && (!levels[i].is_high || levels[i].price<=price))
            continue;
         if(direction==-1 && (levels[i].is_high || levels[i].price>=price))
            continue;
         if(WasSwept(levels[i],bars,copied,before_server))
            continue;
         double distance=MathAbs(levels[i].price-price);
         if(distance<best_distance)
           {
            best_distance=distance;
            dol=levels[i].price;
           }
        }
      return (dol>0.0);
     }

   bool FindGaps(const MqlRates &rates[],const int copied,const int period_seconds,
                 const datetime signal_open,IctGap &gaps[]) const
     {
      int start=ArraySize(gaps);
      if(copied<5)
         return false;

      for(int candle3=1; candle3<copied-2; candle3++)
        {
         int candle2=candle3+1;
         int candle1=candle3+2;
         datetime gap_ready=rates[candle3].time+(datetime)period_seconds;
         if(gap_ready>signal_open)
            continue;

         double range=rates[candle2].high-rates[candle2].low;
         if(range<m_cfg.min_imbalance)
            continue;
         if(IctBodyFraction(rates[candle2])<m_cfg.min_body_fraction)
            continue;

         int direction=0;
         double gap_low=0.0;
         double gap_high=0.0;
         if(rates[candle2].close>rates[candle2].open && rates[candle3].low>rates[candle1].high)
           {
            direction=1;
            gap_low=rates[candle1].high;
            gap_high=rates[candle3].low;
           }
         else if(rates[candle2].close<rates[candle2].open && rates[candle3].high<rates[candle1].low)
           {
            direction=-1;
            gap_low=rates[candle3].high;
            gap_high=rates[candle1].low;
           }
         if(direction==0 || gap_high<=gap_low)
            continue;

         int n=ArraySize(gaps);
         ArrayResize(gaps,n+1);
         gaps[n].low=gap_low;
         gaps[n].high=gap_high;
         gaps[n].candle3_time=rates[candle3].time;
         gaps[n].direction=direction;
         gaps[n].period_seconds=period_seconds;
        }
      return (ArraySize(gaps)>start);
     }

   // Bars that print while the third candle is still open are part of the gap,
   // not a later reaction to it. Only a close after that candle has finished
   // can invert it or chop inside it.
   bool ClosedThroughBefore(const MqlRates &entry_bars[],const int copied,const IctGap &gap) const
     {
      datetime ready=gap.candle3_time+(datetime)gap.period_seconds;
      for(int i=2; i<copied; i++)
        {
         if(entry_bars[i].time<ready)
            break;
         if(gap.direction==1 && entry_bars[i].close<gap.low-m_point)
            return true;
         if(gap.direction==-1 && entry_bars[i].close>gap.high+m_point)
            return true;
        }
      return false;
     }

   int ClosesInside(const MqlRates &entry_bars[],const int copied,const IctGap &gap) const
     {
      datetime ready=gap.candle3_time+(datetime)gap.period_seconds;
      int count=0;
      for(int i=2; i<copied && i<6; i++)
        {
         if(entry_bars[i].time<ready)
            break;
         if(entry_bars[i].close>=gap.low && entry_bars[i].close<=gap.high)
            count++;
        }
      return count;
     }

   bool RoomIsEnough(const int direction,const double entry,const double stop,const double target) const
     {
      double risk=MathAbs(entry-stop);
      double reward=(direction==1 ? target-entry : entry-target);
      if(risk<=0.0 || reward<m_cfg.min_room)
         return false;
      return (reward>=risk*m_cfg.min_reward_risk);
     }

   // The nearest liquidity level still has to be far enough to justify the
   // trade. The order itself stops at two times the risk when that level is
   // farther, because a distant magnet is usually not reached before the stop.
   void AimTarget(const int direction,const double entry,const double stop,IctSignalContext &ctx) const
     {
      ctx.target=ctx.dol;
      double risk=MathAbs(entry-stop);
      if(risk<=0.0)
         return;
      double reward=(direction==1 ? ctx.dol-entry : entry-ctx.dol);
      double cap=risk*2.0;
      if(reward>cap)
         ctx.target=(direction==1 ? entry+cap : entry-cap);
     }

   // The newest close still has to be beyond the level. Otherwise a break
   // that already failed, and was followed by a return through the level,
   // would still look like the current shift.
   int FindBreakShift(const MqlRates &rates[],const int copied,
                      const double level,const bool above,const int newest_allowed) const
     {
      if(above && rates[1].close<=level)
         return -1;
      if(!above && rates[1].close>=level)
         return -1;

      int last=copied-1;
      if(newest_allowed>0 && newest_allowed<last)
         last=newest_allowed;
      for(int i=1; i<last; i++)
        {
         bool beyond=(above ? rates[i].close>level : rates[i].close<level);
         bool prior_inside=(above ? rates[i+1].close<=level : rates[i+1].close>=level);
         if(beyond && prior_inside)
            return i;
        }
      return -1;
     }

   // A sweep is a wick through a level that closes back, after the swing bar
   // has finished and no later than the structure-break bar. The level kept
   // is the strictest one on the newest such bar: the highest swept low, or
   // the lowest swept high. Every close from that bar through the signal bar
   // has to stay on the reclaimed side, which is what "held after the sweep"
   // means and what filters the instant rejection.
   bool SweepHeld(const MqlRates &entry_bars[],const int copied,
                  const IctLevel &levels[],const bool want_low,
                  const datetime earliest_open,const datetime latest_open) const
     {
      int sweep_shift=-1;
      double swept_price=0.0;
      for(int i=1; i<copied; i++)
        {
         if(entry_bars[i].time<earliest_open || entry_bars[i].time>=latest_open)
            continue;

         bool bar_swept=false;
         double bar_price=0.0;
         for(int level_index=0; level_index<ArraySize(levels); level_index++)
           {
            if(levels[level_index].is_high==want_low)
               continue;
            if(levels[level_index].formed>entry_bars[i].time)
               continue;
            bool pierced=(want_low
                          ? entry_bars[i].low<levels[level_index].price-m_point
                          : entry_bars[i].high>levels[level_index].price+m_point);
            bool reclaimed=(want_low
                            ? entry_bars[i].close>levels[level_index].price
                            : entry_bars[i].close<levels[level_index].price);
            if(!pierced || !reclaimed)
               continue;
            if(!bar_swept ||
               (want_low && levels[level_index].price>bar_price) ||
               (!want_low && levels[level_index].price<bar_price))
               bar_price=levels[level_index].price;
            bar_swept=true;
           }
         if(!bar_swept)
            continue;
         sweep_shift=i;
         swept_price=bar_price;
         break;
        }
      if(sweep_shift<0)
         return false;

      for(int i=sweep_shift; i>=1; i--)
        {
         if(want_low && entry_bars[i].close<swept_price)
            return false;
         if(!want_low && entry_bars[i].close>swept_price)
            return false;
        }
      return true;
     }

   bool DetectMss(const MqlRates &structure[],const int structure_copied,
                  const MqlRates &entry_bars[],const int entry_copied,
                  const IctSwing &swings[],const IctLevel &levels[],
                  int &direction,datetime &break_time) const
     {
      direction=0;
      break_time=0;
      int best_direction=0;
      datetime best_time=0;

      for(int side=0; side<2; side++)
        {
         bool bullish=(side==0);
         IctSwing swing,ignored;
         if(!SeparatedSwing(swings,0,bullish,swing,ignored))
            continue;

         int break_shift=FindBreakShift(structure,structure_copied,swing.price,bullish,swing.shift);
         if(break_shift<1)
            continue;
         datetime closed=structure[break_shift].time+(datetime)PeriodSeconds(m_cfg.structure_timeframe);
         if((long)TimeCurrent()-(long)closed>(long)m_cfg.mss_valid_minutes*60)
            continue;
         if(IctBodyFraction(structure[break_shift])<m_cfg.min_mss_body_fraction)
            continue;
         // The staircase that existed when this swing formed has to be the
         // opposite trend. Swings printed by the reversal itself are not included.
         if(TrendAt(swings,swing.time)!=(bullish ? -1 : 1))
            continue;
         datetime swing_closed=swing.time+(datetime)PeriodSeconds(m_cfg.structure_timeframe);
         if(!SweepHeld(entry_bars,entry_copied,levels,bullish,swing_closed,closed))
            continue;

         if(best_time==0 || closed>best_time)
           {
            best_time=closed;
            best_direction=(bullish ? 1 : -1);
           }
        }

      if(best_direction==0)
         return false;
      direction=best_direction;
      break_time=best_time;
      return true;
     }

   ENUM_ICT_SIGNAL EvaluateInverse(const MqlRates &entry_bars[],const int entry_copied,
                                   const IctGap &gaps[],const IctLevel &levels[],
                                   const int direction,IctSignalContext &ctx) const
     {
      datetime signal_time=entry_bars[1].time;
      double price=entry_bars[2].close;
      if(!NearestOpenDol(levels,entry_bars,entry_copied,direction,entry_bars[1].close,signal_time,ctx.dol))
        {
         ctx.reject_reason="no_dol";
         return ICT_SIGNAL_NONE;
        }
      ctx.target=ctx.dol;

      int opposing=(direction==1 ? -1 : 1);
      int in_front=0;
      double furthest=(direction==1 ? 0.0 : DBL_MAX);
      int furthest_index=-1;
      for(int i=0; i<ArraySize(gaps); i++)
        {
         if(gaps[i].direction!=opposing)
            continue;
         if(ClosedThroughBefore(entry_bars,entry_copied,gaps[i]))
            continue;
         double far=(direction==1 ? gaps[i].high : gaps[i].low);
         bool sits=(direction==1 ? (far>price && far<ctx.dol) : (far<price && far>ctx.dol));
         if(!sits)
            continue;
         in_front++;
         if(direction==1 && far>=furthest)
           {
            furthest=far;
            furthest_index=i;
           }
         if(direction==-1 && far<=furthest)
           {
            furthest=far;
            furthest_index=i;
           }
        }
      if(in_front==0 || furthest_index<0)
        {
         ctx.reject_reason="no_fvg";
         return ICT_SIGNAL_NONE;
        }

      ctx.fvg_low=gaps[furthest_index].low;
      ctx.fvg_high=gaps[furthest_index].high;
      const MqlRates bar=entry_bars[1];
      bool cleared=(direction==1 ? bar.close>furthest+m_point : bar.close<furthest-m_point);
      if(!cleared)
        {
         ctx.reject_reason="fvg_stack_remaining";
         return ICT_SIGNAL_NONE;
        }
      if(ClosesInside(entry_bars,entry_copied,gaps[furthest_index])>=2)
        {
         ctx.reject_reason="fvg_chop";
         return ICT_SIGNAL_NONE;
        }

      bool directional=(direction==1 ? bar.close>bar.open : bar.close<bar.open);
      double body=MathAbs(bar.close-bar.open);
      if(!directional || IctBodyFraction(bar)<m_cfg.min_body_fraction || body<m_cfg.min_bounce)
        {
         ctx.reject_reason="inverse_not_clean";
         return ICT_SIGNAL_NONE;
        }

      ctx.stop_distance=m_cfg.stop_points;
      ctx.stop_price=0.0;
      double stop=(direction==1 ? bar.close-m_cfg.stop_points : bar.close+m_cfg.stop_points);
      if(!RoomIsEnough(direction,bar.close,stop,ctx.dol))
        {
         ctx.reject_reason="no_room";
         return ICT_SIGNAL_NONE;
        }

      ctx.model=ICT_MODEL_INVERSE;
      AimTarget(direction,bar.close,stop,ctx);
      return (direction==1 ? ICT_SIGNAL_BUY : ICT_SIGNAL_SELL);
     }

   ENUM_ICT_SIGNAL EvaluateContinuation(const MqlRates &entry_bars[],const int entry_copied,
                                        const IctGap &gaps[],const IctLevel &levels[],
                                        const int direction,IctSignalContext &ctx) const
     {
      datetime signal_time=entry_bars[1].time;
      const MqlRates bar=entry_bars[1];
      if(!NearestOpenDol(levels,entry_bars,entry_copied,direction,bar.close,signal_time,ctx.dol))
        {
         ctx.reject_reason="no_dol";
         return ICT_SIGNAL_NONE;
        }
      ctx.target=ctx.dol;

      bool saw_gap=false;
      bool saw_touch=false;
      bool saw_chop=false;
      int best_index=-1;
      double best_edge=(direction==1 ? -DBL_MAX : DBL_MAX);
      for(int i=0; i<ArraySize(gaps); i++)
        {
         if(gaps[i].direction!=direction)
            continue;
         if(ClosedThroughBefore(entry_bars,entry_copied,gaps[i]))
            continue;
         saw_gap=true;

         bool reached=(direction==1 ? bar.low<=gaps[i].high : bar.high>=gaps[i].low);
         bool broke_far=(direction==1 ? bar.low<gaps[i].low : bar.high>gaps[i].high);
         bool closed_out=(direction==1 ? bar.close>gaps[i].high : bar.close<gaps[i].low);
         if(!reached || broke_far || !closed_out)
            continue;
         saw_touch=true;
         if(ClosesInside(entry_bars,entry_copied,gaps[i])>=2)
           {
            saw_chop=true;
            continue;
           }

         bool directional=(direction==1 ? bar.close>bar.open : bar.close<bar.open);
         double bounce=(direction==1 ? bar.close-bar.low : bar.high-bar.close);
         if(!directional || IctBodyFraction(bar)<m_cfg.min_body_fraction || bounce<m_cfg.min_bounce)
            continue;

         double edge=(direction==1 ? gaps[i].high : gaps[i].low);
         bool closer=(direction==1 ? edge>best_edge : edge<best_edge);
         if(closer)
           {
            best_edge=edge;
            best_index=i;
           }
        }

      if(best_index<0)
        {
         if(!saw_gap)
            ctx.reject_reason="no_fvg";
         else if(!saw_touch)
            ctx.reject_reason="no_rejection";
         else if(saw_chop)
            ctx.reject_reason="fvg_chop";
         else
            ctx.reject_reason="rejection_too_weak";
         return ICT_SIGNAL_NONE;
        }

      ctx.fvg_low=gaps[best_index].low;
      ctx.fvg_high=gaps[best_index].high;
      ctx.stop_distance=0.0;
      ctx.stop_price=(direction==1 ? bar.low : bar.high);
      if(!RoomIsEnough(direction,bar.close,ctx.stop_price,ctx.dol))
        {
         ctx.reject_reason="no_room";
         return ICT_SIGNAL_NONE;
        }

      ctx.model=ICT_MODEL_CONTINUATION;
      AimTarget(direction,bar.close,ctx.stop_price,ctx);
      return (direction==1 ? ICT_SIGNAL_BUY : ICT_SIGNAL_SELL);
     }

public:
                     CIctStrategy(void)
     {
      m_point=0.0;
     }

   bool Initialize(const string symbol,const IctStrategySettings &settings)
     {
      m_symbol=symbol;
      m_cfg=settings;
      m_point=SymbolInfoDouble(m_symbol,SYMBOL_POINT);
      if(m_point<=0.0)
         m_point=0.0;
      return (m_symbol!="");
     }

   void Release(void)
     {
     }

   ENUM_ICT_SIGNAL Evaluate(IctSignalContext &ctx)
     {
      ctx.model=ICT_MODEL_NONE;
      ctx.trend=0;
      ctx.mss=0;
      ctx.fvg_low=0.0;
      ctx.fvg_high=0.0;
      ctx.dol=0.0;
      ctx.stop_price=0.0;
      ctx.stop_distance=0.0;
      ctx.target=0.0;
      ctx.reject_reason="";

      int entry_seconds=PeriodSeconds(m_cfg.entry_timeframe);
      int structure_seconds=PeriodSeconds(m_cfg.structure_timeframe);
      int bias_seconds=PeriodSeconds(m_cfg.bias_timeframe);
      if(entry_seconds<=0 || structure_seconds<=0 || bias_seconds<=0)
        {
         ctx.reject_reason="history_unavailable";
         return ICT_SIGNAL_NONE;
        }

      int entry_bars_needed=(int)MathMax(m_cfg.structure_lookback*(structure_seconds/60),
                                        m_cfg.fvg_lookback_minutes);
      entry_bars_needed=entry_bars_needed/(entry_seconds/60)+30;
      MqlRates entry_bars[];
      int entry_copied=0;
      MqlRates structure[];
      int structure_copied=0;
      MqlRates bias[];
      int bias_copied=0;
      if(!CopySeries(m_cfg.entry_timeframe,entry_bars_needed,entry_bars,entry_copied) ||
         !CopySeries(m_cfg.structure_timeframe,m_cfg.structure_lookback+10,structure,structure_copied) ||
         !CopySeries(m_cfg.bias_timeframe,m_cfg.bias_lookback+10,bias,bias_copied))
        {
         ctx.reject_reason="history_unavailable";
         return ICT_SIGNAL_NONE;
        }
      if(entry_copied<m_cfg.chop_bars+5 ||
         structure_copied<m_cfg.swing_strength*2+10 ||
         bias_copied<m_cfg.swing_strength*2+10)
        {
         ctx.reject_reason="history_unavailable";
         return ICT_SIGNAL_NONE;
        }

      if(IsChoppy(entry_bars,entry_copied))
        {
         ctx.reject_reason="chop";
         return ICT_SIGNAL_NONE;
        }

      IctSwing structure_swings[];
      IctSwing bias_swings[];
      FindSwings(structure,structure_copied,structure_swings);
      FindSwings(bias,bias_copied,bias_swings);

      MqlDateTime eastern;
      IctGmtToEastern(TimeGMT(),eastern);
      IctLevel levels[];
      MqlRates minute_bars[];
      int minute_copied=0;
      // Minute data pins the session extremes. When it is not loaded yet the
      // entry series still has the highs and lows, just on coarser bars.
      if(TryCopy(PERIOD_M1,5000,minute_bars,minute_copied))
         CollectSessionLevels(minute_bars,minute_copied,eastern,levels);
      else
         CollectSessionLevels(entry_bars,entry_copied,eastern,levels);
      CollectSwingLevels(structure_swings,levels);
      if(ArraySize(levels)==0)
        {
         ctx.reject_reason="no_dol";
         return ICT_SIGNAL_NONE;
        }

      datetime mss_time=0;
      int mss_direction=0;
      if(m_cfg.allow_inverse &&
         DetectMss(structure,structure_copied,entry_bars,entry_copied,
                   structure_swings,levels,mss_direction,mss_time))
         ctx.mss=mss_direction;

      IctGap gaps[];
      datetime signal_open=entry_bars[1].time;
      int entry_period=entry_seconds;
      int gap_bars=m_cfg.fvg_lookback_minutes/(entry_seconds/60)+5;
      if(gap_bars>entry_copied)
         gap_bars=entry_copied;
      FindGaps(entry_bars,gap_bars,entry_period,signal_open,gaps);

      MqlRates higher_entry[];
      int higher_copied=0;
      int higher_seconds=structure_seconds;
      int higher_bars=m_cfg.fvg_lookback_minutes/(higher_seconds/60)+5;
      if(higher_bars<8)
         higher_bars=8;
      if(CopySeries(m_cfg.structure_timeframe,higher_bars,higher_entry,higher_copied))
         FindGaps(higher_entry,higher_copied,higher_seconds,signal_open,gaps);

      if(ctx.mss!=0)
         return EvaluateInverse(entry_bars,entry_copied,gaps,levels,ctx.mss,ctx);

      int trend=TrendAt(structure_swings,0);
      int higher_trend=TrendAt(bias_swings,0);
      ctx.trend=trend;
      if(trend==0)
        {
         ctx.reject_reason="no_trend";
         return ICT_SIGNAL_NONE;
        }
      // A flat 30-minute chart does not cancel a 15-minute staircase. Only the
      // opposite staircase does.
      if(higher_trend!=0 && higher_trend!=trend)
        {
         ctx.reject_reason="timeframes_disagree";
         return ICT_SIGNAL_NONE;
        }

      IctSwing protective,ignored_prior;
      bool want_high=(trend==-1);
      if(SeparatedSwing(structure_swings,0,want_high,protective,ignored_prior) &&
         ClosedBeyond(structure,protective,want_high))
        {
         ctx.reject_reason="structure_broken";
         return ICT_SIGNAL_NONE;
        }

      if(!m_cfg.allow_continuation)
        {
         ctx.reject_reason="continuation_disabled";
         return ICT_SIGNAL_NONE;
        }
      return EvaluateContinuation(entry_bars,entry_copied,gaps,levels,trend,ctx);
     }
  };

#endif
