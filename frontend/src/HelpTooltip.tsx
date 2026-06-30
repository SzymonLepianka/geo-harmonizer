import { ReactNode, useId, useState } from 'react'

export function HelpTooltip({ text, children }: { text: string; children?: ReactNode }) {
  const id = useId()
  const [open, setOpen] = useState(false)
  return <span className="help-wrap" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
    {children}
    <button
      type="button"
      className="help-trigger"
      aria-label="Podpowiedź"
      aria-describedby={open ? id : undefined}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      onClick={() => setOpen(true)}
    >?</button>
    {open && <span className="help-tooltip" role="tooltip" id={id}>{text}</span>}
  </span>
}

export function LabelHelp({ label, text }: { label: string; text: string }) {
  return <span className="label-help">{label}<HelpTooltip text={text}/></span>
}
