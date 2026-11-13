# Pick: yock/ping, 2026-11-12

Queue: open + ready-for-agent (103). Blockers = native dependencies (all 103 empty) ∪ `Blocked by:` line ∪ `## Blocked by` section. Waiting label: `blocking` (also needs-info). All 144 referenced blockers resolved (111 closed, 33 open).

# Frontier

#722 fan 3 parent #591 Trail: a hostile's station on own-ship's quarter
#673 fan 2 parent #591 The hunt at tracking: Berkut's and Korshun's sequences to a fix
#410 fan 1 parent #365 The debrief's ocean view
#642 fan 1 parent #591 Trail checks: the escort SSN's stern sweep, with the trail-check rate as the first era override
#650 fan 1 parent #591 Side by direct identification: IFF and voice for ships and aircraft, an HF send for a submarine at PD
#658 fan 1 parent #591 Group taskings: the guide's feed, paired bearing fixes, relay pursuit and takeover
#669 fan 1 parent #591 MAD: the run, the slant envelope and the reconfirm before a drop
#684 fan 1 parent #591 APR-2 and APR-3
#685 fan 1 parent #591 Stand-off carriers: the flight abstracted, the payload real
#692 fan 1 parent #591 Countermeasures: the shared noisemaker and the mobile imitator
#712 fan 1 parent #591 The intelligence trawler at the late-Soviet peak
#716 fan 1 parent #591 The heat clock: the crew's heat report and Equipment faults
#721 fan 1 parent #591 Line-ups on every detection in the debrief logs
#826 fan 0 parent #94 Prosecute: sink a named target
#837 fan 0 parent #94 Covert secondaries
#839 fan 0 parent #94 Counter-detections and heard emissions in the debrief
#840 fan 0 parent #94 The standing orders in force against the true torpedo path
#803 fan 0 parent #117 No close contacts, and an ESM contact's urgency by strength
#844 fan 0 parent #117 Allied submarine notices as boundaries on the chart
#846 fan 0 parent #117 Nav in the debrief after the lift: chart errors, the true bottom, evasion depths and traffic
#954 fan 0 parent #117 Hostiles read an accurate chart, not own-ship's chart errors
#781 fan 0 parent #130 Tune the notch and the noisemaker against Peppe's criterion
#396 fan 0 parent #365 Shore-model traffic and the briefed sea-area summary
#407 fan 0 parent #365 Intercept marks into a Master
#408 fan 0 parent #365 Torpedoes heard on broadband
#876 fan 0 parent #365 The sub-source mode term in the field queries and the cost table
#882 fan 0 parent #365 Every mode: a shelf reference set, the field queries, the cost-table charge, and rows for the soft shelf
#602 fan 0 parent #591 Hull register: surface, counted, aircraft and allied hulls
#632 fan 0 parent #591 The unit's tracker takes every sensor's measurements
#641 fan 0 parent #591 The battery clock and the snorkel routine for diesel classes
#646 fan 0 parent #591 Ship radar emission rules
#655 fan 0 parent #591 Authored posture shifts during a run, reaching each unit only when it hears
#656 fan 0 parent #591 Submarine notices added mid-run reach units by the broadcast
#657 fan 0 parent #591 Ch 16 hails: warships hail the surface vessels they shadow
#671 fan 0 parent #591 Fixed listeners report to the command post
#674 fan 0 parent #591 Aircraft radar doctrine: intermittent sweeps in search, steady once the hunt refines
#675 fan 0 parent #591 Bingo and relief: the hunt handed over on station
#686 fan 0 parent #591 Wake-homers against surface units
#687 fan 0 parent #591 RPK-8 Zapad
#693 fan 0 parent #591 Evasion across the Doppler notch
#698 fan 0 parent #591 Peacetime: readying weapons and the Decree 1310 warning-charge ladder
#706 fan 0 parent #591 Hauling gear when evading
#707 fan 0 parent #591 Civilian lookouts: sighting a raised mast at periscope depth
#708 fan 0 parent #591 A civilian hears a seeker or a detonation through the hull
#709 fan 0 parent #591 Evasion seen by proxy: a hostile's clue from a civilian's manoeuvre
#710 fan 0 parent #591 Chatter: civilians on the marine band
#718 fan 0 parent #591 Standing evasion breaks the rig and shifts the pumps
#728 fan 0 parent #591 Mast strikes: carried away, the run goes on
#730 fan 0 parent #591 A hostile keeps its standoff on its estimated range
#732 fan 0 parent #591 A civilian notices a near-miss
#738 fan 0 parent #591 Lifelines before the lift: the commander's own contacts and one sealed column
#739 fan 0 parent #591 Messages in Lifelines: the command post's column, sloped arrows, the ones own-ship heard
#740 fan 0 parent #591 Near-misses and collisions in the debrief
#743 fan 0 parent #591 Every hostile torpedo path on the debrief plot
#744 fan 0 parent #591 Gear footprints and a snag-sunk trawler in the debrief
#430 fan 0 parent (none) Research: rule3's arcs, short-range sub-fan and curvature cap in the tracer
#577 fan 0 parent (none) Rough sea: taper the surface loss across θc to 2θc, now that the trapped/steep step reaches ~9 dB
#966 fan 0 parent (none) Tracker doc: Gitea does have native dependencies; wayfinder frontier query misses non-task tickets

