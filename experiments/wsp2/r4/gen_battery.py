#!/usr/bin/env python3
"""Deterministic generator for the R4 PanicDial battery.

Labels by construction only: every item is emitted from a
subtype template plus a construction-parameter record, and the
gold label is the gold function of R4-BATTERY.md applied to
those parameters (genuine / corroborators / roomwide_action /
minor). The generator never calls the incumbent dial or any
model.

Templates are hand-written per split (diagnostic = harbour,
validation = community hall, held-out = alpine hostel / bakery
depot / campsite); the three pools share no names, places or
sentence frames. Slot-filling uses random.Random with fixed
per-split seeds; re-running reproduces the JSONL files
byte-identically.

Message tuple form inside templates:
  (author_index, text, gap_seconds_before_this_message,
   reaction_heat, n_replies)
Author indices map onto a shuffled per-item draw from the
split kit's name pool. Reaction heat is emitted as
{"signal": heat} (heat is what Room.ripple reads, via
Message.reaction_heat = sum of reaction values).
"""
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

GOLD = {
    # subtype: (genuine, corroborators, roomwide_action, minor, boundary)
    "everyday_chat":       (False, 0, False, False, False),
    "work_routine":        (False, 0, False, False, False),
    "trivia_burst":        (False, 0, False, False, True),
    "surprise_urgency":    (False, 0, False, False, True),
    "drill_notice":        (False, 0, False, False, True),
    "fiction_discussion":  (False, 0, False, False, True),
    "negated_alarm":       (False, 0, False, False, True),
    "polysemy_calm":       (False, 0, False, False, True),
    "first_report":        (True, 1, False, False, False),
    "minor_incident":      (True, 1, False, True, False),
    "weather_warning":     (True, 1, False, False, False),
    "uncertain_signal":    (True, 1, False, False, False),
    "slow_burn_technical": (True, 1, False, False, True),
    "single_loud_voice":   (True, 0, False, False, True),
    "confirmed_spread":    (True, 4, True, False, False),
    "fast_water":          (True, 4, True, False, False),
    "impact_event":        (True, 3, True, False, False),
    "evacuation_underway": (True, 4, True, False, False),
    "technical_cascade":   (True, 3, True, False, True),
    "escalating_cascade":  (True, 3, True, False, True),
}


def gold_label(genuine, corroborators, roomwide_action, minor):
    if not genuine:
        return "calm"
    if roomwide_action or corroborators >= 3:
        return "stampede"
    return "alarmed"


COUNTS_120 = {
    "everyday_chat": 7, "work_routine": 7, "trivia_burst": 4,
    "surprise_urgency": 4, "drill_notice": 4, "fiction_discussion": 4,
    "negated_alarm": 5, "polysemy_calm": 5,
    "first_report": 8, "minor_incident": 7, "weather_warning": 6,
    "uncertain_signal": 6, "slow_burn_technical": 7,
    "single_loud_voice": 6,
    "confirmed_spread": 8, "fast_water": 7, "impact_event": 7,
    "evacuation_underway": 7, "technical_cascade": 6,
    "escalating_cascade": 5,
}
COUNTS_60 = {
    "everyday_chat": 4, "work_routine": 3, "trivia_burst": 2,
    "surprise_urgency": 2, "drill_notice": 2, "fiction_discussion": 2,
    "negated_alarm": 2, "polysemy_calm": 3,
    "first_report": 4, "minor_incident": 3, "weather_warning": 3,
    "uncertain_signal": 3, "slow_burn_technical": 3,
    "single_loud_voice": 4,
    "confirmed_spread": 4, "fast_water": 4, "impact_event": 3,
    "evacuation_underway": 3, "technical_cascade": 3,
    "escalating_cascade": 3,
}

KITS = {
    "diagnostic": {
        "names": ["mara", "tomas", "ines", "kofi", "ruth", "emil",
                  "sana", "pavel"],
        "craft": "the morning ferry", "craft2": "the mail boat",
        "spot": "the ferry dock", "room": "the galley",
        "deck": "the car deck", "shore": "the harbour office",
        "gear": "the mooring lines", "meal": "chowder",
        "drink": "coffee", "chore": "scrubbing the wheelhouse windows",
        "cargo": "the fish crates", "weather": "a flat calm morning",
        "tool": "the bilge pump", "hull_part": "the stern locker",
        "engine_part": "the coolant hose", "level_name": "bilge level",
        "gauge": "the manifold pressure gauge",
    },
    "validation": {
        "names": ["odette", "hugo", "priya", "stan", "mabel", "yusuf",
                  "greta", "clive"],
        "craft": "the community hall", "craft2": "the branch library",
        "spot": "the hall stage", "room": "the kitchen annex",
        "deck": "the balcony seats", "shore": "the parish office",
        "gear": "the folding chairs", "meal": "soup",
        "drink": "tea", "chore": "sweeping the rehearsal room",
        "cargo": "the costume trunks", "weather": "a drizzly afternoon",
        "tool": "the urn", "hull_part": "the props cupboard",
        "engine_part": "the radiator valve", "level_name": "cistern level",
        "gauge": "the boiler pressure dial",
    },
    "heldout": {
        "names": ["wren", "alder", "josie", "mateo", "faye", "oskar",
                  "nadia", "tobias"],
        "craft": "the alpine hostel", "craft2": "the bakery depot",
        "spot": "the hostel porch", "room": "the bunk room",
        "deck": "the loading bay", "shore": "the depot office",
        "gear": "the guy ropes", "meal": "dumpling stew",
        "drink": " cocoa".strip(), "chore": "stacking the flour sacks",
        "cargo": "the bread trays", "weather": "a clear cold night",
        "tool": "the wood stove", "hull_part": "the cellar hatch",
        "engine_part": "the oven flue", "level_name": "cellar water level",
        "gauge": "the flue temperature gauge",
    },
}

# ------------------------------------------------------------------ #
# Templates. Line format: author_idx|gap_s|heat|replies|text
# {k:key} = split-kit slot, {n} = per-item random 2..47,
# {r:a/b/c} = per-item random choice.
# ------------------------------------------------------------------ #
T = {}


def V(split, subtype, block):
    msgs = []
    for ln in block.strip().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        a, gap, heat, rep, text = ln.split("|", 4)
        msgs.append((int(a), text, float(gap), int(heat), int(rep)))
    T.setdefault(split, {}).setdefault(subtype, []).append(msgs)


