# Speech Generation Notes

## Speech generation

Generated the voice cues using Google Text to Speech API with the following settings:

- **Model**: Gemini 2.5 Pro TTS
- **Style prompt**: "You are a firm, but kind flight instructor. Speaking in an authoritative tone, somewhat quickly."
- **Language**: English (United Kingdom)
- **Voice**: Callirrhoe
- **Encoding**: LINEAR16, 44.1 kHz
- **Speed**: 1.0
- **Gain**: 0dB

**Note**: You have to request audio generation a number of times until you get the correct voice actor. There seems to be three disctinct ones under a single "Voice" name.

## Script for the voice cues

- `Correct the drift.wav`: "Correct the drift!"
- `Get ready to take control.wav`: "Get ready to take control."
- `Great pedals.wav`: "Great pedal control."
- `I have control.wav`: "I have control!"
- `Nice recovery.wav`: "Nice recovery. Excellent job stabilizing the hover."
- `Now you know how to hover.wav`: "Congratulations! You can hold a perfect hover."
- `Perfect.wav`: "That's perfect. You're doing great!"
- `Phase 1 intro.wav`: "In this exercise you are only controlling the pedals. I will control the cyclic and the collective. Look outside at a distance and choose a visual reference point. Try to keep the nose of the helicopter pointed at it, using the pedals."
- `Phase 2 intro.wav`: "In this exercise you are only controlling the collective. I will control the cyclic and the pedals. Try to keep the helicopter at the current altitude."
- `Phase 3 intro.wav`: "In this exercise you are controlling the pedals and the collective. I will control the cyclic. Try to keep the current heading and altitude. Notice that adding more collective requires adding more left pedal."
- `Phase 4 intro.wav`: "In this exercise you are only controlling the cyclic. I will control the pedals and the collective. Try to keep a stable attitude. Relax your hand and only make minute adjustments."
- `Phase 5 intro.wav`: "In this exercise you are controlling the cyclic and the pedals. I will control the collective. Try to keep a stable attitude and heading. Notice that adding more left pedal requires adding more left cyclic, to avoid drifting to the right."
- `Phase 6 intro.wav`: "In this exercise you have all three controls. Try to keep a stable attitude, heading, and altitude. Arrest any drift. Only make small adjustments, to avoid overcorrecting."
- `Phase transition.wav`: "Now that you have mastered this, let's go to the next phase. I'll take back control and explain the next exercise."
- `Relax cyclic.wav`: "Relax your hand on the cyclic. Make smaller inputs!"
- `Smooth collective.wav`: "Relax your collective hand. Make small, gradual adjustments to control your vertical speed."
- `Smooth cyclic.wav`: "Very smooth on the cyclic! Keep those corrections small and calm."
- `Steady pedals.wav`: "Keep your feet steady! Avoid pumping the pedals. Apply gentle, continuous pressure."
- `We are too high.wav`: "Watch your altitude! We are too high. Smoothly lower the collective to bring us down."
- `We are too low.wav`: "Watch your altitude! We are too low. Smoothly add collective to arrest the descent."
- `You have all controls.wav`: "You have all controls."
- `You have the collective and the pedals.wav`: "You have the collective and the pedals."
- `You have the collective.wav`: "You have the collective."
- `You have the cyclic and the pedals.wav`: "You have the cyclic and the pedals."
- `You have the cyclic.wav`: "You have the cyclic."
- `You have the pedals.wav`: "You have the pedals."