# Read by hand

- #430 (frontier): no parent; no blockers. Research follow-up to #372/#282, so no spec part. Kept on the frontier and ranked after all parented tickets with the same fan.
- #577 (frontier): no parent; no blockers. Follow-up from #545's build, outside any spec. Same handling as #430.
- #966 (frontier): no parent; no blockers. A tracker-doc ticket whose body asks the user questions, but it doesn't carry `blocking`, and the one comment answers them by naming the file to fix. Counted as frontier and ranked last. Its prose mentions "blocked by" but there's no line or section, so it has no blockers.
- #583 (blocked by #792): no parent. Body says it's a #578 follow-up that "sits here rather than on a map". Classified on its line only (#614 and #628 closed, #792 open).
- #411: the blocker #77 is a wayfinder map (Scenarios and campaigns), not a build ticket. It resolved as open, so #411 is blocked.
- #954: blockers come only from a `## Blocked by` section (#766, closed). No line, so no disagreement.
- #962: `Part of #591` sits mid-sentence. Taken as the parent. Claimed anyway.
- No ticket's line and section disagree (checked by set comparison on every ticket that has both).
- Comments were checked for blocker changes on all 57 tickets that have comments. #410 (+#600) and #881 (+#897) say they added blockers, and both are already on the body lines.

# Blocked

#402 blocked by #364
#411 blocked by #77
#583 blocked by #792
#638 blocked by #635
#672 blocked by #658
#676 blocked by #663, #673
#677 blocked by #676
#682 blocked by #778
#691 blocked by #682, #778
#694 blocked by #691
#695 blocked by #685
#696 blocked by #692
#697 blocked by #669, #684
#713 blocked by #712
#719 blocked by #747
#720 blocked by #719, #792
#723 blocked by #722
#724 blocked by #723
#725 blocked by #722
#726 blocked by #642
#741 blocked by #721
#742 blocked by #827
#745 blocked by #410
#755 blocked by #89, #92
#792 blocked by #747
#795 blocked by #716
#801 blocked by #747
#823 blocked by #778
#824 blocked by #823
#825 blocked by #823
#827 blocked by #823
#829 blocked by #823, #827
#830 blocked by #747, #778
#831 blocked by #778, #829
#832 blocked by #747
#833 blocked by #832
#834 blocked by #833
#835 blocked by #833
#845 blocked by #747, #792, #832
#847 blocked by #827
#850 blocked by #650
#881 blocked by #897

# Claimed

#635 (yockbot) open blockers: none
#663 (yockbot) open blockers: none
#962 (yockbot) open blockers: none

# Waiting


# Counts

{"queue": 103, "frontier": 58, "blocked": 42, "claimed": 3, "waiting": 0}
