/** Range input with a label and a formatted value. */
export function Slider({ label, value, min, max, step, display, onChange }: { label: string; value: number; min: number; max: number; step: number; display: string; onChange: (v: number) => void }) {
  const pct = max > min ? ((value - min) / (max - min)) * 100 : 100;
  return (
    <label className="block py-3">
      <span className="flex items-center justify-between text-sm">
        <span>{label}</span>
        <span className="tnum font-semibold text-accent">{display}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-3 h-1.5 w-full cursor-pointer appearance-none rounded-full [&::-moz-range-thumb]:size-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:bg-white [&::-webkit-slider-thumb]:size-5 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-[0_2px_8px_rgba(0,0,0,.5)]"
        style={{ background: `linear-gradient(90deg, var(--color-accent) ${pct}%, var(--color-ink-600) ${pct}%)` }}
      />
    </label>
  );
}
