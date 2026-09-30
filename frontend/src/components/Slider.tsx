import { useId } from "react";

export function Slider({
  label,
  value,
  min,
  max,
  step,
  onChange,
  display,
  hint,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
  display?: (value: number) => string;
  hint?: string;
}) {
  const id = useId();
  return (
    <div className="slider">
      <div className="slider__row">
        <label htmlFor={id}>{label}</label>
        <output htmlFor={id}>{display ? display(value) : value.toFixed(2)}</output>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        aria-describedby={hint ? `${id}-hint` : undefined}
      />
      {hint ? (
        <p className="slider__hint" id={`${id}-hint`}>
          {hint}
        </p>
      ) : null}
    </div>
  );
}
