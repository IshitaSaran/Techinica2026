# 12 filler plaintext messages for the Vigenère plant/crack demo.
# Each is ~350-400 letters of ordinary English so frequency analysis has
# enough letters per key position to recover the 8-letter key (TERRAPIN).
# Paste this list into the PLANTS structure in plant_many.py, matching each
# query to one message (order below follows the query list in the prompt).

MESSAGES = {
    "shoes": (
        "The investigator noted that a pair of shoes was recovered near the back entrance of the "
        "warehouse on the evening of the search. The laces were tied in an unusual double knot and "
        "the soles carried traces of pale clay that did not match the gravel of the yard outside. "
        "A small folded receipt was tucked inside the left shoe, listing a purchase made three days "
        "earlier at a hardware store several miles across town, which the team flagged for follow up."
    ),
    "a laptop on a desk": (
        "A silver laptop sat closed on the corner of the desk when the room was first photographed by "
        "the forensic team. The machine was still faintly warm, suggesting it had been used within the "
        "hour, and a thin notebook beside it held a column of numbers that were later matched to a set "
        "of shipping records. Investigators bagged the device carefully, logged its serial number, and "
        "sent it to the lab so the stored files could be examined without altering the original drive."
    ),
    "a dog": (
        "Neighbours described a medium sized brown dog that was often seen near the property during the "
        "weeks before the incident. The animal wore a worn leather collar with no visible tag and tended "
        "to wait patiently by the side gate each morning. One witness recalled that a man in a grey coat "
        "walked the dog along the canal path at dusk, always taking the same quiet route past the old "
        "mill, and investigators hoped a camera along that path might have captured the pair on film."
    ),
    "mountains": (
        "The photographs recovered from the camera showed a broad range of mountains under a heavy grey "
        "sky, with patches of late snow clinging to the higher ridges. A faint trail wound up the lower "
        "slopes toward a wooden shelter that appeared in several frames taken at different times of day. "
        "The timestamps suggested the person had stayed in the area for at least two nights before moving "
        "on, and the team began contacting rangers who might remember an unfamiliar visitor that week."
    ),
    "a car": (
        "A dark coloured car was parked at an awkward angle across two spaces in the lot behind the shop "
        "when the first officers arrived at the scene that morning. The windows were lightly fogged and a "
        "paper coffee cup rested on the dashboard, still half full and faintly warm to the touch. On the "
        "passenger seat lay a crumpled map with one route traced in red ink leading toward the river, and "
        "the plate was recorded so the vehicle could be traced through the registration database quickly."
    ),
    "a person walking": (
        "The clearest frame from the street camera showed a person walking steadily along the far pavement "
        "with both hands pushed deep into the pockets of a long dark coat. They kept close to the wall and "
        "paused only once, at the corner, to glance back toward the junction before continuing out of view. "
        "The gait was even and unhurried, and analysts measured the stride length against known references "
        "in the hope of narrowing down the height of the figure before the next camera picked them up again."
    ),
    "stairs": (
        "A narrow flight of concrete stairs led down from the loading bay to a storage area that the staff "
        "rarely used after the winter months. Dust lay thick on every step except for a single clean line "
        "near the wall, where someone had recently brushed past while carrying something heavy. At the "
        "bottom the team found an empty crate turned on its side and a length of cut rope coiled neatly in "
        "the corner, both of which were photographed and logged before anything in the room was disturbed."
    ),
    "a forest": (
        "The search widened into the forest once the dogs picked up a trail leading away from the clearing "
        "and in among the tall pines. Broken branches and a flattened patch of ferns marked a path that "
        "someone had taken in a hurry, probably after dark given the scuffed and uneven footprints. Deeper "
        "in, the team came upon a cold fire pit ringed with stones and a torn fragment of fabric snagged on "
        "a low thorn, each clue carefully marked with a numbered flag for the photographer to record first."
    ),
    "a beach": (
        "At first light the stretch of beach looked ordinary, but closer inspection revealed a line of "
        "footprints running from the dunes down to the waterline and then stopping abruptly at the tide "
        "mark. A small canvas bag had been half buried in the damp sand, its zip jammed with grit and its "
        "contents soaked through by the rising water. The team worked quickly to recover it before the next "
        "tide, knowing the sea would erase whatever evidence remained on the open sand within a few hours."
    ),
    "a building": (
        "The abandoned building on the edge of the district had been empty for years, its windows boarded "
        "and its doors chained, yet one side entrance showed fresh scratches around the lock. Inside, a thin "
        "layer of dust covered the floor except for a clear trail of footprints leading toward the stairwell "
        "at the rear. On the second level the investigators found a folding chair facing a window with a "
        "clear view of the street, suggesting someone had spent time there watching the comings and goings."
    ),
    "food": (
        "The small kitchen at the back of the flat told its own quiet story to the investigating team that "
        "afternoon. A meal had been left unfinished on the table, the food now cold and a chair pushed back "
        "as though the person had risen suddenly. A grocery bag sat on the counter with its receipt still "
        "inside, stamped with a time only an hour before the call came in. Each item was noted and the "
        "receipt bagged, since the purchase time helped the team build a clearer picture of the final hours."
    ),
    "a phone": (
        "A cracked phone was found face down beneath the sofa cushion, its battery nearly drained but the "
        "screen still faintly responsive when the technician pressed the side button. Several messages were "
        "visible on the lock screen, each from the same unknown number and each sent within a short span "
        "late the previous night. The device was placed in a shielded bag to block any remote signal and "
        "carried to the lab, where the stored data could be copied and examined under proper controlled "
        "conditions."
    ),
}

if __name__ == "__main__":
    for q, m in MESSAGES.items():
        letters = sum(c.isalpha() for c in m)
        print(f"{q:20} chars={len(m):4} letters={letters:4}")