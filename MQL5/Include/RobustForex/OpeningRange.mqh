#ifndef ROBUST_FOREX_OPENING_RANGE_MQH
#define ROBUST_FOREX_OPENING_RANGE_MQH

#include <RobustForex/Strategy.mqh>

// One break of the New York opening range, then one break of the
// afternoon range. The range is the high and low of the first
// range_minutes after 09:30 and after 13:00. A trade is the first
// later close through that high or low, in the direction of the
// range itself when a drive is required. The stop is the far side
// of the range. The target is a multiple of that risk.

struct OrbSettings
  {
   int    range_minutes;
   double min_range;
   double max_range;
   double reward_risk;
   bool   require_drive;
   int    style;       // 0 break of the range, 1 go with the drive, 2 fade the drive
   double min_drive;
   double fixed_stop;
   bool   shorts_only;
   bool   morning_only;
   int    max_morning_entries; // 0 keeps the 2-or-3 cap
   bool   require_open_fail;   // short only after a checkpoint closed back at the open
   int    weekdays;            // bits Mon=1 Tue=2 Wed=4 Thu=8 Fri=16, 0 or 31 is every day
   int    fade10_weekdays;     // weekdays allowed for the 10:00 fade (8 = Thursday only)
   bool   morning_fade;        // the original 09:40-10:55 short
   bool   day_shots;           // 10:00 fade and 11:00 continuation
   double day_move;            // points from the 09:30 open
   double day_target;          // points from the signal close
   bool   daily_on;            // one trade a day, beside the shots
   int    daily_minute;        // New York minute of that trade
   int    daily_dir;           // 1 goes with the morning move, -1 fades it
   double daily_min_move;
   double daily_max_move;
   double daily_stop;
   double daily_target;
   bool   pm_drive_on;         // 14:30 continuation off the 13:00 afternoon open
   int    pm_drive_weekdays;   // bits Mon=1 Tue=2 Wed=4 Thu=8 Fri=16 (28 = Wed/Thu/Fri)
   double pm_drive_move;       // points from the 13:00 open
   double pm_drive_stop;
   double pm_drive_target;
   bool   london_on;           // 03:30 NY (08:30 UK) London Open range-fade
   double london_min_move;     // 5.0 points from 03:00 NY (08:00 UK) open
   double london_max_move;     // 30.0 points max
   double london_stop;         // 15.0 points stop
   double london_target;       // 90.0 points target (6R)
  };

struct OrbSignal
  {
   ENUM_ICT_SIGNAL signal;
   double          stop_price;
   double          stop_distance;
   double          target;
   string          session;
   string          reason;
  };

