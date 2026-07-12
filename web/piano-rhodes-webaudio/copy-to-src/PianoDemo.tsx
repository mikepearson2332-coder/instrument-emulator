// Minimal example: start audio on a tap, switch piano/rhodes, play a keyboard.
// Copy this into your Vite app (or crib from it). The important part is the
// InstrumentEngine lifecycle; the keyboard UI is just for demonstration.

import { useRef, useState } from 'react';
import { InstrumentEngine, type InstrumentName } from './audio/InstrumentEngine';

// One octave C4..B4 (white keys) for the demo.
const KEYS: { midi: number; label: string }[] = [
  { midi: 60, label: 'C' },
  { midi: 62, label: 'D' },
  { midi: 64, label: 'E' },
  { midi: 65, label: 'F' },
  { midi: 67, label: 'G' },
  { midi: 69, label: 'A' },
  { midi: 71, label: 'B' },
  { midi: 72, label: 'C' },
];

export default function PianoDemo() {
  const engineRef = useRef<InstrumentEngine | null>(null);
  const [started, setStarted] = useState(false);
  const [instrument, setInstrument] = useState<InstrumentName>('piano');

  async function start() {
    const eng = new InstrumentEngine();
    await eng.init();
    await eng.resume(); // we're inside a click handler → allowed on mobile
    await eng.setInstrument('piano');
    engineRef.current = eng;
    setStarted(true);
  }

  async function switchTo(name: InstrumentName) {
    await engineRef.current?.setInstrument(name);
    setInstrument(name);
  }

  if (!started) {
    return <button onClick={start}>Start audio</button>;
  }

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <button
          onClick={() => switchTo('piano')}
          disabled={instrument === 'piano'}
        >
          Piano
        </button>
        <button
          onClick={() => switchTo('rhodes')}
          disabled={instrument === 'rhodes'}
        >
          Rhodes
        </button>
      </div>
      <div style={{ display: 'flex', gap: 2 }}>
        {KEYS.map((k, i) => (
          <button
            key={i}
            style={{ width: 44, height: 160 }}
            onPointerDown={() => engineRef.current?.noteOn(k.midi, 96)}
            onPointerUp={() => engineRef.current?.noteOff(k.midi)}
            onPointerLeave={(e) => {
              if (e.buttons) engineRef.current?.noteOff(k.midi);
            }}
          >
            {k.label}
          </button>
        ))}
      </div>
    </div>
  );
}
