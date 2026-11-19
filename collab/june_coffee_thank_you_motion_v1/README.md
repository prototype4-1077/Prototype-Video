# GS070A — coffee handoff, isolated motion test

Play `coffee-handoff.mp4` at normal speed. Forty frames at 1080p30
(1.33 seconds), intentionally silent. This is the visitor's visible
reply to June's offer. Neither 38-second cut was changed.

The table is fixed. The cup is one rigid cel made from the **filled**
body of the receiving key and the clear loop of the approach key.
Its lip and coffee don't redraw during the slide. It stops before
the visitor's grip is complete. Two separate arm cels articulate
over the table; curled fingers show through the loop, thumb settles
over the top, and June releases afterward. The tremor is subtle; it
decays as the visitor comes into contact.

Decoding and tracking the distinctive blue rim chip gave a 129 px
horizontal displacement at 1080p (112 source pixels), zero measured
vertical displacement, and no measurable movement after F16.
Full visitor contact is authored at F23; June's release begins
after F23 and is complete by F30. `decoded-handoff.jpg` shows the
staging and `decoded-contact-close.jpg` samples the fingers, rim,
and loop through contact. The quick wrist turn softens the fingers
slightly between keys; the sheets don't establish whether it feels
natural or whether the story beat earns its time.

June's **right hand** is the interpretation that matches the dorsal
fingers and thumb in this pair. The earlier storyboard called it
left; the art didn't follow that direction. The preceding wide shot
uses his left to steady the mug, so a straight splice would risk the
same continuity issue we set out to fix. Recommended next proof:
show his right hand visibly entering from the ledger side before
it makes contact, then test this beat as a separate longer ending.
Do not cut the existing protected pour or closing performance just
to fit the gesture.

The same output can be regenerated from tracked art:

    python -m pipeline.cartoon_coffee_thank_you --output NEW_DIRECTORY

`handoff-proof.json` records source hashes, the sequence clock and
output hash. No actor-performance approval, production edit, or
main-branch promotion. No paid service or new sound.