class COpeningRange
  {
private:
   OrbSettings m_cfg;
   int         m_day;
   double      m_am_high;
   double      m_am_low;
   double      m_am_open;
   double      m_am_close;
   int         m_am_bars;
   int         m_am_entries;
   bool        m_am_done;
   bool        m_am_open_failed;
   double      m_pm_high;
   double      m_pm_low;
   double      m_pm_open;
   double      m_pm_close;
   int         m_pm_bars;
   bool        m_pm_done;
   double      m_shot_open;
   bool        m_shot_seen;
   bool        m_fade10_done;
   bool        m_with11_done;
   bool        m_daily_done;
   double      m_pm_drive_open;
   bool        m_pm_drive_seen;
   bool        m_pm_drive_done;
   double      m_london_open;
   bool        m_london_seen;
   bool        m_london_done;
   double      m_drive_high;
   double      m_drive_low;
   bool        m_drive_seen;
   bool        m_replay;

   void ResetDay(const int day)
     {
      m_day=day;
      m_am_high=0.0;
      m_am_low=0.0;
      m_am_open=0.0;
      m_am_close=0.0;
      m_am_bars=0;
      m_am_entries=0;
      m_am_done=false;
      m_am_open_failed=false;
      m_pm_high=0.0;
      m_pm_low=0.0;
      m_pm_open=0.0;
      m_pm_close=0.0;
      m_pm_bars=0;
      m_pm_done=false;
      m_shot_open=0.0;
      m_shot_seen=false;
      m_fade10_done=false;
      m_with11_done=false;
      m_daily_done=false;
      m_pm_drive_open=0.0;
      m_pm_drive_seen=false;
      m_pm_drive_done=false;
      m_london_open=0.0;
      m_london_seen=false;
      m_london_done=false;
      m_drive_high=0.0;
      m_drive_low=0.0;
      m_drive_seen=false;
     }

   void Remember(const MqlRates &bar,double &high,double &low,double &open_price,
                 double &close_price,int &bars) const
     {
      if(bars==0)
        {
         high=bar.high;
         low=bar.low;
         open_price=bar.open;
        }
      else
        {
         high=MathMax(high,bar.high);
         low=MathMin(low,bar.low);
        }
      close_price=bar.close;
      bars++;
     }

   ENUM_ICT_SIGNAL Breakout(const MqlRates &bar,const double high,const double low,
                            const double open_price,const double close_price,
                            const bool require_drive,double &stop_price,double &target,
                            string &reason) const
     {
      double range=high-low;
      if(range<m_cfg.min_range)
        {
         reason="range_too_small";
         return ICT_SIGNAL_NONE;
        }
      if(range>m_cfg.max_range)
        {
         reason="range_too_wide";
         return ICT_SIGNAL_NONE;
        }

      bool up=bar.close>high;
      bool down=bar.close<low;
      if(!up && !down)
        {
         reason="";
         return ICT_SIGNAL_NONE;
        }

      if(require_drive)
        {
         double drive=close_price-open_price;
         if(MathAbs(drive)<2.0)
           {
            reason="no_drive";
            return ICT_SIGNAL_NONE;
           }
         if((drive>0.0 && down) || (drive<0.0 && up))
           {
            reason="";
            return ICT_SIGNAL_NONE;
           }
        }

      int direction=(up ? 1 : -1);
      stop_price=(direction==1 ? low : high);
      double risk=MathAbs(bar.close-stop_price);
      if(risk<=0.0)
        {
         reason="no_risk";
         return ICT_SIGNAL_NONE;
        }
      target=(direction==1 ? bar.close+risk*m_cfg.reward_risk
                           : bar.close-risk*m_cfg.reward_risk);
      reason="";
      return (direction==1 ? ICT_SIGNAL_BUY : ICT_SIGNAL_SELL);
     }

   ENUM_ICT_SIGNAL Session(const MqlRates &bar,const int bar_min,
                           const int range_start,const int range_end,const int trade_end,
                           double &high,double &low,double &open_price,double &close_price,
                           int &bars,bool &done,
                           double &stop_price,double &stop_distance,double &target,string &reason)
     {
      if(done || bar_min<range_start)
         return ICT_SIGNAL_NONE;

      if(bar_min<range_end)
        {
         Remember(bar,high,low,open_price,close_price,bars);
         if(m_cfg.style==0 || bar_min+5<range_end)
            return ICT_SIGNAL_NONE;

         double drive=close_price-open_price;
         if(MathAbs(drive)<m_cfg.min_drive)
           {
            done=true;
            reason="no_drive";
            return ICT_SIGNAL_NONE;
           }
         int direction=(drive>0.0 ? 1 : -1);
         if(m_cfg.style==2)
            direction=-direction;
         // The fade only keeps the short. A buy is the side that gave the profit back.
         if(m_cfg.style==2 || m_cfg.shorts_only)
           {
            if(direction==1)
              {
               done=true;
               reason="long_skipped";
               return ICT_SIGNAL_NONE;
              }
           }
         stop_price=0.0;
         stop_distance=m_cfg.fixed_stop;
         target=(direction==1 ? close_price+m_cfg.fixed_stop*m_cfg.reward_risk
                              : close_price-m_cfg.fixed_stop*m_cfg.reward_risk);
         done=true;
         reason="";
         return (direction==1 ? ICT_SIGNAL_BUY : ICT_SIGNAL_SELL);
        }

      int needed=m_cfg.range_minutes/5;
      if(bars<needed || bar_min>=trade_end)
        {
         done=true;
         return ICT_SIGNAL_NONE;
        }

      ENUM_ICT_SIGNAL signal=Breakout(bar,high,low,open_price,close_price,
                                      m_cfg.require_drive,stop_price,target,reason);
      if(signal!=ICT_SIGNAL_NONE)
         done=true;
      else if(reason=="range_too_small" || reason=="range_too_wide" || reason=="no_drive" || reason=="no_risk")
         done=true;
      return signal;
     }

public:
   void SetReplay(const bool replay) { m_replay=replay; }
   void MarkDailyDone(void)          { m_daily_done=true; }

   void ShotState(double &open_price,bool &seen,bool &fade_done,bool &with_done,bool &daily_done) const
     {
      open_price=m_shot_open;
      seen=m_shot_seen;
      fade_done=m_fade10_done;
      with_done=m_with11_done;
      daily_done=m_daily_done;
     }

                     COpeningRange(void)
     {
      m_day=0;
      m_am_done=false;
      m_pm_done=false;
      m_am_bars=0;
      m_pm_bars=0;
      m_replay=false;
      m_drive_seen=false;
      m_daily_done=false;
      m_pm_drive_open=0.0;
      m_pm_drive_seen=false;
      m_pm_drive_done=false;
      m_london_open=0.0;
      m_london_seen=false;
      m_london_done=false;
     }

   void Configure(const OrbSettings &settings)
     {
      m_cfg=settings;
      if(m_cfg.range_minutes<5)
         m_cfg.range_minutes=5;
      if(m_cfg.reward_risk<=0.0)
         m_cfg.reward_risk=1.0;
     }

   // Sell after the open has already run up. Checked every 15 minutes
   // through the morning, so a later push still gets the one short.
   // A down open is never bought.
   ENUM_ICT_SIGNAL MorningShorts(const MqlRates &bar,const int bar_min,
                                 double &stop_distance,double &target)
     {
      int start=9*60+30;
      int last=start+85;
      if(bar_min>=11*60+30)
         m_am_done=true;
      if(m_am_done || bar_min<start || bar_min>=11*60+30)
         return ICT_SIGNAL_NONE;

      Remember(bar,m_am_high,m_am_low,m_am_open,m_am_close,m_am_bars);

      bool checkpoint=(bar_min>=start+10 && bar_min<=last && ((bar_min-start-10)%15)==0);
      if(!checkpoint)
         return ICT_SIGNAL_NONE;

      double drive=m_am_close-m_am_open;
      // A pop only gets faded after the open has already failed. The week of
      // 5 Oct 2026 kept every winner that way: each one popped after a
      // checkpoint had closed at or under the open. The only full stop was
      // Tuesday, which was up from the first checkpoint and never came back.
      if(drive<=0.0)
         m_am_open_failed=true;
      else if(m_cfg.require_open_fail && !m_am_open_failed)
         return ICT_SIGNAL_NONE;
      int cap=(drive>=15.0 ? 3 : 2);
      if(m_cfg.max_morning_entries>0)
         cap=m_cfg.max_morning_entries;
      if(m_am_entries>=cap)
        {
         m_am_done=true;
         return ICT_SIGNAL_NONE;
        }

      double needed=m_cfg.min_drive;
      if(bar_min==last && m_am_entries==0)
         needed=0.0;
      if(drive<=needed)
        {
         if(bar_min>=last)
            m_am_done=true;
         return ICT_SIGNAL_NONE;
        }

      m_am_entries++;
      if(m_am_entries>=cap)
         m_am_done=true;
      stop_distance=m_cfg.fixed_stop;
      target=m_am_close-m_cfg.fixed_stop*m_cfg.reward_risk;
      return ICT_SIGNAL_SELL;
     }

   // London Open range-fade at 03:30 NY (08:30 UK) off the 03:00 NY (08:00 UK) open.
   // When the first 30 minutes of London move 5..30 points on US100.cash, fade it
   // back toward the London open with a 15-point stop and 90-point target ($1,400 risk).
   // Flattened at 09:20 NY (14:20 UK) so the account is always free before 09:30 NY.
   ENUM_ICT_SIGNAL LondonFade(const MqlRates &bar,const int bar_min,
                              double &stop_distance,double &target)
     {
      if(!m_cfg.london_on)
         return ICT_SIGNAL_NONE;
      if(bar_min==3*60)
        {
         m_london_open=bar.open;
         m_london_seen=true;
        }
      if(!m_london_seen || m_london_done || bar_min!=3*60+30)
         return ICT_SIGNAL_NONE;

      m_london_done=true;
      if(m_replay)
         return ICT_SIGNAL_NONE;

      double move=bar.close-m_london_open;
      if(MathAbs(move)<m_cfg.london_min_move || MathAbs(move)>=m_cfg.london_max_move)
         return ICT_SIGNAL_NONE;

      bool buy=(move<0.0);
      stop_distance=m_cfg.london_stop;
      target=bar.close+(buy ? m_cfg.london_target : -m_cfg.london_target);
      return (buy ? ICT_SIGNAL_BUY : ICT_SIGNAL_SELL);
     }

   // Two later shots off the same 09:30 open. At 10:00 a move of day_move
   // points is faded on fade10_weekdays (Thursday). At 11:00 a move of that
   // size is taken in its own direction on shot weekdays (Mon/Wed/Thu/Fri).
   // Each one gets a single try. The target is day_target points beyond that
   // bar's close, and the position is held to the cash close.
   ENUM_ICT_SIGNAL DayShots(const MqlRates &bar,const int bar_min,const int dow,
                            double &stop_distance,double &target)
     {
      int open_min=9*60+30;
      if(bar_min==open_min)
        {
         m_shot_open=bar.open;
         m_shot_seen=true;
        }
      if(!m_shot_seen)
         return ICT_SIGNAL_NONE;

      bool fade_bar=(bar_min==10*60);
      bool with_bar=(bar_min==11*60);
      if(!fade_bar && !with_bar)
         return ICT_SIGNAL_NONE;

      int fade_days=(m_cfg.fade10_weekdays>0 ? m_cfg.fade10_weekdays : m_cfg.weekdays);
      int with_days=(m_cfg.weekdays>0 ? m_cfg.weekdays : 31);
      bool fade_allowed=((fade_days&(1<<(dow-1)))!=0);
      bool with_allowed=((with_days&(1<<(dow-1)))!=0);
      if((fade_bar && !fade_allowed) || (with_bar && !with_allowed))
         return ICT_SIGNAL_NONE;

      if((fade_bar && m_fade10_done) || (with_bar && m_with11_done))
         return ICT_SIGNAL_NONE;
      if(fade_bar)
         m_fade10_done=true;
      else
         m_with11_done=true;
      if(m_replay)
         return ICT_SIGNAL_NONE;

      double move=bar.close-m_shot_open;
      if(MathAbs(move)<m_cfg.day_move)
         return ICT_SIGNAL_NONE;

      bool buy=(fade_bar ? move<0.0 : move>0.0);
      stop_distance=m_cfg.fixed_stop;
      target=bar.close+(buy ? m_cfg.day_target : -m_cfg.day_target);
      return (buy ? ICT_SIGNAL_BUY : ICT_SIGNAL_SELL);
     }

   // On days without the clock shots, the same 11:00 trade can go early.
   // After the 09:30 open, a closed 5-minute bar that is already 60 points
   // away, and has not given back half of that distance, is taken in the
   // direction of the move. That fill replaces 11:00. It is not a second
   // trade, and it does not run all day. Replay only remembers the open.
   ENUM_ICT_SIGNAL EarlyWithMove(const MqlRates &bar,const int bar_min,
                                 double &stop_distance,double &target)
     {
      int open_min=9*60+30;
      if(bar_min==open_min)
        {
         m_shot_open=bar.open;
         m_shot_seen=true;
         m_drive_high=bar.high;
         m_drive_low=bar.low;
         m_drive_seen=true;
        }
      else if(m_shot_seen && bar_min>open_min && bar_min<m_cfg.daily_minute)
        {
         if(!m_drive_seen)
           {
            m_drive_high=bar.high;
            m_drive_low=bar.low;
            m_drive_seen=true;
           }
         else
           {
            m_drive_high=MathMax(m_drive_high,bar.high);
            m_drive_low=MathMin(m_drive_low,bar.low);
           }
        }
      if(m_replay || m_daily_done || !m_shot_seen)
         return ICT_SIGNAL_NONE;
      if(bar_min<open_min || bar_min>=m_cfg.daily_minute)
         return ICT_SIGNAL_NONE;

      double move=bar.close-m_shot_open;
      if(MathAbs(move)<m_cfg.day_move)
         return ICT_SIGNAL_NONE;
      double pullback=(move>0.0 ? m_drive_high-bar.close : bar.close-m_drive_low);
      if(pullback>MathAbs(move)*0.5)
         return ICT_SIGNAL_NONE;

      m_daily_done=true;
      bool buy=(m_cfg.daily_dir>=0 ? move>0.0 : move<0.0);
      stop_distance=m_cfg.daily_stop;
      target=bar.close+(buy ? m_cfg.daily_target : -m_cfg.daily_target);
      return (buy ? ICT_SIGNAL_BUY : ICT_SIGNAL_SELL);
     }

   // One trade on the 11:00 bar when the morning stayed in a range (<60 pts)
   // rather than breaking out. Fading a 10..60 point morning drift back toward
   // the 09:30 open won in 8 of 10 months across 2026.
   ENUM_ICT_SIGNAL DailyOnce(const MqlRates &bar,const int bar_min,
                             double &stop_distance,double &target)
     {
      int open_min=9*60+30;
      if(bar_min==open_min)
        {
         m_shot_open=bar.open;
         m_shot_seen=true;
        }
      if(!m_shot_seen || bar_min!=m_cfg.daily_minute)
         return ICT_SIGNAL_NONE;
      if(m_daily_done)
         return ICT_SIGNAL_NONE;
      m_daily_done=true;
      if(m_replay)
         return ICT_SIGNAL_NONE;
      double move=bar.close-m_shot_open;
      if(MathAbs(move)<m_cfg.daily_min_move || MathAbs(move)<0.5)
         return ICT_SIGNAL_NONE;
      if(m_cfg.daily_max_move>0.0 && MathAbs(move)>=m_cfg.daily_max_move)
         return ICT_SIGNAL_NONE;

      bool buy=(m_cfg.daily_dir>=0 ? move>0.0 : move<0.0);
      stop_distance=m_cfg.daily_stop;
      target=bar.close+(buy ? m_cfg.daily_target : -m_cfg.daily_target);
      return (buy ? ICT_SIGNAL_BUY : ICT_SIGNAL_SELL);
     }

   // Afternoon power-hour continuation at 14:30 NY off the 13:00 NY open.
   // On Wed/Thu/Fri, when price has driven 80+ points between 13:00 and 14:30
   // and the account is flat, ride the drive into the 15:55 close.
   ENUM_ICT_SIGNAL AfternoonDrive(const MqlRates &bar,const int bar_min,const int dow,
                                  double &stop_distance,double &target)
     {
      if(!m_cfg.pm_drive_on)
         return ICT_SIGNAL_NONE;
      if(bar_min==13*60)
        {
         m_pm_drive_open=bar.open;
         m_pm_drive_seen=true;
        }
      if(!m_pm_drive_seen || m_pm_drive_done || bar_min!=14*60+30)
         return ICT_SIGNAL_NONE;
      int pm_days=(m_cfg.pm_drive_weekdays>0 ? m_cfg.pm_drive_weekdays : 28);
      if((pm_days&(1<<(dow-1)))==0)
         return ICT_SIGNAL_NONE;

      m_pm_drive_done=true;
      if(m_replay)
         return ICT_SIGNAL_NONE;

      double move=bar.close-m_pm_drive_open;
      if(MathAbs(move)<m_cfg.pm_drive_move)
         return ICT_SIGNAL_NONE;

      bool buy=(move>0.0);
      stop_distance=m_cfg.pm_drive_stop;
      target=bar.close+(buy ? m_cfg.pm_drive_target : -m_cfg.pm_drive_target);
      return (buy ? ICT_SIGNAL_BUY : ICT_SIGNAL_SELL);
     }

   // Buy only after the first 30 minutes of the afternoon have already
   // fallen 20 points, and only Wednesday through Friday. Monday and
   // Tuesday buys of this same dip lost the profit.
   ENUM_ICT_SIGNAL AfternoonLong(const MqlRates &bar,const int bar_min,const int dow,
                                 double &stop_distance,double &target)
     {
      int start=13*60;
      int last=start+25;
      if(bar_min>last)
         m_pm_done=true;
      if(m_pm_done || bar_min<start || bar_min>last)
         return ICT_SIGNAL_NONE;
      if(dow<3 || dow>5)
        {
         if(bar_min==last)
            m_pm_done=true;
         return ICT_SIGNAL_NONE;
        }

      Remember(bar,m_pm_high,m_pm_low,m_pm_open,m_pm_close,m_pm_bars);
      if(bar_min!=last)
         return ICT_SIGNAL_NONE;

      m_pm_done=true;
      double drop=m_pm_open-m_pm_close;
      if(drop<20.0)
         return ICT_SIGNAL_NONE;

      stop_distance=m_cfg.fixed_stop;
      target=m_pm_close+m_cfg.fixed_stop*m_cfg.reward_risk;
      return ICT_SIGNAL_BUY;
     }

   ENUM_ICT_SIGNAL Evaluate(const MqlRates &bar,const MqlDateTime &eastern,OrbSignal &out)
     {
      out.signal=ICT_SIGNAL_NONE;
      out.stop_price=0.0;
      out.stop_distance=0.0;
      out.target=0.0;
      out.session="";
      out.reason="";

      int day=IctDayKey(eastern);
      if(day!=m_day)
         ResetDay(day);

      // The 60-point shots stay on their days. The once-a-day trade is
      // allowed on the other weekdays as well.
      int dow=eastern.day_of_week;
      if(dow<1 || dow>5)
         return ICT_SIGNAL_NONE;
      bool shot_day=true;
      if(m_cfg.weekdays>0 && m_cfg.weekdays<31)
         shot_day=((m_cfg.weekdays&(1<<(dow-1)))!=0);

      int bar_min=eastern.hour*60+eastern.min;
      if(m_cfg.style==2)
        {
         if(m_cfg.london_on)
           {
            ENUM_ICT_SIGNAL lon=LondonFade(bar,bar_min,out.stop_distance,out.target);
            if(lon!=ICT_SIGNAL_NONE)
              {
               out.signal=lon;
               out.session="london";
               return lon;
              }
           }
         if(shot_day && m_cfg.morning_fade)
           {
            ENUM_ICT_SIGNAL fade=MorningShorts(bar,bar_min,out.stop_distance,out.target);
            if(fade!=ICT_SIGNAL_NONE)
              {
               out.signal=fade;
               out.session="am";
               return fade;
              }
           }
         if(m_cfg.day_shots)
           {
            ENUM_ICT_SIGNAL shot=DayShots(bar,bar_min,dow,out.stop_distance,out.target);
            if(shot!=ICT_SIGNAL_NONE)
              {
               out.signal=shot;
               out.session="day";
               return shot;
              }
           }
         if(m_cfg.daily_on)
           {
            ENUM_ICT_SIGNAL daily=DailyOnce(bar,bar_min,out.stop_distance,out.target);
            if(daily!=ICT_SIGNAL_NONE)
              {
               out.signal=daily;
               out.session="daily";
               return daily;
              }
           }
         if(m_cfg.pm_drive_on)
           {
            ENUM_ICT_SIGNAL pm_drive=AfternoonDrive(bar,bar_min,dow,out.stop_distance,out.target);
            if(pm_drive!=ICT_SIGNAL_NONE)
              {
               out.signal=pm_drive;
               out.session="daily";
               return pm_drive;
              }
           }
         if(m_cfg.morning_only)
            return ICT_SIGNAL_NONE;
         if(!shot_day)
            return ICT_SIGNAL_NONE;
         // Afternoon dip stays on with the day shots. A shot still open
         // blocks it, because a new order is only sent when the book is flat.
         {
            ENUM_ICT_SIGNAL buy=AfternoonLong(bar,bar_min,eastern.day_of_week,
                                              out.stop_distance,out.target);
            if(buy!=ICT_SIGNAL_NONE || m_cfg.morning_only)
              {
               out.signal=buy;
               out.session=(buy==ICT_SIGNAL_BUY ? "pm" : "am");
               return buy;
              }
         }
        }

      int am_start=9*60+30;
      int am_end=am_start+m_cfg.range_minutes;
      ENUM_ICT_SIGNAL signal=Session(bar,bar_min,am_start,am_end,11*60+30,
                                     m_am_high,m_am_low,m_am_open,m_am_close,
                                     m_am_bars,m_am_done,
                                     out.stop_price,out.stop_distance,out.target,out.reason);
      if(signal!=ICT_SIGNAL_NONE || out.reason!="" || m_cfg.morning_only)
        {
         out.signal=signal;
         out.session="am";
         return signal;
        }

      int pm_start=13*60;
      int pm_end=pm_start+m_cfg.range_minutes;
      signal=Session(bar,bar_min,pm_start,pm_end,15*60+50,
                     m_pm_high,m_pm_low,m_pm_open,m_pm_close,
                     m_pm_bars,m_pm_done,
                     out.stop_price,out.stop_distance,out.target,out.reason);
      out.signal=signal;
      if(signal!=ICT_SIGNAL_NONE || out.reason!="")
         out.session="pm";
      return signal;
     }
  };

#endif