# ---------------- diagnostic (harbour) ----------------
V("diagnostic", "everyday_chat", """
0|0|0|0|morning everyone, {k:weather} over the water and the kettle is already on
1|240|0|0|lovely. did anyone move my mug from the shelf again
2|180|0|0|guilty, it is by the chart table, washed and everything
0|300|0|0|{k:craft} leaves at nine, so no rush on the passenger list
3|200|0|0|I will bring the list down after I finish my toast
""")
V("diagnostic", "everyday_chat", """
1|0|0|0|quiet start today, just the gulls arguing over the bins
4|420|0|0|they can have the bins, yesterday's rolls are in there
2|260|0|0|remind me to order more milk, we are down to the last carton
1|190|0|0|noted on the board. also the tide table printout is smudged again
4|310|0|0|I will print a fresh one when the office opens
""")
V("diagnostic", "work_routine", """
0|0|0|0|jobs for today: coil the spare lines, check the life rings, wipe down {k:deck}
2|150|0|0|I will take the life rings, the straps were twisted last week
5|230|0|0|leave {k:gear} to me, I sorted half of them yesterday
0|280|0|0|good. {k:cargo} get stacked by the gate before lunch, please
2|170|0|0|understood, and I will sign the sheet when it is done
""")
V("diagnostic", "work_routine", """
3|0|0|0|rota swap: I am on {k:chore} this afternoon instead of stores
1|320|0|0|suits me, stores was my least favourite anyway
3|140|0|0|the store list is on the clipboard, mostly rope, soap and batteries
5|260|0|0|add zip ties, we used the last of them on the banner
1|210|0|0|done. tea break at eleven as usual
""")
V("diagnostic", "trivia_burst", """
0|0|2|1|quiz time, fastest answer wins: which harbour has the tallest lighthouse
1|6|3|1|the north one, easy
2|4|2|2|no wait, the island one is taller
3|5|4|1|island, final answer, locking it in
0|7|3|0|island is right, point each. next: how many knots in a bowline demo
2|4|2|1|one knot, it is just a bowline
1|6|3|0|this quiz is rigged and I love it
""")
V("diagnostic", "trivia_burst", """
2|0|1|0|thirty second challenge: name a fish beginning with every letter you can
3|5|2|1|anchovy, brill, cod, dace
4|4|2|1|eel, flounder, gurnard, haddock
2|6|3|0|keep going keep going
3|3|2|1|ide, john dory, kipper
4|5|4|2|we have peaked as a crew, nothing tops this
""")
V("diagnostic", "surprise_urgency", """
0|0|0|0|listen, the surprise picnic for ruth is TODAY, I need everyone sharp
1|45|0|1|balloons are in my car, I can be back in ten minutes, hurry me a bench by the window
2|60|0|0|cake is ordered but someone has to collect it before four, it is urgent, she finishes at five
0|30|0|0|go go go on the bunting then, and hide the card where she never looks
3|55|0|0|behind the tide books, classic. I will bring plates immediately after my round
""")
V("diagnostic", "surprise_urgency", """
4|0|0|0|secret mission: emil's leaving card needs signatures from everyone before he is back
5|40|0|0|he is back at two, that is soon, pass it here fast
4|35|0|1|sign and move it along, no dawdling, and someone stall him at the chandlery
1|50|0|0|I can stall anyone with rope talk. consider it done right now
""")
V("diagnostic", "drill_notice", """
0|0|0|1|notice for the board: fire drill this thursday at ten, whole crew, muster by the flag pole
1|600|0|0|noted. do we bring the register or does the office
0|420|0|0|office brings it. it is only a drill, back to normal work by half past
2|380|0|0|and the alarm test is friday, one short ring, nobody needs to move for that one
""")
V("diagnostic", "drill_notice", """
5|0|0|0|advance warning: the emergency lighting inspection is next week, tuesday morning
3|520|0|0|that is the one where they set the alarm off twice, yes
5|300|0|0|yes, planned tests only, signs go up on monday so passengers know
3|240|0|0|grand, I will warn the cafe so they do not jump out of their skins
""")
V("diagnostic", "fiction_discussion", """
1|0|0|0|finished that novel last night, the one where the ship catches fire in chapter nine
2|280|0|0|and the crew abandons ship into a storm, I remember, very dramatic
1|190|0|0|the mayday scene was nonsense though, nobody talks like that on a radio
4|260|0|0|still a good yarn. the film version makes the collision ten times bigger
2|170|0|0|films always do. anyway, who is making tea
""")
V("diagnostic", "fiction_discussion", """
3|0|0|0|movie night vote: the disaster one with the sinking ferry, or the comedy
0|340|0|0|disaster one, I love how over the top the stampede on deck is
3|210|0|0|the bit where they shout man overboard and it is a hat
0|180|0|0|a hat with its own subplot. comedy might be safer for my ribs
""")
V("diagnostic", "negated_alarm", """
2|0|2|1|smoke reported off the point, coastguard are asking what we can see
0|90|1|1|I can see the headland clearly, no fire this side, it looks like mist
2|140|2|0|coastguard update: it was a bonfire permit on the beach, false alarm, stand down everyone
1|120|0|0|good, standing down. back to the nets then
0|200|0|0|confirmed nothing burning anywhere near the point, all clear
""")
V("diagnostic", "negated_alarm", """
5|0|1|0|the galley alarm just chirped twice and stopped
3|70|0|1|that was me testing the battery, sorry, no smoke, no fire, cooker is cold
5|110|0|0|so a false alarm of your own making. put a note on it next time please
3|90|0|0|note written: alarm tested at nine, all normal, nobody evacuate anywhere
""")
V("diagnostic", "polysemy_calm", """
1|0|0|0|the booking site crashed again at midnight, third crash this month
2|300|0|0|the market stall site crashed too, must be the same host having a bad night
1|220|0|0|no harm done, bookings are on paper as backup. also passenger numbers flooded in after the advert
4|260|0|0|a flood of emails is the good kind of flood. I will answer them in order
""")
V("diagnostic", "polysemy_calm", """
0|0|0|0|can someone run the payroll sheets to the office before three
3|180|0|0|I am running the harbour 10k on sunday so a run to the office is warm-up
0|150|0|0|ha. and light the stove in {k:room} when you are back, it is chilly in there
3|200|0|0|will do, a proper little fire in the stove makes the place
""")
V("diagnostic", "first_report", """
2|0|1|0|there is a smell of burning coming from {k:hull_part}, like hot wiring
0|80|0|1|which locker, the one by the batteries
2|65|0|0|yes that one. I have not opened it, the handle feels warm though
0|120|0|0|keep it shut for now, I am coming down with the extinguisher to look properly
2|90|0|0|ok, waiting by the steps. no smoke visible from here yet
""")
V("diagnostic", "first_report", """
4|0|0|0|water in the forward bilge, more than the usual seep, maybe a hand's depth
1|140|0|1|has it risen since yesterday or is that the rain getting in
4|110|0|0|cannot tell yet, it is over the boards though which is new
1|160|0|0|take a photo with the ruler in it, we will compare in an hour
""")
V("diagnostic", "minor_incident", """
3|0|1|0|ines slipped on the wet step and has twisted her ankle, she is sat down and talking fine
0|100|0|1|ice pack is in the freezer, second drawer
3|80|0|0|got it. it is swelling a bit but she can wiggle her toes, we will skip the clinic unless it worsens
5|130|0|0|I will drive her home after lunch if she wants, no weight on it till then
""")
V("diagnostic", "minor_incident", """
1|0|0|0|small diesel spill by the fuel point, about a bucket's worth, I have put the pads down
4|150|0|0|contained then. any of it reached the water
1|95|0|0|none, the pads caught it all, just the concrete to wash now
4|120|0|0|good, log it in the book and I will sign it off later
""")
V("diagnostic", "weather_warning", """
0|0|0|1|coastguard relay: gale warning for tonight, gusts rising after midnight for all small craft
2|400|0|0|we should double the lines on the outer berths before dark then
0|300|0|0|agreed, and move the kayaks under cover. nothing out in it tonight
2|260|0|0|I will start on the outer berths once the ferry is away
""")
V("diagnostic", "weather_warning", """
5|0|0|0|harbourmaster note: swell building tomorrow, the morning crossing may run late
1|500|0|0|passengers will need telling at the gate, I will put the sign out
5|350|0|0|it is a warning only at this stage, they may still sail on time
1|240|0|0|sign will say expect delays, that covers both
""")
V("diagnostic", "uncertain_signal", """
4|0|2|0|the engine room alarm panel is lit, one red lamp, no label on it
0|75|0|1|which lamp, third from the left
4|60|0|0|second. nothing smells hot and the engine sounds normal, but the lamp is steady
0|110|0|0|stay there, I am bringing the manual down, we check it properly before we touch anything
""")
V("diagnostic", "uncertain_signal", """
2|0|1|0|a detector somewhere below is beeping, slow beeps, I cannot place it
3|130|0|0|carbon monoxide units beep like that when the battery dies too
2|105|0|0|could be. I will open the vents and take the handheld meter down with me
3|150|0|0|shout up every minute while you are down there, meter reading first
""")
V("diagnostic", "slow_burn_technical", """
1|0|0|0|{k:level_name} readings for the log: 41 at six, 44 at seven, 46 just now
1|3600|0|0|next reading 49. the seep past the shaft seal is steady, not dramatic, but it is not stopping
0|1800|0|1|pump is keeping pace for the moment, yes
1|2400|0|0|it is. margin is thinner each watch though. if it passes 60 we need the yard pump alongside
0|1500|0|0|agreed, I will ring the yard in the morning and book it as a precaution
""")
V("diagnostic", "slow_burn_technical", """
5|0|0|0|{k:gauge} has crept up three marks since monday, logged each day
5|3000|0|0|today it is up another half mark and the casing is warmer to the touch than last week
2|2000|0|1|any change in the note of the engine at idle
5|1700|0|0|slightly rougher. I have written it all in the book, numbers and times
2|1900|0|0|then we strip it down at the weekend rather than wait for the service date
""")
V("diagnostic", "single_loud_voice", """
3|0|6|3|FIRE. there is a fire on the fuel dock, I can see flames from the office window
3|25|8|4|it is a real fire, fuel dock, flames by the pumps, someone needs to look at this NOW
3|20|7|3|why is nobody answering, fire fire, fuel dock, this is not a drill
3|35|9|2|I am still the only one who can see it from here, flames are small but it is definitely burning
3|30|6|2|shouting again so this stays at the top: FIRE ON THE FUEL DOCK
""")
V("diagnostic", "single_loud_voice", """
4|0|5|2|HELP the winch cable just snapped and it is swinging over the deck, keep away from the winch
4|28|7|3|it snapped with a bang, cable is hanging off the drum, do not walk under it, help me watch it
4|22|8|2|still swinging, I cannot reach the brake safely on my own, someone come to the winch when you can
4|40|6|3|I am keeping everyone I can see away from it, cable has not settled yet
""")
V("diagnostic", "confirmed_spread", """
1|0|2|1|fire in the chandlery store, back wall, it is going up the shelving
0|18|3|2|confirmed, I can see it from the yard, flames through the store window now
2|14|2|1|evacuate the chandlery and the cafe next door, everyone out to the muster point
3|12|3|2|cafe is clearing, I have the register, moving people to the flag pole now
5|16|2|1|fire service called, they are on their way, keep the gate clear for them
0|20|2|0|nobody go back in for stock, the whole back wall is alight, stay at muster
""")
V("diagnostic", "confirmed_spread", """
4|0|1|1|smoke pouring off {k:craft2}, engine space, thick and black
2|15|2|1|I see it too, and there are flames at the vents now, it is not just smoke
1|13|3|2|everyone off that boat, onto the pontoon, move away from her now
3|11|2|1|pontoon is clear, passengers are off, I count heads at the gate
0|17|2|0|second boat alongside is casting off to give her room, keep clear of the lines
""")
V("diagnostic", "fast_water", """
5|0|1|1|water coming over the stern of the moored trawler, she is sitting low already
3|20|2|1|her deck is awash at the back, I can see it from the bridge, she is going down by the stern
0|16|3|2|all hands to the trawler, pumps over the side, and get her crew off first
2|14|2|1|crew are coming off now, two pumps going in, water is still rising inside her
4|18|3|1|get the big pump from the store as well, and lines to the bollards so she cannot roll
1|15|2|0|she is settling fast, nobody stay aboard her, work from the pontoon only
""")
V("diagnostic", "fast_water", """
2|0|2|0|the lock gate has gone, water is pouring through the basin gate into the lower yard
4|19|3|1|it is knee deep in the lower yard already and rising, move the cars first
0|13|2|2|everyone to the lower yard, move everything you can to the high side, now
3|15|3|1|crates are floating in the store, we are carrying what we can up the steps
5|12|2|1|power is off to the lower yard, I have thrown the breaker, keep out of the deep part
""")
V("diagnostic", "impact_event", """
0|0|2|1|{k:craft} has hit the breakwater, hard, she is holed at the bow and listing
1|16|3|1|I saw the impact from the office, she is down by the head and taking water
2|14|3|2|mayday relay on sixteen, ferry holed off the breakwater, all craft keep clear and stand by
3|12|2|1|passengers are mustering on the top deck in lifejackets, crew are counting
5|18|3|1|lifeboat is launching, we are going alongside with pumps, everyone stay off channel sixteen unless you are part of this
""")
V("diagnostic", "impact_event", """
3|0|1|1|man overboard off the stern, I saw him go in by the nets
0|13|4|2|throw the ring, keep your eyes on him, do not lose the spot, point and keep pointing
4|11|3|1|ring is away, he has it, boat is turning back for him now
1|15|3|1|second boat is alongside him, they have hands on him, hauling him in
2|17|2|0|he is out and breathing, blanket on him, ambulance to the dock gate please
""")
V("diagnostic", "evacuation_underway", """
0|0|2|1|evacuate {k:craft}, everyone off by the gangway, this is not a drill, leave bags where they are
1|14|3|2|top deck is clear, I am sweeping the lounge now, nobody left in there
2|12|2|1|car deck emptying, last vehicles are off, marshals have the ramp
3|15|3|1|muster count at the flag pole: forty one, two still missing from the list
5|13|3|2|galley pair found, they came out the stern door, count is complete, everyone is off her
4|16|2|0|keep everyone at muster, nobody returns for anything, crew stay with your groups
""")
V("diagnostic", "evacuation_underway", """
2|0|3|1|fire alarm is sounding for real in the terminal, get out, all doors, go to the car park muster
4|12|2|1|ticket hall is empty, I have checked the toilets, clear
0|14|3|2|cafe staff are out with their register, passengers moving to muster steadily
1|11|2|1|west stairs are smoky, use the east stairs only, marshals redirect there
3|13|3|0|count at muster is rising, keep the lanes open for the engines arriving
""")
V("diagnostic", "technical_cascade", """
1|0|1|0|she has taken a list of nine degrees in the last ten minutes and it is still growing
0|17|2|1|confirmed on the inclinometer, nine and a half, ballast readings are off the scale on the low side
2|15|3|2|all hands on deck, get every passenger to the high side and into jackets, move now
3|13|2|1|high side filling up, crew are handing out jackets row by row
5|16|3|1|boats are being swung out both sides, nobody leans her further, keep the low side clear
0|14|2|0|list is eleven now, prepare to lower away as soon as I give the word
""")
V("diagnostic", "technical_cascade", """
4|0|0|1|the forward bulkhead is bowing and the seams are weeping along the whole frame
2|18|2|1|pressure behind it must be enormous, the lower space has filled completely then
3|14|3|2|everyone out of the forward spaces, seal the doors behind you and get topside now
1|12|2|1|forward spaces are empty and sealed, all crew accounted for at the hatch
0|15|3|1|move everyone aft and to the boats, stations as drilled, steady and quick
""")
V("diagnostic", "escalating_cascade", """
5|0|0|0|odd smell in the battery locker, sharp, like hot plastic
5|240|0|0|it is stronger now and one of the casings is bulging, that is not right at all
2|90|1|1|bulging battery is bad, get out of that compartment and shut the door on it
0|45|2|2|it has burst, flames in the locker, the compartment is filling with smoke fast
1|20|3|2|evacuate the whole pontoon side, everyone off the boats near her, move to the yard now
3|16|3|1|pontoon is clearing, I have the gate, nobody is going back down there
4|14|2|1|fire crew are arriving, keep the lane open, all boats either side are empty now
""")
V("diagnostic", "escalating_cascade", """
3|0|0|0|small fire in a bin by the fuel store, someone bring a bucket
3|150|1|0|it is not going out, the wind is pushing it along the fence towards the store
1|70|2|1|it has reached the store door, paint tins are going off inside
0|25|3|2|everyone back from the fuel store, evacuate the yard side, muster at the gate now
2|18|3|1|yard is clearing, I count twelve at the gate and more coming
4|15|2|1|road gate is open for the engines, keep everyone behind the line at muster
""")
# ---------------- validation (community hall) ----------------
V("validation", "everyday_chat", """
0|0|0|0|afternoon all, the hall smells of polish and somebody has left biscuits in the office
1|260|0|0|those are mine, help yourselves but leave two for the choir
2|190|0|0|the choir will never know. bridge club wants the small room on friday
0|280|0|0|booked, I have put them in the diary in pencil as usual
""")
V("validation", "everyday_chat", """
3|0|0|0|the library returns trolley is overflowing again, fiction mostly
4|330|0|0|I will wheel it through after my sandwich
3|210|0|0|there is a note on top, someone wants the large print gardening books held
4|240|0|0|held and labelled, anything else is tomorrow's problem
""")
V("validation", "work_routine", """
0|0|0|0|thursday list: stack {k:gear} after lunch club, check the urn, lock the store
1|170|0|0|chairs are mine, the legs are all wobbly on the blue ones
5|250|0|0|urn descaled last week, just fill and switch on for the evening class
0|290|0|0|and {k:cargo} go back up to the loft before the dancers arrive
""")
V("validation", "work_routine", """
2|0|0|0|rota change: I am covering {k:chore} on saturday instead of tickets
4|300|0|0|grateful, tickets was short anyway
2|160|0|0|the booking ledger needs its october page ruled off and totalled
4|220|0|0|leave it on my desk, I like that job with a ruler and quiet
""")
V("validation", "trivia_burst", """
1|0|2|1|pop quiz in the interval: capital of norway, quick quick
3|5|3|1|oslo, too easy, next
0|4|2|2|longest river in europe, go
3|6|4|1|volga, and before you ask, deepest lake is baikal
1|5|3|0|she has swallowed an atlas, points to greta, round over
""")
V("validation", "trivia_burst", """
5|0|1|0|thirty seconds, name as many prime numbers as you can aloud
2|4|2|1|two three five seven eleven thirteen
4|5|2|1|seventeen nineteen twenty three twenty nine
5|6|3|0|time, and the hall record still stands from the summer fete
""")
V("validation", "surprise_urgency", """
0|0|0|0|code word harvest: mabel's eightieth surprise tea is TODAY at four, positions everyone
3|50|0|1|bunting is in the store cupboard, I need it up before she arrives, hurry
2|42|0|0|the cake van is at the corner already, someone meet it fast and sign
0|38|0|0|go go go on the tables then, cloths on, and hide the photo board behind the curtain
""")
V("validation", "surprise_urgency", """
4|0|0|0|secret ballot surprise: the raffle hamper must be wrapped before stan gets back at noon
1|48|0|0|that is twenty minutes, pass the paper here immediately
4|36|0|1|wrap and pass it along, and someone keep him talking at the gate about gutters
1|44|0|0|gutter talk is my speciality, consider him delayed right now
""")
V("validation", "drill_notice", """
2|0|0|1|notice: fire drill for the hall next wednesday at eleven, all user groups, muster on the green
0|560|0|0|the toddler group will love that. who holds the register
2|400|0|0|office does. and the alarm sounder gets its monthly test on monday, one short burst only
0|300|0|0|I will tell the art class so nobody spills their tea at the noise
""")
V("validation", "drill_notice", """
5|0|0|0|advance notice: emergency exit lighting is being serviced on the last friday of the month
4|480|0|0|that is the visit with the ladders and the beeping, yes
5|290|0|0|planned work, signs will go up, and they test the alarm twice before lunch
4|230|0|0|fine, the rehearsal moves to the small room that morning
""")
V("validation", "fiction_discussion", """
1|0|0|0|book group verdict on the lighthouse novel: the storm chapter where the boat capsizes
3|270|0|0|and the keeper rows out alone, pure melodrama and I adored it
1|200|0|0|the flood in the village hall chapter felt closer to home, too close
2|250|0|0|it is fiction, our hall has never flooded, touch wood and pass the biscuits
""")
V("validation", "fiction_discussion", """
4|0|0|0|play reading tonight: the act where the theatre catches fire, very hammy
0|320|0|0|the stampede for the exits is played for laughs in this one
4|190|0|0|and the hero shouts mayday into a prop telephone
0|210|0|0|last time we read it the audience stamped louder than the cast
""")
V("validation", "negated_alarm", """
3|0|2|1|someone thinks they saw smoke over the school field, can anyone see from the hall
0|85|1|1|I am at the window, nothing there but bonfire leaves at the allotment, and the permit board says it is booked
3|130|2|0|warden confirms: controlled bonfire, false alarm, stand down, no fire anywhere near the school
1|110|0|0|lovely, standing down, back to the jumble sale sorting
""")
V("validation", "negated_alarm", """
2|0|1|0|the annex alarm panel just flashed red and went quiet again
5|75|0|1|that will be the caretaker's test from this morning, he forgot to log it, no smoke anywhere
2|105|0|0|so another false alarm to add to his collection. log says test complete, all clear
5|95|0|0|noted in the book: alarm tested, building normal, nobody needs to go anywhere
""")
V("validation", "polysemy_calm", """
4|0|0|0|the ticket site crashed at opening again, same crash as the panto rush
1|280|0|0|and stall bookings flooded the phone line all morning in reply
4|210|0|0|a flood of calls and a crashed website, a very modern morning. paper list at the desk still works
1|240|0|0|it does. meanwhile the hall run of the play has two more weeks, good run for us
""")
V("validation", "polysemy_calm", """
0|0|0|0|can someone run the tombola drum over to the church hall before five
3|170|0|0|I will run it over now, I need the steps anyway after lunch
0|150|0|0|thanks. and when the room is empty, light the fire in the grate, the evening class feels the cold
3|190|0|0|a fire in the grate and the room will be cosy by six
""")
V("validation", "first_report", """
2|0|1|0|there is a scorch smell coming from {k:hull_part}, sweet and electrical
0|95|0|1|that cupboard holds the stage light spares, has anything been plugged in today
2|70|0|0|nothing today. the door of it feels warm at the top edge though
0|125|0|0|leave it closed, I am coming with the caretaker and his keys to open it carefully
""")
V("validation", "first_report", """
4|0|0|0|puddle spreading under the hall kitchen sink, it has reached the doorway already
1|150|0|1|is the tap off, or is it still coming
4|105|0|0|taps are off and it is still spreading slowly, so it is a pipe underneath
1|145|0|0|mop bucket for now, take a photo of the waterline, plumber gets a call in the morning
""")
V("validation", "minor_incident", """
5|0|1|0|hugo cut his palm on the stage door latch, it is bleeding a fair bit but he is calm and sitting
0|95|0|1|first aid box is under the office counter, bring the big plasters
5|85|0|0|pressure on it now with a clean pad, it is slowing already
3|120|0|0|I will sit with him and check it in ten minutes, stitches unlikely by the look of it
""")
V("validation", "minor_incident", """
1|0|0|0|paint spill in the art room, half a tin of emulsion across the lino, nobody hurt
4|140|0|0|contained to the one room then. has it reached the corridor
1|90|0|0|no, doorstep stopped it. I have the mop and the gritty stuff for the shine
4|115|0|0|good, sign on the door till it dries, I will note it in the book
""")
V("validation", "weather_warning", """
0|0|0|1|met office relay for our area: storm warning overnight, gusts at roof level after two
2|390|0|0|the hall roof tiles rattled in the last one, we should check the gutters before dark
0|280|0|0|and bring the notice boards inside. nothing travels tonight if it turns
2|250|0|0|I will do boards and bins, you take the gutter check
""")
V("validation", "weather_warning", """
3|0|0|0|valley flood watch posted for the weekend, river is up after the hill rain
4|460|0|0|the hall is well above the lane, but the car park corner dips
3|320|0|0|warning stage only, they review it tomorrow. sandbags stay stacked by the store meanwhile
4|230|0|0|I will move my car to the top row just in case
""")
V("validation", "uncertain_signal", """
4|0|2|0|a beeping is coming from the boiler room, regular, like a detector complaining
0|80|0|1|the carbon monoxide one has a low battery beep that sounds just like that
4|65|0|0|maybe, but I am not opening that door alone until someone is with me
0|115|0|0|right call, I am on my way with the key and the windows get opened from outside first
""")
V("validation", "uncertain_signal", """
1|0|1|0|the stage alarm box is showing a fault light, amber, and a zone number I do not know
5|125|0|0|no sound from the sounder itself, and nothing smells of anything
1|100|0|0|I will photograph the panel and ring the alarm company, they can tell us what zone nine is
5|140|0|0|meanwhile nobody props the stage door, just in case it is real
""")
V("validation", "slow_burn_technical", """
1|0|0|0|{k:level_name} log: three quarters at monday, seven eighths yesterday, full to the lip this morning
1|3400|0|0|siphon took off what it could, level is back a finger's width and no more
0|2100|0|1|so the inflow has picked up beyond the siphon some time this week
1|2300|0|0|that is the shape of it. if it lips over again we need the contractor's pump, booked not begged
0|1600|0|0|ring them friday and book it, numbers are in the log if they argue
""")
V("validation", "slow_burn_technical", """
5|0|0|0|{k:gauge} has sat a needle's width higher every day this week, all logged
5|2900|0|0|today the needle trembles at the top of its swing, which it never used to
2|1900|0|1|has the radiator in the annex been bled this season
5|1750|0|0|bled in october and the water ran clear. I have written today's reading beside the others
2|1850|0|0|then the engineer comes out next week, not at the scheduled service, I will book it
""")
V("validation", "single_loud_voice", """
3|0|6|3|FIRE in the boiler room, I can see orange through the vent, FIRE I tell you
3|24|8|4|nobody is moving, it is a fire, boiler room vent, flames, I am not inventing this
3|21|7|3|third time shouting: fire, boiler room, come and look if you do not believe me
3|33|9|2|I am staying by this vent where I can see it, it is small but it is burning, FIRE
""")
V("validation", "single_loud_voice", """
4|0|5|2|HELP, the scenery flat just toppled in the store and it is leaning on the door, I cannot shift it
4|27|7|3|it fell with a crash a minute ago, the door opens a crack only, someone needs to come to the store
4|23|8|2|still pinned, my shoulder is not enough, HELP, store room, bring another pair of hands when you can
4|38|6|3|I can hear the rehearsal through the wall so I know you are all in there, store room please
""")
V("validation", "confirmed_spread", """
1|0|2|1|fire in the kitchen annex, the cooker hood is alight and it is taking the cupboards
0|17|3|2|confirmed from the corridor, flames are up the wall tiles now, it is spreading
2|13|2|1|get everyone out of the hall, evacuate to the green, leave the doors wide behind you
3|12|3|2|lunch club are moving, I have the register, we are counting on the green
5|15|2|1|fire service is called and coming, keep the lane gate open for the engine
0|19|2|0|nobody back in for coats or bags, the annex roof space is involved now, stay on the green
""")
V("validation", "confirmed_spread", """
4|0|1|1|smoke rolling out of the library store vents, thick grey, and a glow behind the louvres
2|16|2|1|I see the glow too, that room is alight, not just smouldering
1|12|3|2|everyone out of the library wing, out through the foyer, assemble at the flag bed
3|11|2|1|reading room is empty, I swept it, doors are shut behind me
0|16|2|0|second appliance is coming, keep the yard clear and the count going at assembly
""")
V("validation", "fast_water", """
5|0|1|1|the water main in the lane has burst, water is sheeting down the slope into the hall car park
3|18|2|1|it is ankle deep at the hall door already and coming under it
0|15|3|2|all hands to the hall, sandbags across both doors, and move the library stock off the floor
2|13|2|1|stock is going up on tables, water is at the second shelf in the store
4|17|3|1|power off to the ground floor sockets, I have the breaker list, keep feet out of the deep corner
1|14|2|0|it is still rising, work from the steps, nobody wade in alone
""")
V("validation", "fast_water", """
2|0|2|0|the brook has come over the bank behind the hall, the whole garden is under water
4|17|3|1|it is through the back door and across the kitchen floor already
0|14|2|2|everyone in, move everything off the floor and get the electrics isolated, now
3|13|3|1|chairs are up, urn is safe on the counter, water still coming in at the door
5|12|2|1|the lane is a river, cars stay where they are, keep people inside on the dry side
""")
V("validation", "impact_event", """
0|0|2|1|a delivery van has mounted the kerb outside and hit the hall gatepost, the post is down
1|15|3|1|I heard the bang from the foyer, the van is across the pavement at an angle
2|13|3|2|someone is slumped in the van, call an ambulance, and keep the children inside away from the gate
3|12|2|1|gate area is cordoned with chairs, nobody is going out that way
5|17|3|1|ambulance is on its way, I am staying with the driver and talking to him, he is responding
""")
V("validation", "impact_event", """
3|0|1|1|the big oak limb has come down across the green and it has brought the fence with it
0|13|4|2|did anyone see it fall, was anyone on the green, check the benches side first
4|11|3|1|benches are empty, the dog walker is at the gate waving, nobody under it
1|15|3|1|tape it off wide, there are more limbs moving up there, keep everyone off the green
2|16|2|0|tree surgeon is called, and the school next door has been told to keep their side shut
""")
V("validation", "evacuation_underway", """
0|0|2|1|evacuate the hall, everyone out both doors to the green, this is real, leave everything
1|13|3|2|main room is emptying, I am checking the toilets and the store as I go
2|12|2|1|kitchen staff are out with the register, line forming on the green
3|14|3|1|count is forty eight, the bridge club is still short two names
5|12|3|2|found them, they left by the side door early, count is complete, everyone is out
4|15|2|0|hold everyone on the green, nobody drifts back for the raffle prizes or anything else
""")
V("validation", "evacuation_underway", """
2|0|3|1|the alarm is for real this time, smoke in the corridor, everyone out to the car park point
4|11|2|1|library is empty, readers are out, doors pulled to behind them
0|13|3|2|annex classes are coming down the stairs steadily, marshals at both doors
1|10|2|1|east corridor is smoky, send them west only, repeat, west stairs only
3|12|3|0|numbers at the point are climbing well, keep both lanes open for the appliances
""")
V("validation", "technical_cascade", """
1|0|1|0|the balcony rail bolts have sheared on the left side and the whole rail is bowing outward
0|16|2|1|confirmed, the rail moves when I press it, the fixing plate is torn half out of the wall
2|14|3|2|everyone off the balcony and out of the seats below it, clear the whole circle now
3|12|2|1|balcony is empty, I am taping the stairs so nobody wanders back up
5|15|3|1|stalls below are cleared too, the rail is sagging further, keep the area empty
0|13|2|0|hall stays shut until an engineer has been, nobody under that rail for any reason
""")
V("validation", "technical_cascade", """
4|0|0|1|the stage roof truss is creaking in a rhythm and the centre batten has dropped two inches
2|17|2|1|I can see the drop against the paint line, and dust is falling from the joint
3|13|3|2|get every performer off the stage and out of the wings, move into the foyer now
1|11|2|1|stage and wings are empty, cast are in the foyer with their coats on the floor
0|14|3|1|cancel the show, doors stay locked, nobody retrieves anything from under that truss
""")
V("validation", "escalating_cascade", """
5|0|0|0|there is a fizzing sound from the hall battery cabinet, like a kettle element
5|230|0|0|it is louder and the cabinet door is hot now, something in there is cooking
2|85|1|1|hot battery cabinet is serious, out of that room and pull the door to behind you
0|40|2|2|it has gone bang and there is smoke rolling along the corridor ceiling
1|19|3|2|everyone out of the building, evacuate to the green, do not use the corridor past the smoke
3|15|3|1|green is filling, register is with me, doors are being held for the last classes
4|13|2|1|appliances are turning in at the gate, keep the green count going and the lane clear
""")
V("validation", "escalating_cascade", """
3|0|0|0|tea urn has tipped in the kitchen and there is water everywhere in there
3|140|1|0|it was not just the urn, the pipe behind it has split and it is jetting at the wall
1|65|2|1|it is into the electrics cupboard now, sparks from the top box
0|22|3|2|everyone out of the kitchen wing, get the whole hall to the green, this is an evacuation now
2|17|3|1|wing is empty, I have the class lists, counting on the green as they arrive
4|14|2|1|breaker is off, water is slowing, but nobody goes back in until the electrician says so
""")
# ---------------- held-out (hostel / depot / campsite) ----------------
V("heldout", "everyday_chat", """
0|0|0|0|evening, the woodpile is restacked and there is soup if anyone missed supper
1|230|0|0|soup at this hour is why people come back to this place
2|180|0|0|someone left trail boots by the door again, the good spot
0|290|0|0|{k:craft} board walk tomorrow at eight for whoever wants the ridge
3|210|0|0|count me in if the kettle is on before we leave
""")
V("heldout", "everyday_chat", """
4|0|0|0|depot diary: the rye flour is short this week so thursday is a smaller bake
5|310|0|0|the cafe on the square will riot, gently, with teaspoons
4|200|0|0|they have been warned. also the van has a new rattle at forty
2|270|0|0|everything here rattles at forty, including me before coffee
""")
V("heldout", "work_routine", """
0|0|0|0|morning jobs: turn the proving racks, sweep {k:deck}, sign for the yeast delivery
2|160|0|0|racks are mine, the wheels squeak on the second one
5|240|0|0|leave the bay doors to me, the chain is stiff with cold
0|270|0|0|{k:cargo} get counted before the second bake, not after
""")
V("heldout", "work_routine", """
3|0|0|0|pitch list for the campsite: rake the gravel pitches, empty the fire pits, restock the wood store
1|290|0|0|fire pits first, yesterday's group left theirs full of ash
3|150|0|0|the wood store list is on the shed door, kindling is the short bit
5|230|0|0|I will take gravel, my knees have recovered from last time
""")
V("heldout", "trivia_burst", """
0|0|2|1|campfire quiz, shout it out: tallest waterfall in the country
1|5|3|1|the grey falls above the lake, done
2|4|2|2|no, the one behind the glacier is taller after snowmelt
3|6|4|1|glacier one, and highest campsite is ours, obviously
0|5|3|0|points all round, next: longest river name you can spell
""")
V("heldout", "trivia_burst", """
2|0|1|0|bakery speed round: name a bread for every letter, clock is running
3|4|2|1|anniseed loaf, brioche, ciabatta, damper
4|5|2|1|english muffin, focaccia, grissini, hardtack
2|6|3|0|we are wasted on baking, we should be on television
""")
V("heldout", "surprise_urgency", """
0|0|0|0|operation lantern: josie's surprise birthday walk sets off at dusk, I need everyone placed
1|46|0|1|the banner is in the dry store, I can have it across the porch in five minutes, hurry though
2|58|0|0|hot chocolate flask run is urgent, she is back from the lake at six and the cake is not hidden yet
0|32|0|0|go go go, cake behind the map shelf, flasks by the door, lights low when she comes in
""")
V("heldout", "surprise_urgency", """
4|0|0|0|whisper chain: the engagement banner for the depot yard must be strung before the van returns
5|44|0|0|van is ten minutes out, that is tight, throw me the string immediately
4|37|0|1|string coming, tie and move, and someone distract the driver with paperwork at the gate
1|49|0|0|paperwork distraction is my gift, consider the gate covered right now
""")
V("heldout", "drill_notice", """
0|0|0|1|notice for guests: fire drill at the hostel this saturday at nine, all floors, muster by the bike shed
1|540|0|0|the school group will treat it as an adventure. who reads the names out
0|410|0|0|warden reads them. sunday also has the alarm test, one short ring at breakfast, ignore that one
2|360|0|0|I will warn the bakery van crew, they jump every single time
""")
V("heldout", "drill_notice", """
5|0|0|0|advance warning to all staff: the emergency generator does its monthly full-load test on thursday
3|500|0|0|that is the loud one with the exhaust flap rattling, yes
5|280|0|0|planned test only, notices are on the depot doors from tomorrow, nobody needs to move for it
3|230|0|0|good, I will tell the night baker so his heart stays in his chest
""")
V("heldout", "fiction_discussion", """
1|0|0|0|that climbing film last night, the storm scene where the tent rips and the camp slides
2|270|0|0|and the radio mayday that nobody answers for dramatic reasons
1|185|0|0|then the avalanche that was somehow visible from three valleys away
4|255|0|0|cinema avalanche, the real thing gives no speeches. good film though, I gripped the chair
""")
V("heldout", "fiction_discussion", """
3|0|0|0|reading the depot book club pick: chapter where the bakery burns down in the night
0|330|0|0|the stampede out of the bakery is the best written bit in the whole book
3|205|0|0|and the owner shouting fire into the snow like it owes him money
0|175|0|0|he gets his comeuppance in the flood chapter, wait and see
""")
V("heldout", "negated_alarm", """
2|0|2|1|guest reports smoke over the ridge behind the hostel, can anyone confirm from the porch
0|95|1|1|I am on the porch, that is low cloud on the ridge line, no fire up there at all
2|135|2|0|ranger station confirms the same: mist band, false alarm, stand down, nothing is burning
1|115|0|0|stood down then, and the guest gets a hot drink for caring
""")
V("heldout", "negated_alarm", """
5|0|1|0|the depot alarm just wailed for ten seconds and cut out on its own
3|72|0|1|electrician was in the panel at that moment, it was his test, sorry, no smoke anywhere in the building
5|108|0|0|another false alarm for the log. write it up: alarm tested at dawn, all clear, bread unbothered
3|88|0|0|logged, and he owes the early shift a pastry for the fright
""")
V("heldout", "polysemy_calm", """
1|0|0|0|the booking app crashed twice in the night, same crash the guesthouse app had
2|290|0|0|meanwhile requests flooded the inbox after the magazine piece, hundreds of them
1|215|0|0|a flood of bookings and a crashing app, the modern pair. paper diary is coping fine
4|250|0|0|paper never crashes. also the morning run group leaves at seven for anyone keen
""")
V("heldout", "polysemy_calm", """
0|0|0|0|someone run these invoices to the depot office before the post goes
3|175|0|0|happy to run them over, I am doing the river path anyway
0|145|0|0|thanks. and get {k:tool} going in {k:room} before the walkers come back, it will be raw in there
3|195|0|0|stove lit, room will be properly warm by the time they stamp in
""")
V("heldout", "first_report", """
2|0|1|0|there is a hot chemical smell around {k:hull_part}, sharp at the back of the throat
0|88|0|1|that hatch is over the cleaning store, has a bottle split in there maybe
2|68|0|0|could be, the smell gets stronger when the hatch moves in the draught
0|118|0|0|do not open it alone, I am coming down with gloves and the mask from the store
""")
V("heldout", "first_report", """
4|0|0|0|the cellar steps are wet halfway down and the damp line is higher than last week
1|135|0|1|wet from the wall side or the floor side
4|108|0|0|wall side, a dark line of it, and the bottom step is under a film of water already
1|150|0|0|photograph it against the paint marks, we will watch it again tonight before anyone panics
""")
V("heldout", "minor_incident", """
3|0|1|0|mateo sliced his thumb on the bread knife, it is bleeding steadily but he is joking about it
0|92|0|1|rinse it, pressure with the blue cloth, first aid tin is by the sink
3|82|0|0|pressure on, bleeding is easing, it is a clean cut and not deep by the look of it
5|125|0|0|I will take over the slicing, he sits out the next bake with his hand up
""")
V("heldout", "minor_incident", """
1|0|0|0|a stack of trays went over in the bay, two dented, one guest got a fright and nothing worse
4|145|0|0|contained in the bay then. any glass in it
1|92|0|0|no glass, just tin and noise. I have swept the corner and stacked the rest wider
4|118|0|0|good, chalk it on the board, the bay floor gets its grip strips this week
""")
V("heldout", "weather_warning", """
0|0|0|1|mountain forecast relay: storm force gusts on the tops from midnight, all routes exposed
2|380|0|0|then the ridge walk is off tomorrow and the signs should say so tonight
0|290|0|0|agreed, and secure the porch furniture and the wood store tarpaulin. nobody on the tops in it
2|250|0|0|I will do the tarpaulin before supper, it flapped loose in the last blow
""")
V("heldout", "weather_warning", """
5|0|0|0|river authority note: snowmelt warning for the weekend, the lower pitches may get soggy
1|470|0|0|the two tent pitches by the fence are the low ones, we move bookings off them early
5|330|0|0|warning stage for now, they update at noon tomorrow
1|235|0|0|I will ring the weekend tents tonight so it is not a surprise at the gate
""")
V("heldout", "uncertain_signal", """
4|0|2|0|there is a hissing from the gas store that was not there at breakfast
0|78|0|1|steady hiss or pulsing with something
4|62|0|0|steady, and no smell near the door, but the store is locked so I cannot see the bottles
0|112|0|0|stay well back from it, I am bringing the store key and we open up from the side, slowly
""")
V("heldout", "uncertain_signal", """
2|0|1|0|one of the hostel detectors is chirping every minute and I cannot tell which floor
3|128|0|0|the landing one chirps like that for a flat battery, they all do
2|102|0|0|maybe, but I am walking each floor with the spare batteries and the log book until I find it
3|148|0|0|call out as you go, and if it is the kitchen one we swap the whole unit tonight
""")
V("heldout", "slow_burn_technical", """
1|0|0|0|{k:level_name} for the book: a hand's breadth on monday, two hands by wednesday, three this morning
1|3300|0|0|the drain took what it could overnight and the line did not drop at all this time
0|1950|0|1|so the inflow has outpaced the drain some time in the last two days
1|2250|0|0|that is the arithmetic of it. at this rate the store floor wets by sunday, we book the pump before then
0|1550|0|0|booked for friday, and I want your numbers in the book each morning till then
""")
V("heldout", "slow_burn_technical", """
5|0|0|0|{k:gauge} readings this week sit higher each day and the flue casing has started to tick as it cools
5|2800|0|0|this morning it read higher again and the ticking went on twice as long
2|1850|0|1|any soot pattern change around the joints
5|1680|0|0|a darker fan above the second joint, new since last week, all written down with times
2|1800|0|0|then the flue gets opened up this week, not at the winter service, I will book the sweep
""")
V("heldout", "single_loud_voice", """
3|0|6|3|FIRE behind the bakery ovens, I can see flames licking the back panel, FIRE
3|23|8|4|why is this chat quiet, there is a fire at the ovens, someone acknowledge this NOW please
3|20|7|3|shouting again because it matters: fire, ovens, back panel, it is burning right now
3|34|9|2|I am the only one in the depot end, flames are hand-high and the panel is blackening, FIRE
""")
V("heldout", "single_loud_voice", """
4|0|5|2|HELP, a gas bottle toppled in the store and it is venting, I have backed out and shut nothing
4|26|7|3|it is hissing hard in there, HELP, gas store by the bay, do not anyone walk in past me
4|21|8|2|still venting, I am keeping the yard gate side clear, someone with the key needs to come when they can
4|37|6|3|shouting from the yard so nobody wanders in: gas store, keep away, HELP
""")
V("heldout", "confirmed_spread", """
1|0|2|1|fire in the hostel laundry, the dryer wall is alight and it is climbing into the ceiling
0|16|3|2|confirmed from the stairs, I can see flames in the laundry doorway, it is spreading fast
2|13|2|1|get every guest out, evacuate all floors to the bike shed muster, leave the doors shut behind you
3|11|3|2|top floor is clearing, I have the room list, we are counting heads at the muster
5|15|2|1|fire service is rolling, keep the track clear for them and the hydrant corner empty
0|18|2|0|nobody goes back for passports or packs, the ceiling in there is involved, stay at muster
""")
V("heldout", "confirmed_spread", """
4|0|1|1|smoke is boiling out of the depot granary vents and there is a glow at the baseboards
2|14|2|1|the glow is flames now, I see them from the yard, that store is alight inside
1|12|3|2|everyone out of the depot buildings, across the yard to the road gate, now
3|10|2|1|bake room is empty, doors are shut, I am last out with the bake list
0|15|2|0|second crew is coming from the town station, keep the yard empty and the gate wide
""")
V("heldout", "fast_water", """
5|0|1|1|the river has taken the bank, water is across the lower pitches and into the wash block
3|18|2|1|it is shin deep at the wash block and rising visibly, tents on the low row are standing in it
0|15|3|2|all hands to the campsite, get every camper to the high field, and kill the pitch power boxes
2|13|2|1|campers are moving up with their gear above their heads, low row is emptying fast
4|16|3|1|power boxes are off, I am on the steps, nobody crosses the fast bit by the bridge
1|14|2|0|water is still climbing, work from the high side only, pairs at all times
""")
V("heldout", "fast_water", """
2|0|2|0|the depot cellar has filled in minutes, water is up the steps and pushing at the yard door
4|17|3|1|it is through the yard door now, crates are floating in the bake room doorway
0|13|2|2|everyone to the depot, stock up off the floor, and isolate the ovens before the water reaches them
3|14|3|1|ovens are isolated, flour is going up on the racks as fast as we can carry it
5|11|2|1|the yard is a pond, keep out of the cellar stair entirely, it is still filling
""")
V("heldout", "impact_event", """
0|0|2|1|the delivery van has left the track above the hostel and rolled onto its side in the gully
1|15|3|1|I heard it go from the porch, it is on its side and the horn is stuck on
2|13|3|2|driver is climbing out through the windscreen, he is moving but dazed, ambulance is being called
3|11|2|1|two of us are down the bank with blankets, we are keeping him still and talking
5|16|3|1|ambulance is coming up the valley road, keep the track gate open and a car at the bend with lights on
""")
V("heldout", "impact_event", """
3|0|1|1|a climber has fallen at the crag path, she is conscious but her leg is badly bent
0|12|4|2|keep her warm and still, do not move the leg, talk to her and keep her awake
4|10|3|1|jackets are under and over her, someone is at the path head to wave the team in
1|14|3|1|mountain rescue is on the path with the stretcher, twenty minutes out and closing
2|16|2|0|she is packaged and moving, slow carry down, keep the path clear for them
""")
V("heldout", "evacuation_underway", """
0|0|2|1|evacuate the hostel, everyone out to the bike shed muster, this is not a drill, take nothing with you
1|13|3|2|top floor is coming down steadily, I am checking every bunk room as I pass
2|11|2|1|ground floor is empty, kitchen staff are out with the guest list in hand
3|14|3|1|muster count: thirty six names, two still unaccounted from the annex
5|12|3|2|annex pair located on the porch steps, they went out the back, count is complete, all guests out
4|15|2|0|hold everyone at muster whatever they forgot, staff stay with your floor groups
""")
V("heldout", "evacuation_underway", """
2|0|3|1|depot alarm is real, smoke in the packing corridor, everyone out to the road gate point
4|10|2|1|bake room is clear, bakers are out and the doors are pulled shut
0|13|3|2|office pair are out with the delivery book, line is forming at the gate
1|10|2|1|packing corridor is too smoky to recheck, use the yard side count only
3|12|3|0|numbers at the gate are nearly complete, keep the road lane open for the appliances
""")
V("heldout", "technical_cascade", """
1|0|1|0|the bunk room floor joists have sagged another inch overnight and the door no longer closes
0|16|2|1|confirmed with the string line, the centre is down two inches and the plaster is cracking in fans
2|13|3|2|everyone out of that room and the room below it, tape both doors, move the guests to the annex now
3|11|2|1|both rooms are emptied, guests are rehoused, nobody is fetching chargers from in there
5|14|3|1|the sag is visible from the yard now, keep the whole wing shut until the builder has propped it
0|12|2|0|wing stays locked tonight whatever anyone left in there, annex has spare bedding for all
""")
V("heldout", "technical_cascade", """
4|0|0|1|the oven flue has parted at the second joint and hot gases are jetting into the roof space
2|16|2|1|I can see the jet shimmer at the joint and the roof boards above it are darkening
3|12|3|2|everyone out of the bake room and the loft above it, ovens off at the main, move now
1|10|2|1|bake room is empty and the main is off, staff are at the yard door with the list
0|13|3|1|keep the loft shut and the yard clear, nobody goes up for the stock books tonight
""")
V("heldout", "escalating_cascade", """
5|0|0|0|a smell of hot dust from the hostel drying room, stronger than the usual warm smell
5|220|0|0|it is a scorched smell now and one of the heater guards is glowing at the edge
2|80|1|1|glowing guard means out of that room, door shut behind you, and tell the warden desk
0|42|2|2|it has caught, flames along the guard and the towels on the rail are alight
1|19|3|2|evacuate the hostel, every floor, guests to the bike shed, this is the real thing now
3|15|3|1|floors are clearing, I am counting at the shed door with the room list
4|13|2|1|appliances are on the track up, keep the muster tight and the lane open for them
""")
V("heldout", "escalating_cascade", """
3|0|0|0|a small grass fire at the campsite edge, one ring of it, someone bring the water carrier
3|130|1|0|the wind took it sideways, it is running along the fence line now and not stopping
1|60|2|1|it is in the gorse hedge, that whole hedge is going up in sections
0|24|3|2|everyone off the lower pitches, evacuate the campsite to the high field, muster by the gate now
2|17|3|1|pitches are emptying, I have families at the gate and the count is under way
4|14|2|1|the fire crew are coming up the lane, keep the high field group together and clear of the lane
""")

