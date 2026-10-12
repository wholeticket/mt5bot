# Nasdaq session EA for MetaTrader 5

A native MQL5 Expert Advisor that trades one Nasdaq playbook. It is research
software, not a promise of profit. The channel breakout and failed-break fade
that used to live here have been removed.

Run it on a Nasdaq symbol (`NAS100`, `US100`, `USTEC`, `NQ`, `MNQ`, or whatever
your broker calls the index). The distances below are **index points in the
price**. On a chart where the price is `18000.0`, forty points is `40.0`, not
forty `SYMBOL_POINT` steps. If a broker quotes the index in a scaled price,
scale the point inputs to match.

## The model

Two entries, one management rule. Both need a clean 5-minute tape. If more than
about two thirds of the recent closes alternate color, the EA stands aside.

**Continuation.** The 15-minute and 30-minute structure both have to be the
same staircase: higher highs and higher lows, or lower highs and lower lows,
with each step at least `InpMinSwingStepPoints` (default 20). Price pulls back
into a fair value gap and the signal candle rejects it. The stop is the wick
of that rejection. The target is the nearest unswept draw on liquidity in the
trend direction.

**Inverse.** Used after a liquidity sweep and a market structure shift, and it
takes priority over continuation while the shift is fresh
(`InpMssValidMinutes`, default 90). A shift is a 15-minute close through the
last swing, in the opposite direction of the staircase that existed when that
swing formed, after price has wicked through a liquidity level and closed back.
The entry is a 5-minute or 15-minute fair value gap that price closes straight
through, including every stacked gap still sitting between price and the
target. The stop is a fixed `InpStopPoints` (default 40) from the fill.

A fair value gap is the three-candle imbalance: the middle candle is at least
`InpMinImbalancePoints` (default 40) and its body is at least
`InpMinBodyFraction` of its range (default 0.70). The entry candle has to meet
that same body test and travel at least `InpMinBouncePoints` (default 30).
There must be at least `InpMinRoomPoints` (default 30) from the entry to the
target, and at least `InpMinRewardRisk` (default 1) units of reward per unit of
risk. A gap with two or more recent closes sitting inside it is skipped.

Draws on liquidity, marked each day in New York time:

- Asia high and low, 18:00 to 03:00
- London high and low, 03:00 to 09:30
- Previous cash-session high and low, 09:30 to 16:00, skipping weekends
- 15-minute swing highs and swing lows

A level that has already been traded through is not a target. The nearest
remaining one is. If that one is too close, the trade is skipped rather than
aimed at a further level.

## When it is allowed to trade

New York time, on the clock of the bar that just closed:

- Morning, 09:30 to 10:30
- Afternoon, 13:00 to 16:00, and only if the morning did not produce a setup
- Nothing from 11:30 to 13:00

The whole New York day is blocked on the third Friday of the month, and on a
day whose US calendar contains an FOMC or Federal Funds event. Other
high-importance US releases, plus events whose name contains "Powell" or
"Fed Chair", block entries from `InpNewsMinutesBefore` minutes before the
release until `InpNewsMinutesAfter` minutes after (default 10 and 10). The
calendar feed is read as UTC. If the terminal has no calendar, entries are not
blocked and the journal says `calendar_unavailable`. Speeches that are not on
the economic calendar are not detected.

## Management and size

The broker-side take profit is the liquidity level. At `InpPartialRewardRisk`
(default 1), half the position is closed and the stop is moved to the fill.
The remainder is left to the liquidity level. There is no trailing stop.

`InpPartialFraction` only works when the volume can be split and still leave a
legal remainder. A one-lot position on a symbol whose minimum is one lot is
moved to breakeven without a trim, and the journal says `partial_skipped`.

Size comes from `InpRiskPercent` of equity and the stop distance, not from a
fixed contract count. The playbook's 7 or 10 micro contracts is a sizing choice
for one account; this EA will not take that many unless the risk percent and
the account are large enough to pay for them. On MNQ, one index point is about
$2 per contract, so a 40-point stop risks about $80 per contract before
commission.

`InpMaximumSpreadPoints` is in **broker points** (`SYMBOL_POINT`), which is a
different unit from the index-point inputs above. Set it for the symbol you
actually trade. `InpCommissionPerLotRoundTurn` should be the round-turn
commission in account currency per lot; leave it at 0 for a spread-only CFD.
The tester still cannot charge that commission itself. Read
`TESTER|event=result` for the estimate.

## Install

1. In MT5, choose `File > Open Data Folder`.
2. Copy `MQL5/Experts/RobustForexEA.mq5` into `MQL5/Experts`.
3. Copy `MQL5/Include/RobustForex` into `MQL5/Include`, overwriting the
   existing folder.
4. Copy `MQL5/Presets/NAS100_ICT.set` into `MQL5/Profiles/Tester`. Delete any
   older preset for this EA. Those files belong to the removed channel
   strategy and their input names no longer match.
5. Compile in MetaEditor. Proceed only at zero errors and zero warnings.
6. Do not enable live trading. Validate in the Strategy Tester on the Nasdaq
   symbol, with real ticks, then on demo.

The magic number is `26101201`. Positions opened by the previous strategy used
a different magic and are left alone.

Anchors for the daily loss and drawdown locks are terminal global variables
named `RobustForex_<account>_*`. After a deposit or withdrawal, delete them in
`Tools > Global Variables` while the EA is stopped, then restart.

## Journal

Messages use `AREA|key=value` fields.

- `SIGNAL`: a setup that passed the price rules, with the model
  (`continuation` or `inverse`), the gap, the liquidity target, and the stop.
- `FILTER`: why a bar was skipped. `chop`, `no_trend`, `timeframes_disagree`,
  `structure_broken`, `no_dol`, `no_fvg`, `no_rejection`, `rejection_too_weak`,
  `fvg_chop`, `fvg_stack_remaining`, `inverse_not_clean`, `no_room`,
  `history_unavailable`, `opex`, `fomc_day`, `red_folder`, `spread`,
  `am_setup_already_formed`.
- `RISK`: sizing and the daily, drawdown, and portfolio locks.
- `TRADE`: fills, the partial, the move to breakeven, and rejects when the
  live price has already spent the stop or the target.
- `TESTER`: gross result, estimated commission, and net result.
