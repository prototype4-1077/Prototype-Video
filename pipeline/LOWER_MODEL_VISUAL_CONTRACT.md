# Lower-Model Visual Contract

Use this contract whenever a lower-capability model generates hero art or still-derived footage.
Its purpose is not to make prompts less cinematic. It removes combinations that image models
commonly solve by deforming anatomy or violating object physics.

## Default rule: one subject, one action, one anomaly

A lower-model-safe still contains:

- one primary subject;
- one clearly visible action or state;
- one impossible element at most;
- one dominant light source;
- no hidden interaction that the model must infer.

When a scene needs multiple ideas, distribute them across separate scenes or let motion/stock
footage carry the interaction.

## Automatic simplification triggers

Simplify or route to stock footage when a prompt contains any of these combinations:

1. Two or more visible hands.
2. A hand holding, touching, striking, operating, or merging with another object.
3. Anatomy plus transformation: dissolving, growing, blending, becoming, fusing, or extending.
4. A reflection that must reproduce a person or hand accurately.
5. A face plus machinery, translucent anatomy, or multiple light sources.
6. A tool in motion plus a visible gripping hand.
7. More than one spatial relationship using words such as behind, through, inside, touching,
   crossing, and reflected.
8. More than one impossible element.

## Safer substitutions

- Two hands touching → one object and the shadow or trace of the second action.
- Hand holding a tool → gloved stock footage, or tool alone with a contact mark.
- Hammer above hand → intact prosthetic hand plus hammer-shaped shadow; hammer outside frame.
- Body boundary changing → empty chalk outline or architectural boundary, no person inside.
- Tool becoming part of body → repeated real stock motion with a glove; no morphing.
- People represented inside the self → floor plan, tactile map, network, or illuminated route.
- Mirror/reflection concept → glass, water, projected light, or a duplicate object rather than a
  reflected human.

## Anatomy lock

Whenever any hand remains visible, the prompt must state:

- exactly one visible hand;
- five distinct fingers;
- intact wrist;
- hand lies flat or performs one simple pose;
- no cropped fingers;
- no extra limbs;
- no touching another hand;
- no grasp unless using verified stock footage.

A generated hand that is partially hidden, motion-blurred, reflected, or holding a complex tool
should be rejected before animation.

## Composition lock

Describe the scene in this order:

1. Camera position and crop.
2. Exact number of subjects.
3. Subject pose or object placement.
4. One action.
5. One impossible element.
6. Lighting.
7. Negative constraints.

Example:

> Low table-level camera. Exactly one intact five-finger silicone prosthetic hand lies flat on a
> wooden table. A hammer-shaped shadow passes across it; the hammer is outside the frame. One warm
> laboratory lamp. No human hand, no grasp, no impact, no extra fingers, no reflection, no text.

## Selection gate

Before a generated still is animated, inspect it at full resolution for:

- finger count and joints;
- wrist continuity;
- tool geometry;
- contact points;
- duplicated objects;
- inconsistent shadows;
- reflection mismatch;
- unreadable or pseudo-text;
- body parts emerging from the background.

Any anatomy or physics failure is a hard rejection. Do not rely on motion, cropping, grain, or
captions to hide it.

## Routing priority

1. Genuine stock footage for hands, tools, medical work, mirrors, and physical interaction.
2. Generated non-human geometry or objects for abstract mechanisms.
3. Generated human imagery only when the pose is simple and anatomy is fully visible.
4. Complex anatomy or transformation requires a higher-capability model or manual approval.