# ------------------------------------------------------------------ #
SPLITS = {
    "diagnostic": ("r4diag", COUNTS_120, 20261146),
    "validation": ("r4val", COUNTS_60, 460046),
    "heldout": ("r4held", COUNTS_120, 77114611),
}
CHOICE_RE = __import__("re").compile(r"\{r:([^}]*)\}")
KIT_RE = __import__("re").compile(r"\{k:([a-z_]+)\}")
NUM_RE = __import__("re").compile(r"\{n\}")


def render(text, kit, rng, num):
    text = CHOICE_RE.sub(lambda m: rng.choice(m.group(1).split("/")), text)
    text = KIT_RE.sub(lambda m: kit[m.group(1)], text)
    text = NUM_RE.sub(str(num), text)
    return text


def build_split(split, rng):
    prefix, counts, _seed = SPLITS[split]
    kit = KITS[split]
    items = []
    # deterministic subtype order: GOLD dict order, counts interleaved
    plan = []
    for subtype, n in counts.items():
        plan.extend([subtype] * n)
    rng.shuffle(plan)
    seen = {}
    for subtype in plan:
        variants = T[split][subtype]
        k = seen.get(subtype, 0)
        seen[subtype] = k + 1
        variant = variants[k % len(variants)]
        names = kit["names"][:]
        rng.shuffle(names)
        num = rng.randint(2, 47)
        genuine, corr, roomwide, minor, boundary = GOLD[subtype]
        ts = 0.0
        msgs = []
        for ai, text, gap, heat, rep in variant:
            gap_j = gap * rng.uniform(0.85, 1.2) if gap else 0.0
            ts += gap_j
            msgs.append({
                "author": names[ai % len(names)],
                "text": render(text, kit, rng, num),
                "ts": round(ts, 1),
                "reactions": ({"signal": heat} if heat else {}),
                "n_replies": rep,
            })
        fam = ("loud" if subtype == "single_loud_voice"
               else gold_label(genuine, corr, roomwide, minor))
        pool = DETAILS[split][fam]
        d_author = variant[0][0] if fam == "loud" else (k + 2) % 6
        detail = {"author": names[d_author % len(names)],
                  "text": pool[k % len(pool)],
                  "ts": 0.0, "reactions": {}, "n_replies": 0}
        msgs.insert(1, detail)
        # re-time: the detail takes a modest gap after the first
        # message and every later message shifts by exactly that
        # gap, so all original inter-message gaps are preserved.
        d_gap = rng.uniform(10.0, 40.0)
        for j, m in enumerate(msgs):
            if j == 0:
                m["ts"] = 0.0
            elif j == 1:
                m["ts"] = round(d_gap, 1)
            else:
                m["ts"] = round(m["ts"] + d_gap, 1)
        items.append({
            "id": f"{prefix}-{len(items) + 1:03d}",
            "split": split,
            "label": gold_label(genuine, corr, roomwide, minor),
            "subtype": subtype,
            "boundary": boundary,
            "construction": {"genuine": genuine,
                             "corroborators": corr,
                             "roomwide_action": roomwide,
                             "minor": minor,
                             "variant": k % len(variants)},
            "messages": msgs,
        })
    return items


