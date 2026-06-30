import { ReactNode, useCallback, useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

export function HelpTooltip({ text, children }: { text: string; children?: ReactNode }) {
  const id = useId()
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const [position, setPosition] = useState({ left: 0, top: 0 })

  const updatePosition = useCallback(() => {
    const rect = triggerRef.current?.getBoundingClientRect()
    if (!rect) return
    const tooltipWidth = 280
    const gap = 8
    const fitsRight = rect.right + gap + tooltipWidth <= window.innerWidth - 12
    setPosition({
      left: fitsRight ? rect.right + gap : Math.max(12, rect.left - tooltipWidth - gap),
      top: Math.min(window.innerHeight - 90, Math.max(90, rect.top + rect.height / 2)),
    })
  }, [])

  const show = () => {
    updatePosition()
    setOpen(true)
  }

  useEffect(() => {
    if (!open) return
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)
    return () => {
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [open, updatePosition])

  return <span className="help-wrap" onMouseEnter={show} onMouseLeave={() => setOpen(false)}>
    {children}
    <button
      ref={triggerRef}
      type="button"
      className="help-trigger"
      aria-label="Podpowiedź"
      aria-describedby={open ? id : undefined}
      onFocus={show}
      onBlur={() => setOpen(false)}
      onClick={show}
    >?</button>
    {open && createPortal(<span className="help-tooltip" role="tooltip" id={id} style={{ position: 'fixed', left: position.left, top: position.top }}>{text}</span>, document.body)}
  </span>
}

export function LabelHelp({ label, text }: { label: string; text: string }) {
  return <span className="label-help">{label}<HelpTooltip text={text}/></span>
}
