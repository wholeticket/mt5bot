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
                     COpeningRange(void)
     {
      m_day=0;
      m_am_done=false;
      m_pm_done=false;
      m_am_bars=0;
      m_pm_bars=0;
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

      // Monday, Thursday and Friday made the money on the 2026 tape.
      // Tuesday was the losing day. Wednesday's stops are what walked
      // the account through the $45,000 floor. 0 and 31 keep every day.
      int dow=eastern.day_of_week;
      if(m_cfg.weekdays>0 && m_cfg.weekdays<31 && dow>=1 && dow<=5 &&
         (m_cfg.weekdays&(1<<(dow-1)))==0)
         return ICT_SIGNAL_NONE;

      int bar_min=eastern.hour*60+eastern.min;
      if(m_cfg.style==2)
        {
         ENUM_ICT_SIGNAL fade=MorningShorts(bar,bar_min,out.stop_distance,out.target);
         if(fade!=ICT_SIGNAL_NONE)
           {
            out.signal=fade;
            out.session="am";
            return fade;
           }
         ENUM_ICT_SIGNAL buy=AfternoonLong(bar,bar_min,eastern.day_of_week,
                                           out.stop_distance,out.target);
         if(buy!=ICT_SIGNAL_NONE || m_cfg.morning_only)
           {
            out.signal=buy;
            out.session=(buy==ICT_SIGNAL_BUY ? "pm" : "am");
            return buy;
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