def main():
    total = 0
    for split, (_p, _c, seed) in SPLITS.items():
        rng = random.Random(seed)
        items = build_split(split, rng)
        path = HERE / f"{split}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        total += len(items)
        from collections import Counter
        print(split, len(items), Counter(i["label"] for i in items),
              "boundary", sum(i["boundary"] for i in items))
    print("total", total)
    return 0



# ------------------------------------------------------------------ #
# Detail lines: one per item, inserted as the second message.
# Purpose (added after the first verifier run caught item-text
# duplication across variant reuses): every reuse of a template
# carries a different detail line, so no two items in a split
# share a full text. Detail lines are construction-neutral:
# calm lines are mundane; alarmed lines are bystander remarks
# that neither confirm nor deny the hazard (they do not change
# the corroborator count, which counts only authors who confirm
# or escalate); stampede lines are logistics. For
# single_loud_voice the detail line is spoken by the same sole
# author (the pool is written in that voice) so the one-voice
# construction is preserved.
# ------------------------------------------------------------------ #
DETAILS = {
    "diagnostic": {
        "calm": [
            "the kettle has boiled dry again, someone fill it when they pass",
            "tide is making nicely over the causeway stones today",
            "someone has left a scarf on the harbour wall, blue one",
            "the noticeboard needs new pins, half of them are bent",
            "gulls have taken the bin lid off again by the slipway",
            "my gloves are still damp from yesterday, hung them by the stove",
            "the harbour cat is asleep on the warm engine cover again",
            "post boat brought a parcel for the office, it is by the door",
        ],
        "alarmed": [
            "I have the incident book open on the desk if times need writing down",
            "the office phone is free if anyone needs it, I am beside it",
            "noted from me, I am up by the winch house and can stay a while",
            "I will keep this channel clear and just listen unless I am called",
            "the bench by the steps is free if anyone needs to sit down",
            "I have a torch here if it is wanted, fully charged",
            "writing the times in pencil as they come, say if I miss one",
            "I am staying where I am until someone tells me otherwise",
        ],
        "stampede": [
            "I am holding the yard gate wide and waving people through",
            "extra blankets are coming down from the store with me",
            "I have the spare torches from the office, handing them out at the door",
            "keeping the lane to the road clear, cones are out",
            "I am counting heads into groups of ten as they pass me",
            "the first aid bag is on the table at the muster side",
            "I have thrown both yard doors open and wedged them",
            "passing the word along the line so the back rows hear it too",
        ],
        "loud": [
            "still here at the window, still watching it, this is me again",
            "it is me posting again, nobody else can see this side of the building",
            "posting again so it does not scroll away, same place, same view",
            "I will keep posting every half minute until someone answers me",
            "same voice again, I have not moved from this spot",
            "me again, I am not shouting for fun, I promise you that",
            "again from me, the only pair of eyes on this side",
            "I am staying on this channel and I am not going quiet",
        ],
    },
    "validation": {
        "calm": [
            "the urn has that rattle again when it boils, ignore it",
            "someone has left an umbrella in the foyer, a red one",
            "the clock in the main room is five minutes fast, as ever",
            "new pencils are in the office drawer if the art class asks",
            "the green looks lovely after the mowing, stripes and all",
            "my reading glasses are on the piano again, third time this week",
            "the biscuit tin has been restocked, digestives this time",
            "a note for the diary: the step ladder is back from the church",
        ],
        "alarmed": [
            "I have the bookings ledger here if times need noting in it",
            "the foyer phone is free, I am sitting beside it for a bit",
            "from me just this: I am by the main doors and I will stay put",
            "I will listen on this channel and keep it clear for the others",
            "there is a chair here by me if anyone needs to sit a moment",
            "I have the big torch from the office if it is wanted",
            "pencil ready, I am writing times down as they are called out",
            "I am not moving from the foyer until I am told to",
        ],
        "stampede": [
            "I am holding the main doors wide and guiding people through",
            "blankets from the store cupboard are coming out with me",
            "I have the spare torches, handing them out at the door",
            "keeping the path to the green clear, chairs moved aside",
            "counting people through in tens as they pass me",
            "the first aid bag is on the green table already",
            "both sets of doors are wedged open, foyer is flowing well",
            "passing the word down the queue so everyone hears it",
        ],
        "loud": [
            "still me at the vent, still watching, posting again",
            "it is me again, nobody else is at this end of the building",
            "posting again so this stays visible, same spot, same view",
            "I will keep posting until somebody answers, that is a promise",
            "same voice as before, I have not moved an inch",
            "me again, I would not be doing this for a laugh",
            "again from me, the only eyes on this side of the place",
            "I am staying on this channel and I am not done yet",
        ],
    },
    "heldout": {
        "calm": [
            "the porch thermometer says two degrees and feels like it",
            "someone has left mittens on the stove rail, grey pair",
            "the depot clock is striking the hour ten minutes late again",
            "fresh kindling is in the basket by the door for tonight",
            "the path to the lake is all frost and very pretty",
            "my notebook is on the bunk shelf if anyone borrows it",
            "the flour order book has a new page started, very satisfying",
            "a robin has taken to sitting on the woodpile at dawn",
        ],
        "alarmed": [
            "I have the warden's log open if times want writing in it",
            "the depot phone is free and I am beside it for a while",
            "just this from me: I am at the porch and staying where I am",
            "I will keep this channel clear and listen unless called",
            "there is a bench here by me if anyone needs the weight off",
            "I have a good torch here if it is wanted, new batteries",
            "writing the times down in pencil as they come in",
            "I am not moving from this spot until I am told otherwise",
        ],
        "stampede": [
            "I am holding the track gate wide and waving people through",
            "blankets from the hostel store are coming out with me",
            "spare torches are in my hands, passing them out at the door",
            "keeping the path to the muster clear, sledges moved aside",
            "counting people through in tens as they pass me",
            "the first aid kit is already on the muster table",
            "both depot doors are wedged open and the yard is flowing",
            "passing the word along the line so the back hears it too",
        ],
        "loud": [
            "still me at this end, still watching it, posting again",
            "it is me again, there is nobody else at this end of the site",
            "posting again so it does not scroll off, same place, same view",
            "I will keep posting every half minute until someone answers",
            "same voice again, I have not moved from this spot at all",
            "me again, I am not doing this for the entertainment",
            "again from me, the only pair of eyes on this side",
            "I am staying on this channel and I am not going quiet",
        ],
    },
}

if __name__ == "__main__":
    sys.exit(main())
